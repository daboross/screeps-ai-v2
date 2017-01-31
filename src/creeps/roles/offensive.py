from constants import ATTACK_DISMANTLE, ATTACK_POWER_BANK, ENERGY_GRAB, RAID_OVER, REAP_POWER_BANK, TD_D_GOAD, \
    TD_H_D_STOP, TD_H_H_STOP, role_recycling, role_td_healer, target_single_flag, target_single_flag2
from creep_management import autoactions
from creeps.behaviors.military import MilitaryBase
from creeps.behaviors.transport import TransportPickup
from creeps.roles.mining import EnergyHauler
from jstools.screeps import *
from position_management import flags
from utilities import hostile_utils, movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


class TowerDrainHealer(MilitaryBase):
    def run(self):
        target = self.targets.get_new_target(self, target_single_flag, TD_H_H_STOP)
        if not target:
            if len(flags.find_flags(self.home, RAID_OVER)):
                self.memory.last_role = self.memory.role
                self.memory.role = role_recycling
            else:
                self.log("TowerDrainHealer has no target!")
                self.go_to_depot()
            return
        if not self.pos.isEqualTo(target):
            self.follow_military_path(self.home.spawn, target)

        autoactions.instinct_do_heal(self)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, TD_H_H_STOP)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class TowerDrainer(MilitaryBase):
    def should_pickup(self, resource_type=None):
        return False

    def run(self):
        if 'goading' not in self.memory:
            self.memory.goading = False
        if self.memory.goading and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.goading = False
            self.targets.untarget_all(self)
        if not self.memory.goading and self.creep.hits >= self.creep.hitsMax:
            self.memory.goading = True
            self.targets.untarget_all(self)
        goad_target = self.targets.get_new_target(self, target_single_flag, TD_D_GOAD)
        if not goad_target:
            self.log("TowerDrainer has no target!")
            self.memory.last_role = self.memory.role
            self.memory.role = role_recycling
            return

        def set_max_avoid_regular_matrix(room_name, cost_matrix):
            if room_name == goad_target.pos.roomName:
                for x in range(0, 50):
                    for y in range(0, 50):
                        existing = cost_matrix.get(x, y)
                        if existing == 0:
                            terrain = Game.map.getTerrainAt(x, y, room_name)
                            if terrain[0] == 'p':
                                existing = 2
                            elif terrain[0] == 's':
                                existing = 10
                            else:
                                continue
                        cost_matrix.set(x, y, existing + 20)

        if self.memory.goading:
            if self.pos.isEqualTo(goad_target):
                pass
            elif movement.chebyshev_distance_room_pos(self.pos, goad_target) < 50:
                self.move_to(goad_target, {'costCallback': set_max_avoid_regular_matrix})
            else:
                self.follow_military_path(self.home.spawn, goad_target, {'avoid_rooms': [goad_target.pos.roomName]})
        else:
            heal_target = self.targets.get_new_target(self, target_single_flag2, TD_H_D_STOP)
            if not heal_target:
                if len(flags.find_flags(self.home, RAID_OVER)):
                    self.recycle_me()
                else:
                    self.go_to_depot()
                return
            if self.pos.isEqualTo(heal_target):
                pass
            elif movement.chebyshev_distance_room_pos(self.pos, heal_target) < 50:
                # TODO: make a military moveTo method like this
                self.move_to(heal_target, {'costCallback': set_max_avoid_regular_matrix})
            else:
                self.follow_military_path(self.home.spawn, heal_target, {'avoid_rooms': [goad_target.pos.roomName]})

        autoactions.instinct_do_attack(self)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, TD_D_GOAD)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target, {'avoid_rooms': [target.pos.roomName]})
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class Dismantler(MilitaryBase):
    def move_to_can_reach(self, target):
        self.move_to(target)
        path = Room.deserializePath(self.memory['_move']['path'])
        # If we can't reach the target, let's find a new one
        return len(path) and movement.chebyshev_distance_room_pos(path[len(path) - 1], target) <= 1

    def do_dismantle(self, structure):
        if structure.my:
            self.log("WARNING: Dismantling our own {} ({}).".format(structure.structureType, structure))
            Game.notify("WARNING: Creep {} in {} at time {} is dismantling our own {} at {} ({}).".format(
                self.name, self.pos.roomName, Game.time, structure.structureType, structure.pos, structure))
        dismantled = False
        new_target = False
        if self.pos.isNearTo(structure):
            result = self.creep.dismantle(structure)
            if result == OK:
                dismantled = True
                damage = self.creep.getActiveBodyparts(WORK) * DISMANTLE_POWER
                other = self.room.find(FIND_HOSTILE_CREEPS)
                if len(other):
                    heal = _.sum(other, lambda c: c.pos.inRangeTo(structure, 3)
                                                  and c.getActiveBodyparts(WORK) * REPAIR_POWER)
                else:
                    heal = 0
                if damage >= heal + structure.hits:
                    new_target = True
            else:
                self.log("Unknown result from dismantler.dismantle({}): {}".format(structure, result))
        else:
            # If we can't reach the target, let's find a new one
            #new_target = not self.move_to_can_reach(structure) # TODO: this
            self.move_to(structure)
        return new_target, dismantled

    def remove_target(self, target):
        msg = "[dismantle][{}][{}] Dismantle job at {},{} completed! {} untargeting.".format(
            target.pos.roomName, Game.time, target.pos.x, target.pos.y, self.name)
        console.log(msg)
        Game.notify(msg)
        target.remove()

    def run(self):
        if self.memory.dismantling and self.creep.hits < self.creep.hitsMax / 2:
            self.memory.dismantling = False
            self.targets.untarget(self, target_single_flag2)
        if not self.memory.dismantling and self.creep.hits >= self.creep.hitsMax:
            self.memory.dismantling = True
            self.targets.untarget(self, target_single_flag2)

        if self.memory.dismantling:
            target = self.targets.get_new_target(self, target_single_flag, ATTACK_DISMANTLE)
            if not target:
                if len(flags.find_flags(self.home, RAID_OVER)):
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
                        self.memory.last_role = self.memory.role
                        self.memory.role = role_recycling
                else:
                    self.log("Dismantler has no target!")
                    self.go_to_depot()
                return
            if target.memory.civilian:
                self.memory.running = 'idle'
            if self.pos.roomName == target.pos.roomName:
                new_target = False
                dismantled = False
                structure = self.room.look_at(LOOK_STRUCTURES, target)[0]
                if structure:
                    new_target, dismantled = self.do_dismantle(structure)
                else:
                    site = self.room.look_at(LOOK_CONSTRUCTION_SITES, target)[0]
                    if site and not site.my:
                        self.move_to(site)
                    elif self.memory.dt:  # dismantler target
                        mem_pos = positions.deserialize_xy_to_pos(self.memory.dt, target.pos.roomName)
                        structure = self.room.look_at(LOOK_STRUCTURES, mem_pos)[0]
                        if structure:
                            new_target, dismantled = self.do_dismantle(structure)
                        else:
                            site = self.room.look_at(LOOK_CONSTRUCTION_SITES, mem_pos)[0]
                            if site:
                                self.move_to(site)
                            else:
                                new_target = True
                    else:
                        new_target = True

                if new_target:
                    if 'dismantle_all' in target.memory and not target.memory['dismantle_all']:
                        self.remove_target(target)
                        return
                    structures = self.room.find(FIND_STRUCTURES)
                    sites = self.room.find(FIND_CONSTRUCTION_SITES)
                    best_priority = -Infinity
                    best = None
                    hits_per_tick = DISMANTLE_POWER * self.creep.getActiveBodypartsBoostEquivalent(WORK, 'dismantle')
                    for structure in structures.concat(sites):
                        stype = structure.structureType
                        if structure.my or stype == STRUCTURE_CONTROLLER or stype == STRUCTURE_PORTAL \
                                or (stype == STRUCTURE_EXTRACTOR and not structure.hits) \
                                or (structure.store and _.findKey(structure.store,
                                                                  lambda amount, key: amount > 100
                                                                  and (key != RESOURCE_ENERGY or amount > 10 * 1000))):
                            continue
                        distance = movement.chebyshev_distance_room_pos(self, structure)

                        priority = -distance
                        if stype == STRUCTURE_WALL or stype == STRUCTURE_RAMPART:
                            if structure.hits:
                                priority -= structure.hits / hits_per_tick
                        if structure.progressTotal:  # a construction site
                            priority -= 50
                        if stype == STRUCTURE_ROAD and distance > 1:
                            priority -= 500 * distance
                        if priority > best_priority:
                            best_priority = priority
                            best = structure
                    if best:
                        self.memory.dt = positions.serialize_pos_xy(best)  # dismantler target
                        if __pragma__('js', '(best instanceof ConstructionSite)'):
                            self.move_to(best)
                        elif not dismantled:
                            self.do_dismantle(best)
                        else:
                            self.move_to(best)
                    else:
                        self.remove_target(target)
                        return
            else:
                if self.memory.dt:  # dismantler target
                    target = positions.deserialize_xy_to_pos(self.memory.dt, target.pos.roomName)
                if 'checkpoint' not in self.memory or \
                                movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                    self.memory.checkpoint = self.pos
                if hostile_utils.enemy_owns_room(self.memory.checkpoint.roomName):
                    self.memory.checkpoint = self.home.spawn or movement.find_an_open_space(self.home.name)

                self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint), target)

        else:
            target = self.targets.get_new_target(self, target_single_flag2, TD_H_D_STOP)
            if not target:
                if len(flags.find_flags(self.home, RAID_OVER)):
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
                        self.recycle_me()
                else:
                    self.log("Dismantler has no healer target!")
                    self.go_to_depot()
                return
            if self.pos.roomName != target.pos.roomName:
                self.creep.moveTo(target)
            else:
                room = self.hive.get_room(target.pos.roomName)
                if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                    if not self.pos.isEqualTo(target):
                        self.creep.moveTo(target)
                        self.follow_military_path(self.home.spawn, target)
                else:
                    self.go_to_depot()

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, ATTACK_DISMANTLE)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class EnergyGrab(TransportPickup, EnergyHauler):
    def run(self):
        target = self.targets.get_new_target(self, target_single_flag, ENERGY_GRAB)
        if not target:
            if 'recycling_from' not in self.memory:
                target = self.memory.recycling_from = self.pos
            else:
                target = _.create(RoomPosition.prototype, self.memory.recycling_from)
            if not self.pos.isNearTo(self.home.spawn):
                return self.follow_energy_path(target, self.home.spawn)
            else:
                self.memory.last_role = self.memory.role
                self.memory.role = role_recycling
                return

        fill = self.home.room.storage or self.home.spawn

        if self.memory.filling and (
                        Game.time * 2 + self.creep.ticksToLive) % 5 and self.pos.roomName == target.pos.roomName:
            piles = self.room.look_at(LOOK_RESOURCES, target)
            if not len(piles) and not _.find(self.room.look_at(LOOK_STRUCTURES, target),
                                             lambda s: s.structureType == STRUCTURE_CONTAINER and s.store.energy):
                new_target = self.room.find_closest_by_range(FIND_STRUCTURES, target.pos,
                                                             lambda s: s.structureType == STRUCTURE_CONTAINER
                                                                       and s.store.energy)
                if not new_target:
                    new_target = self.room.find_closest_by_range(FIND_DROPPED_RESOURCES, target.pos)
                if new_target:
                    target.setPosition(new_target.pos)
                    return False
                else:
                    target.remove()
                    return False
        elif fill == self.home.spawn and not self.memory.filling:
            if self.pos.roomName == fill.pos.roomName:
                return self.run_local_refilling(target, fill)
            else:
                del self.memory.running

        return self.transport(target, fill)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, ENERGY_GRAB)
        if not target:
            return -1
        path_len = self.path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class PowerAttack(MilitaryBase):
    def run(self):
        if not self.memory.healing and self.creep.hits < \
                max(ATTACK_POWER * self.creep.getActiveBodyparts(ATTACK), self.creep.hitsMax / 2):
            self.memory.healing = True
            self.targets.untarget_all(self)
        if self.memory.healing and self.creep.hits >= self.creep.hitsMax:
            self.memory.healing = False
            self.targets.untarget_all(self)

        target = self.targets.get_new_target(self, target_single_flag, ATTACK_POWER_BANK)
        if not target:
            if len(flags.find_flags(self.home, RAID_OVER)):
                if self.creep.ticksToLive < 300:
                    self.creep.suicide()
                else:
                    self.recycle_me()
            else:
                self.log("PowerAttack has no target!")
                self.go_to_depot()
            return
        heal_target = self.targets.get_new_target(self, target_single_flag2, TD_H_D_STOP, target.pos)
        if self.memory.healing:
            if not heal_target:
                if len(flags.find_flags(self.home, RAID_OVER)):
                    if self.creep.ticksToLive < 300:
                        self.creep.suicide()
                    else:
                        self.memory.last_role = self.memory.role
                        self.memory.role = role_recycling
                else:
                    self.log("PowerAttack has no healer target!")
                    self.go_to_depot()
                return
            if self.pos.roomName != heal_target.pos.roomName:
                self.creep.moveTo(heal_target)
            else:
                room = self.hive.get_room(heal_target.pos.roomName)
                if room and _.find(room.find(FIND_MY_CREEPS), lambda c: c.memory.role == role_td_healer):
                    if not self.pos.isEqualTo(heal_target):
                        self.creep.moveTo(heal_target)
                        self.follow_military_path(self.home.spawn, heal_target)
                else:
                    self.go_to_depot()
        else:
            if self.pos.isNearTo(target):
                struct = self.room.look_at(LOOK_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.attack(struct)
                else:
                    for flag in flags.find_flags(self.room, TD_H_H_STOP):
                        flag.remove()
                    for flag in flags.find_flags(self.room, TD_H_D_STOP):
                        flag.remove()
                    target.remove()
            if not self.pos.isEqualTo(heal_target):
                if self.pos.roomName == target.pos.roomName:
                    result = self.creep.moveTo(heal_target)
                    if result != OK and result != ERR_TIRED:
                        self.log("Unknown result from creep.moveTo({}): {}".format(target, result))
                else:
                    self.follow_military_path(self.home.spawn, heal_target)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, ATTACK_POWER_BANK)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


# TODO: Change the speech on this to something unique.
class PowerCleanup(MilitaryBase):
    def should_pickup(self, resource_type=None):
        return resource_type is None or resource_type == RESOURCE_POWER

    def run(self):
        target = self.targets.get_new_target(self, target_single_flag, REAP_POWER_BANK)
        if not target:
            if len(flags.find_flags(self.home, RAID_OVER)) or self.creep.ticksToLive < 100:
                self.recycle_me()
            else:
                self.log("PowerAttack has no target!")
                self.go_to_depot()
            return
        if self.memory.filling and self.carry_sum() >= self.creep.carryCapacity:
            self.memory.filling = False

        if not self.memory.filling and self.carry_sum() <= 0:
            self.memory.filling = True

        storage = self.home.room.storage
        if self.memory.filling:
            if self.pos.roomName != target.pos.roomName:
                self.follow_military_path(self.home.spawn, target)
                return

            # TODO: Make some cached memory map of all hostile creeps, and use it to avoid.
            resources = self.room.find(FIND_DROPPED_RESOURCES)
            if len(resources):
                closest = None
                closest_distance = Infinity
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:

                        if self.memory.last_energy_target:
                            compressed_pos = resource.pos.x | (resource.pos.y << 6)
                            if compressed_pos == self.memory.last_energy_target:
                                closest = resource
                                break
                        if (resource.amount > 50 or
                                    len(self.room.find_in_range(FIND_SOURCES, 1, resource.pos)) == 0):

                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self, resource)
                            if distance < closest_distance:
                                closest = resource
                                closest_distance = distance
                pile = closest
            else:
                pile = None

            if not pile:
                del self.memory.last_energy_target
                if not _.find(self.room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_POWER_BANK}):
                    if self.carry_sum() >= 0:
                        self.memory.filling = False
                    else:
                        target.remove()
                else:
                    if self.pos.inRangeTo(target, 7):
                        self.move_around(target)
                    else:
                        self.move_to(target)
                return

            self.memory.last_energy_target = pile.pos.x | (pile.pos.y << 6)

            if not self.pos.isNearTo(pile):
                self.move_to(pile)
                return False

            result = self.creep.pickup(pile)

            if result == OK:
                pass
            elif result == ERR_FULL:
                self.memory.filling = False
                return True
            else:
                self.log("Unknown result from cleanup-creep.pickup({}): {}", pile, result)
        else:
            if not storage:
                self.go_to_depot()
                return

            if self.pos.roomName != storage.pos.roomName:
                self.follow_military_path(target, storage)
                return False

            target = storage
            if not self.pos.isNearTo(target):
                self.move_to(target)
                return False

            resource_type = _.find(Object.keys(self.creep.carry), lambda r: self.creep.carry[r] > 0)
            result = self.creep.transfer(target, resource_type)
            if result == OK:
                pass
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.filling = True
                return True
            elif result == ERR_FULL:
                if target == storage:
                    self.log("Storage in room {} full!", storage.room.name)
            else:
                self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource_type, result)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_single_flag, REAP_POWER_BANK)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10

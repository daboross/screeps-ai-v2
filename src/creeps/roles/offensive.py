from cache import global_cache
from constants import ATTACK_DISMANTLE, ATTACK_POWER_BANK, ENERGY_GRAB, RAID_OVER, REAP_POWER_BANK, TD_D_GOAD, \
    TD_H_D_STOP, TD_H_H_STOP, role_td_healer, target_single_flag, target_single_flag2
from creep_management import autoactions
from creeps.behaviors.military import MilitaryBase
from creeps.behaviors.transport import TransportPickup
from creeps.roles.mining import EnergyHauler
from jstools.screeps_constants import *
from position_management import flags
from utilities import hostile_utils, movement

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
                self.recycle_me()
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
            if len(flags.find_flags(self.home, RAID_OVER)):
                self.recycle_me()
            else:
                self.log("TowerDrainer has no target!")
                self.recycle_me()
            return
        if self.memory.goading:
            if self.pos.isEqualTo(goad_target):
                pass
            elif movement.chebyshev_distance_room_pos(self.pos, goad_target) < 50:
                self.creep.moveTo(goad_target, {
                    "costCallback": lambda room_name, matrix: self.hive.honey.set_max_avoid(
                        room_name, matrix, {'max_avoid': [goad_target.pos.roomName]}
                    )
                })
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
                self.creep.moveTo(heal_target, {  # TODO: make a military moveTo method like this
                    "costCallback": lambda room_name, matrix: self.hive.honey.set_max_avoid(
                        room_name, matrix, {'max_avoid': [goad_target.pos.roomName]}
                    )
                })
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
                        self.recycle_me()
                else:
                    self.log("Dismantler has no target!")
                    self.go_to_depot()
                return
            if self.pos.isNearTo(target):
                struct = self.room.look_at(LOOK_STRUCTURES, target.pos)[0]
                if struct:
                    self.creep.dismantle(struct)
                else:
                    site = self.room.look_at(LOOK_CONSTRUCTION_SITES, target.pos)[0]
                    if site:
                        self.basic_move_to(site)
                    else:
                        global_cache.clear_values_matching(target.pos.roomName + '_cost_matrix_')
                        if 'dismantle_all' not in target.memory or target.memory.dismantle_all:
                            new_target_site = self.room.find_closest_by_range(FIND_HOSTILE_CONSTRUCTION_SITES,
                                                                              target.pos)
                            new_structure = self.room.find_closest_by_range(
                                FIND_STRUCTURES, target.pos, lambda s: s.structureType != STRUCTURE_ROAD
                                                                       and s.structureType != STRUCTURE_CONTAINER
                                                                       and s.structureType != STRUCTURE_CONTROLLER
                                                                       and s.structureType != STRUCTURE_EXTRACTOR
                                                                       and s.structureType != STRUCTURE_STORAGE
                                                                       and s.structureType != STRUCTURE_TERMINAL)
                            if new_structure and (not new_target_site or
                                                          movement.distance_squared_room_pos(target, new_target_site)
                                                          > movement.distance_squared_room_pos(target, new_structure)):
                                new_pos = new_structure.pos
                            elif new_target_site:
                                new_pos = new_target_site.pos
                            else:
                                target.remove()
                                return
                            target.setPosition(new_pos)
                            self.move_to(new_pos)
                        else:
                            target.remove()
            else:
                if self.pos.roomName == target.pos.roomName:
                    self.move_to(target)
                else:
                    if 'checkpoint' not in self.memory or \
                                    movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                        self.memory.checkpoint = self.pos
                    if hostile_utils.enemy_room(self.memory.checkpoint.roomName):
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
                return self.recycle_me()

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
                        self.recycle_me()
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

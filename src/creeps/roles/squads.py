import math

from constants import role_recycling, target_single_flag
from creeps.base import RoleBase
from creeps.behaviors.military import MilitaryBase
from creeps.roles.smart_offensive import kiting_away_raw_path
from empire import honey, stored_data
from jstools import errorlog
from jstools.screeps import *
from position_management import locations
from rooms import defense
from utilities import hostile_utils, movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


class SquadInit(RoleBase):
    def run(self):
        target = self.target(target_single_flag)
        if not target:
            self.log("Squad init has no target! D:")
            self.memory.last_role = self.memory.role
            self.memory.role = role_recycling
            return

        self.home.squads.note_stage0_creep(self, target)
        self.home.squads.renew_or_depot(self)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self)
            if target:
                self.move_to(target)
                return

        RoleBase.go_to_depot(self)

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


class SquadFinalRenew(RoleBase):
    def run(self):
        self.home.squads.renew_or_depot(self)
        self.home.squads.note_stage1_creep(self, self.memory.squad)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self)
            if target:
                self.move_to(target)
                return

        RoleBase.go_to_depot(self)

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


class SquadFinalBoost(RoleBase):
    def run(self):
        self.home.squads.boost_or_depot(self)
        self.home.squads.note_stage2_creep(self, self.memory.squad)

    def go_to_depot(self):
        if self.findSpecialty() == ATTACK:
            target = self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self)
            if target:
                self.move_to(target)
                return

        RoleBase.go_to_depot(self)


class SquadDrone(MilitaryBase):
    def run(self):
        self.home.squads.note_stage3_creep(self, self.memory.squad)

    def run_squad(self, members, target):
        pass

    def find_target_here(self, target):
        return None

    def get_replacement_time(self):
        return Game.time + CREEP_LIFE_TIME * 2


def cost_of_wall_hits(hits):
    return int(math.ceil(20 * math.log(hits / (DISMANTLE_POWER * MAX_CREEP_SIZE / 2 * 40), 50)))


def dismantle_pathfinder_callback(room_name):
    room = Game.rooms[room_name]
    if room:
        plain_cost = 2
        matrix = honey.create_custom_cost_matrix(room_name, plain_cost, plain_cost * 5, 1, False)
        any_lairs = False
        for structure in room.find(FIND_STRUCTURES):
            structure_type = structure.structureType
            if structure_type == STRUCTURE_RAMPART and (structure.my or structure.isPublic):
                continue
            elif structure_type == STRUCTURE_ROAD:
                if matrix.get(structure.pos.x, structure.pos.y) == 0:
                    matrix.set(structure.pos.x, structure.pos.y, plain_cost)
                continue
            elif structure_type == STRUCTURE_CONTAINER:
                continue
            elif structure_type == STRUCTURE_KEEPER_LAIR:
                any_lairs = True
                matrix.set(structure.pos.x, structure.pos.y, 255)
            elif structure_type == STRUCTURE_SPAWN or structure_type == STRUCTURE_EXTENSION:
                for x in range(structure.pos.x - 1, structure.pos.x + 2):
                    for y in range(structure.pos.y - 1, structure.pos.y + 2):
                        existing = matrix.get_existing(x, y)
                        matrix.set(x, y, existing - 1)
            elif structure_type == STRUCTURE_TOWER:
                initial_x = structure.pos.x
                initial_y = structure.pos.y
                for x in range(initial_x - 10, initial_x + 10):
                    for y in range(initial_y - 10, initial_y + 10):
                        distance = movement.chebyshev_distance_xy(initial_x, initial_y, x, y)
                        if distance <= 5:
                            matrix.increase_at(x, y, None, 10 * plain_cost)
                        else:
                            matrix.increase_at(x, y, None, (10 - distance) * plain_cost)

            elif structure.hits:
                matrix.increase_at(structure.pos.x, structure.pos.y, None,
                                   cost_of_wall_hits(structure.hits) * plain_cost)
            else:
                matrix.set(structure.pos.x, structure.pos.y, 255)
        for site in room.find(FIND_MY_CONSTRUCTION_SITES):
            if site.structureType == STRUCTURE_RAMPART or site.structureType == STRUCTURE_ROAD \
                    or site.structureType == STRUCTURE_CONTAINER:
                continue
            matrix.set(site.pos.x, site.pos.y, 255)
        # Note: this depends on room being a regular Room, not a RoomMind, since RoomMind.find(FIND_HOSTILE_CREEPS)
        # excludes allies!
        if not room.controller or not room.controller.my or not room.controller.safeMode:
            for creep in room.find(FIND_HOSTILE_CREEPS):
                matrix.set(creep.pos.x, creep.pos.y, 255)
        if any_lairs:
            for source in room.find(FIND_SOURCES):
                for x in range(source.pos.x - 4, source.pos.x + 5):
                    for y in range(source.pos.y - 4, source.pos.y + 5):
                        matrix.set(x, y, 200)
            for mineral in room.find(FIND_MINERALS):
                for x in range(mineral.pos.x - 4, mineral.pos.x + 5):
                    for y in range(mineral.pos.y - 4, mineral.pos.y + 5):
                        matrix.set(x, y, 200)
        print('Dismantler cost matrix for {}:\nStart.\n{}\nEnd.'
              .format(room_name, matrix.visual()))
    else:
        matrix = __new__(PathFinder.CostMatrix())
        data = stored_data.get_data(room_name)
        if not data:
            return matrix
        for obstacle in data.obstacles:
            if obstacle.type == StoredObstacleType.ROAD:
                if matrix.get(obstacle.x, obstacle.y) == 0:
                    matrix.set(obstacle.x, obstacle.y, 1)
            else:
                if obstacle.type == StoredObstacleType.SOURCE_KEEPER_SOURCE \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_MINERAL:
                    for x in range(obstacle.x - 4, obstacle.x + 5):
                        for y in range(obstacle.y - 4, obstacle.y + 5):
                            matrix.set(x, y, 200)
                matrix.set(obstacle.x, obstacle.y, 255)
    return matrix


_dismantle_move_to_opts = {
    "maxRooms": 1,
    "maxOps": 4000,
    "reusePath": 100,
    "plainCost": 2,
    "swampCost": 10,
    "roomCallback": dismantle_pathfinder_callback,
}


def dismantle_condition_not_a_road(structure):
    return structure.structureType != STRUCTURE_ROAD and not structure.my


class SquadDismantle(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        path = _.get(self.memory, ['_move', 'path'])
        if path:
            next_pos = self.creep.findNextPathPos(path)
            if _.isObject(next_pos):
                best_structure = _.find(self.room.look_at(LOOK_STRUCTURES, next_pos), dismantle_condition_not_a_road)
                if best_structure:
                    result = self.creep.dismantle(best_structure)
                    if result != OK:
                        self.log("Unknown result from {}.dismantle({}): {}"
                                 .format(self.creep, best_structure, result))
                    return
            elif next_pos == ERR_NOT_FOUND:
                del self.memory['_move']
        if self.room.my:
            return
        structures_around = self.room.look_for_in_area_around(LOOK_STRUCTURES, self, 1)
        best_structure = None
        our_dismantle_power = DISMANTLE_POWER * self.creep.getActiveBodypartsBoostEquivalent(WORK, 'dismantle')
        if len(structures_around) > 1:
            ramparts_at = None
            for structure_obj in structures_around:
                if structure_obj.structure.structureType == STRUCTURE_RAMPART:
                    if ramparts_at is None:
                        ramparts_at = {}
                    ramparts_at[positions.serialize_pos_xy(structure_obj.structure)] = structure_obj.structure.hits
            best_rank = -Infinity
            for structure_obj in self.room.look_for_in_area_around(LOOK_STRUCTURES, self, 1):
                structure = structure_obj.structure
                if structure.my or structure_type == STRUCTURE_CONTROLLER or structure_type == STRUCTURE_PORTAL \
                        or (structure.store and _.findKey(structure.store,
                                                          lambda amount, key: amount > 5000
                                                          and (key != RESOURCE_ENERGY or amount > 100 * 1000))):
                    continue
                structure_type = structure.structureType
                if structure_type == STRUCTURE_TOWER:
                    rank = 55
                elif structure_type == STRUCTURE_SPAWN:
                    rank = 50
                elif structure_type == STRUCTURE_LAB:
                    rank = 45
                elif structure_type == STRUCTURE_EXTENSION:
                    rank = 40
                elif structure_type == STRUCTURE_LINK:
                    rank = 30
                else:
                    rank = 10
                rampart = ramparts_at and ramparts_at[positions.serialize_pos_xy(structure)]
                hits = structure.hits
                if rampart and rampart.hits:
                    hits += rampart.hits
                if hits < our_dismantle_power:
                    rank -= hits / our_dismantle_power
                if rank > best_rank:
                    best_rank = rank
                    best_structure = structure
        elif len(structures_around):
            best_structure = structures_around[0].structure
            if best_structure.my:
                return
        else:
            return

        result = self.creep.dismantle(best_structure)
        self._dismantled = best_structure
        if result == OK:
            if best_structure.hits < our_dismantle_power \
                    or best_structure.hits < our_dismantle_power + _.sum(
                        members, lambda x: x.creep.getActiveBodypartsBoostEquivalent(RANGED_ATTACK, 'rangedAttack')
                                * RANGED_ATTACK_POWER):
                del self.memory._move
        else:
            self.log("Unknown result from {}.dismantle({}): {}"
                     .format(self.creep, best_structure, result))

    def find_target_here(self, target):
        """
        :type target: position_management.locations.Location
        """
        if self.memory.tloctimeout > Game.time:
            pos = positions.deserialize_xy_to_pos(self.memory.tloc, target.roomName)
            if pos:
                if _.some(self.room.look_at(LOOK_STRUCTURES, pos), dismantle_condition_not_a_road):
                    return pos
        structure_target = _.find(self.room.look_at(LOOK_STRUCTURES, target), dismantle_condition_not_a_road)
        if structure_target:
            self.memory.tloc = positions.serialize_pos_xy(structure_target)
            self.memory.tloctimeout = Game.time + 50
            return structure_target.pos

        if self.pos.roomName != target.roomName:
            return None

        best_target = None
        best_rank = -Infinity
        enemy_structures = self.room.find(FIND_HOSTILE_STRUCTURES)
        for struct in enemy_structures:
            structure_type = struct.structureType
            if structure_type == STRUCTURE_SPAWN:
                rank = 50
            elif structure_type == STRUCTURE_LAB:
                rank = 40
            elif structure_type == STRUCTURE_TOWER:
                rank = 30
            elif structure_type == STRUCTURE_EXTENSION:
                rank = 20
            elif structure_type != STRUCTURE_RAMPART:
                rank = 10
            else:
                rank = 0
            rank -= movement.chebyshev_distance_room_pos(self, struct) / 20
            if structure_type != STRUCTURE_RAMPART:
                rampart = _.find(self.room.look_at(LOOK_STRUCTURES, struct), {'structureType': STRUCTURE_RAMPART})
                if rampart:
                    rank -= 10 * rampart.hits / (DISMANTLE_POWER * MAX_CREEP_SIZE / 2 * CREEP_LIFE_TIME * 0.9)
            if rank > best_rank:
                best_target = struct
                best_rank = rank

        if best_target:
            self.memory.tloc = positions.serialize_pos_xy(best_target)
            self.memory.tloctimeout = Game.time + 100
            return best_target.pos
        else:
            self.memory.tloc = positions.serialize_pos_xy(target)
            self.memory.tloctimeout = Game.time + 20
            return target

    def _move_options(self, target_room, opts):
        target = locations.get(self.memory.squad)
        if target and target.roomName == self.pos.roomName and target.roomName == target_room:
            return _dismantle_move_to_opts
        else:
            return SquadDrone._move_options(self, target_room, opts)

    def findSpecialty(self):
        return WORK


class SquadHeal(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        for to_check in members:
            if self.pos.isNearTo(to_check):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if to_check.creep.hits < to_check.creep.hitsMax:
                    rank += (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))

    def findSpecialty(self):
        return HEAL


class SquadTowerDrainHeal(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        most_damage = 0
        most_damaged = None
        for to_check in members:
            damage = (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
            if self.pos.isNearTo(to_check):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if damage:
                    rank += damage
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
            if damage > most_damage:
                most_damage = damage
                most_damaged = to_check
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))
        elif most_damaged:
            result = self.creep.rangedHeal(most_damaged.creep)
            if result != OK:
                self.log("Unknown result using {}.rangedHeal({}): {}"
                         .format(self.creep, most_damaged.creep, result))
        if not self.creep.__moved and most_damaged and not self.pos.isNearTo(most_damaged):
            self.move_to(most_damaged)

    def findSpecialty(self):
        return HEAL


class SquadRangedAttack(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        attacked = False
        here = self.room.find(FIND_HOSTILE_CREEPS)
        if len(here):
            directly_nearby = 0
            best = None
            best_range = Infinity
            best_rank = -Infinity
            for enemy in here:
                enemy_range = movement.chebyshev_distance_room_pos(enemy, self)
                if enemy_range <= 3:
                    specialty = enemy.findSpecialty()
                    if specialty == ATTACK or specialty == RANGED_ATTACK:
                        rank = 40
                    elif specialty == WORK:
                        rank = 35
                    else:
                        rank = 30
                    if _.some(self.room.look_at(LOOK_STRUCTURES, enemy),
                              lambda s: s.structureType == STRUCTURE_RAMPART and not s.my):
                        rank -= 20
                    rank += (enemy.hitsMax - enemy.hits) / enemy.hitsMax * 5
                    if enemy_range < 1:
                        directly_nearby += rank
                    if rank > best_rank:
                        best_rank = rank
                        best_range = enemy_range
                        best = enemy
            if directly_nearby > 65 or best_range <= 1:
                result = self.creep.rangedMassAttack()
                if result != OK:
                    self.log("Unknown result from {}.rangedMassAttack(): {}"
                             .format(self.creep, result))
                attacked = True
            elif best:
                result = self.creep.rangedAttack(best)
                if result != OK:
                    self.log("Unknown result from {}.rangedAttack({}): {}"
                             .format(self.creep, best, result))
                attacked = True
        if not attacked:
            dismantler = _.find(members, lambda x: isinstance(x, SquadDismantle))
            if dismantler and '_dismantled' in dismantler:
                self.creep.rangedAttack(dismantler['_dismantled'])

    def findSpecialty(self):
        return RANGED_ATTACK


class SquadAllAttack(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        if _.all(members, lambda x: x.pos.roomName == target.roomName):
            self.move_to(self.room.find_closest_by_range(FIND_HOSTILE_CREEPS, self))

    def findSpecialty(self):
        return ATTACK


_MOVE_TO_OPTIONS = {'reusePath': 1, 'useRoads': False}

# this is hardcoded in the screeps engine
# https://github.com/screeps/engine/blob/1a7175be293240aafa93e514c0487a82e5a383d8/src/processor/intents/creeps/rangedMassAttack.js#L30
#  var distanceRate = {1: 1, 2: 0.4, 3: 0.1};
ranged_mass_attack_rates = [1, 1, 0.4, 0.1]  # array for fast indexing


class SquadKitingRangedAttack(SquadDrone):
    def run_squad(self, members, target, do_things=False):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        :type do_things: bool
        """
        hostiles_nearby = defense.stored_hostiles_near(self.pos.roomName)
        if self.creep.hits < self.creep.hitsMax or \
                (len(hostiles_nearby)
                 and _.find(hostiles_nearby,
                            lambda h: movement.chebyshev_distance_room_pos(
                                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = target

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, lambda h: h.offensive and movement.chebyshev_distance_room_pos(
                    self.pos, positions.deserialize_xy_to_pos(h.pos, h.room) <= 5)):
                hostiles_nearby = _.filter(hostiles_nearby, 'offensive')
            nearby = _.filter(hostiles_nearby,
                              lambda h: movement.chebyshev_distance_room_pos(
                                  self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5)
            closest = _.min(
                hostiles_nearby,
                lambda h: movement.chebyshev_distance_room_pos(self.pos, positions.deserialize_xy_to_pos(h.pos, h.room))
                          - (5 if h.offensive else 0)
            )
            closest_pos = positions.deserialize_xy_to_pos(closest.pos, closest.room)
            harmless = not _.some(nearby, lambda x: x.attack or x.ranged)
            ranged = _.some(nearby, lambda x: x.ranged)
            only_ranged = not _.some(nearby,
                                     lambda h: movement.chebyshev_distance_room_pos(
                                         self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 4 and h.attack)
            mass_attack = _.some(nearby, lambda h: movement.chebyshev_distance_room_pos(
                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 1
                                                   and h.room == self.pos.roomName)
        else:
            enemies = self.room.find(FIND_HOSTILE_CREEPS)
            if len(enemies):
                if self.pos.roomName != marker_flag.roomName:
                    enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                          and hostile_utils.not_sk(h))
                else:
                    any_offensive = _.find(enemies, hostile_utils.is_offensive)
                    if any_offensive:
                        enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                              and hostile_utils.not_sk(h))
                    else:
                        enemies = _.filter(enemies, hostile_utils.not_sk)
            if len(enemies):
                closest = _.min(enemies, lambda h: movement.chebyshev_distance_room_pos(self.pos, h.pos))
                closest_pos = closest.pos
                nearby = _.filter(enemies, lambda h: movement.chebyshev_distance_room_pos(h, self.pos) <= 5)
                harmless = not _.some(nearby,
                                      lambda h: h.hasActiveBodyparts(ATTACK) or h.hasActiveBodyparts(RANGED_ATTACK)) \
                           and self.creep.hits >= self.creep.hitsMax
                ranged = _.some(nearby, lambda h: h.hasActiveBodyparts(RANGED_ATTACK))
                only_ranged = not _.some(nearby,
                                         lambda h:
                                         movement.chebyshev_distance_room_pos(self.pos, h.pos) <= 4
                                         and h.hasBodyparts(ATTACK))
                mass_attack = _.some(nearby, lambda h: self.pos.isNearTo(h.pos) and self.pos.roomName == h.pos.roomName)
            else:
                closest = None
                closest_pos = None
                nearby = []
                harmless = False
                ranged = False
                only_ranged = True
                mass_attack = False
        if not closest:
            if not do_things:
                return False
            self.move_to(target)
            return False
        closest_creep = Game.getObjectById(closest.id)
        min_distance = movement.chebyshev_distance_room_pos(closest_pos, self.pos)
        if Game.time % 2:
            self.creep.say("{},{}: {}".format(closest_pos.x, closest_pos.y, min_distance))
        else:
            self.creep.say("🐾 🏹 🐾", True)
        fatigue = (closest_creep and (closest_creep.fatigue or not closest_creep.hasActiveBodyparts(MOVE)))
        if self.memory.healing:
            self.memory.healing = self_damaged = self.creep.hits < self.creep.hitsMax
        else:
            # If 1/4 of our ranged attack parts are dead.
            total_ra = self.creep.getBodyparts(RANGED_ATTACK)
            alive_ra = self.creep.getActiveBodyparts(RANGED_ATTACK)
            self.memory.healing = self_damaged = (total_ra < 10 and alive_ra < total_ra / 2) or alive_ra < total_ra / 3

        if closest_pos.roomName == self.pos.roomName and min_distance <= 3:
            if mass_attack:
                self.creep.rangedMassAttack()
            else:
                closest_creep = Game.getObjectById(closest.id)
                self.creep.rangedAttack(closest_creep)

        if (min_distance <= 6) and self.pos.roomName != closest_pos.roomName:
            self.memory.countdown = (self.memory.countdown or 10) - 1
            if self.memory.countdown <= 0:
                if self.memory.countdown == 0:
                    self.memory.countdown -= 1
                if self.memory.countdown <= 5:
                    del self.memory.countdown
                self.move_to(marker_flag, _MOVE_TO_OPTIONS)
            return
        if ranged and self_damaged:
            safe_distance = 5
        elif ranged and only_ranged:
            safe_distance = 0
        else:
            safe_distance = 3
        should_run = (not _.some(self.pos.lookFor(LOOK_STRUCTURES), {'structureType': STRUCTURE_RAMPART, 'my': True})
                      and not harmless
                      and (min_distance < safe_distance or (min_distance == safe_distance and not fatigue)))

        should_approach = not should_run and (harmless or min_distance > safe_distance)
        if should_approach:
            moved = False
            if min_distance == 1 and len(nearby) > 1:
                # NOTE: expensive!!
                def rate_attack_pos(x, y):
                    summation = 0
                    for enemy in nearby:
                        if enemy.pos.x:
                            ex = enemy.pos.x
                            ey = enemy.pos.y
                        else:
                            ex, ey = positions.deserialize_xy(enemy.pos)
                        distance = movement.chebyshev_distance_xy(x, y, ex, ey)
                        summation += ranged_mass_attack_rates[distance] or 0
                    return summation * 10 + movement.chebyshev_distance_xy(x, y, self.pos.x, self.pos.y)

                best_attack_x = self.pos.x
                best_attack_y = self.pos.y
                best_attack_rate = rate_attack_pos(best_attack_x, best_attack_y)
                for xx in range(self.pos.x - 1, self.pos.x + 1):
                    for yy in range(self.pos.y - 1, self.pos.y + 1):
                        rate = rate_attack_pos(xx, yy)
                        if rate > best_attack_rate:
                            best_attack_x = xx
                            best_attack_y = yy
                            best_attack_rate = rate
                if best_attack_x != self.pos.x or best_attack_y != self.pos.y:
                    self.move_to(__new__(RoomPosition(best_attack_x, best_attack_y, self.pos.roomName)))
                    moved = True
            if not moved:
                # NOTE: this depends on our custom moveTo function not checking for instanceof RoomPosition
                self.move_to(closest_pos, _MOVE_TO_OPTIONS)
        elif should_run:
            kiting_path = errorlog.try_exec(
                'kiting-offense',
                kiting_away_raw_path,
                lambda pos: "Error calculating or moving by kiting path at pos {}.".format(pos),
                self.pos,
                [{
                     'pos': positions.deserialize_xy_to_pos(h.pos, h.room),
                     'range': 10,
                 } for h in hostiles_nearby]
            )
            if kiting_path is True:
                # errored
                self.creep.say("Err")
                self.go_to_depot()
            elif len(kiting_path):
                self.creep.move(self.pos.getDirectionTo(kiting_path[0]))
            else:
                self.log("WARNING: kiting offense has no path at position {}!".format(self.pos))
        return True
    def findSpecialty(self):
        return RANGED_ATTACK


class SquadKitingAttack(SquadDrone):
    def run_squad(self, members, target, do_things=False):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        :type do_things: bool
        """
        if not do_things:
            return
        hostiles_nearby = defense.stored_hostiles_near(self.pos.roomName)
        if self.creep.hits < self.creep.hitsMax or \
                (len(hostiles_nearby)
                 and _.find(hostiles_nearby,
                            lambda h: movement.chebyshev_distance_room_pos(
                                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 3)):
            self.creep.heal(self.creep)

        marker_flag = target

        if len(hostiles_nearby):
            if _.find(hostiles_nearby, lambda h: h.offensive and movement.chebyshev_distance_room_pos(
                    self.pos, positions.deserialize_xy_to_pos(h.pos, h.room) <= 5)):
                hostiles_nearby = _.filter(hostiles_nearby, 'offensive')
            nearby = _.filter(hostiles_nearby,
                              lambda h: movement.chebyshev_distance_room_pos(
                                  self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 5)
            closest = _.min(
                hostiles_nearby,
                lambda h: movement.chebyshev_distance_room_pos(self.pos, positions.deserialize_xy_to_pos(h.pos, h.room))
                          - (5 if h.offensive else 0)
            )
            closest_pos = positions.deserialize_xy_to_pos(closest.pos, closest.room)
            harmless = not _.some(nearby, lambda x: x.attack or x.ranged)
            ranged = _.some(nearby, lambda x: x.ranged)
            only_ranged = not _.some(nearby,
                                     lambda h: movement.chebyshev_distance_room_pos(
                                         self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 4 and h.attack)
            mass_attack = _.some(nearby, lambda h: movement.chebyshev_distance_room_pos(
                self.pos, positions.deserialize_xy_to_pos(h.pos, h.room)) <= 1
                                                   and h.room == self.pos.roomName)
        else:
            enemies = self.room.find(FIND_HOSTILE_CREEPS)
            if len(enemies):
                if self.pos.roomName != marker_flag.roomName:
                    enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                          and hostile_utils.not_sk(h))
                else:
                    any_offensive = _.find(enemies, hostile_utils.is_offensive)
                    if any_offensive:
                        enemies = _.filter(enemies, lambda h: hostile_utils.is_offensive(h)
                                                              and hostile_utils.not_sk(h))
                    else:
                        enemies = _.filter(enemies, hostile_utils.not_sk)
            if len(enemies):
                closest = _.min(enemies, lambda h: movement.chebyshev_distance_room_pos(self.pos, h.pos))
                closest_pos = closest.pos
                nearby = _.filter(enemies, lambda h: movement.chebyshev_distance_room_pos(h, self.pos) <= 5)
                harmless = not _.some(nearby,
                                      lambda h: h.hasActiveBodyparts(ATTACK) or h.hasActiveBodyparts(RANGED_ATTACK)) \
                           and self.creep.hits >= self.creep.hitsMax
                ranged = _.some(nearby, lambda h: h.hasActiveBodyparts(RANGED_ATTACK))
                only_ranged = not _.some(nearby,
                                         lambda h:
                                         movement.chebyshev_distance_room_pos(self.pos, h.pos) <= 4
                                         and h.hasBodyparts(ATTACK))
                mass_attack = _.some(nearby, lambda h: self.pos.isNearTo(h.pos) and self.pos.roomName == h.pos.roomName)
            else:
                closest = None
                closest_pos = None
                nearby = []
                harmless = False
                ranged = False
                only_ranged = True
                mass_attack = False
        if not closest:
            self.move_to(target)
            return
        closest_creep = Game.getObjectById(closest.id)
        min_distance = movement.chebyshev_distance_room_pos(closest_pos, self.pos)
        if Game.time % 2:
            self.creep.say("{},{}: {}".format(closest_pos.x, closest_pos.y, min_distance))
        else:
            self.creep.say("🏹", True)
        fatigue = (closest_creep and (closest_creep.fatigue or not closest_creep.hasActiveBodyparts(MOVE)))
        if self.memory.healing:
            self.memory.healing = self_damaged = self.creep.hits < self.creep.hitsMax
        else:
            # If 1/4 of our ranged attack parts are dead.
            total_ra = self.creep.getBodyparts(ATTACK)
            alive_ra = self.creep.getActiveBodyparts(ATTACK)
            self.memory.healing = self_damaged = (total_ra < 10 and alive_ra < total_ra / 2) or alive_ra < total_ra / 3

        if closest_pos.roomName == self.pos.roomName and min_distance <= 1:
            closest_creep = Game.getObjectById(closest.id)
            self.creep.attack(closest_creep)

        if (min_distance <= 6) and self.pos.roomName != closest_pos.roomName:
            self.memory.countdown = (self.memory.countdown or 10) - 1
            if self.memory.countdown <= 0:
                if self.memory.countdown == 0:
                    self.memory.countdown -= 1
                if self.memory.countdown <= 5:
                    del self.memory.countdown
                self.move_to(marker_flag, _MOVE_TO_OPTIONS)
            return
        if ranged and self_damaged:
            safe_distance = 5
        elif ranged and only_ranged:
            safe_distance = 0
        elif self_damaged:
            safe_distance = 3
        else:
            safe_distance = 0
        should_run = (not _.some(self.pos.lookFor(LOOK_STRUCTURES), {'structureType': STRUCTURE_RAMPART, 'my': True})
                      and not harmless
                      and (min_distance < safe_distance or (min_distance == safe_distance and not fatigue)))

        should_approach = not should_run and (harmless or min_distance > safe_distance)
        if should_approach:
            # NOTE: this depends on our custom moveTo function not checking for instanceof RoomPosition
            self.move_to(closest_pos, _MOVE_TO_OPTIONS)
        elif should_run:
            kiting_path = errorlog.try_exec(
                'kiting-offense',
                kiting_away_raw_path,
                lambda pos: "Error calculating or moving by kiting path at pos {}.".format(pos),
                self.pos,
                [{
                     'pos': positions.deserialize_xy_to_pos(h.pos, h.room),
                     'range': 10,
                 } for h in hostiles_nearby]
            )
            if kiting_path is True:
                # errored
                self.creep.say("Err")
                self.go_to_depot()
            elif len(kiting_path):
                self.creep.move(self.pos.getDirectionTo(kiting_path[0]))
            else:
                self.log("WARNING: kiting offense has no path at position {}!".format(self.pos))

    def findSpecialty(self):
        return RANGED_ATTACK


class SquadDirectSupportHeal(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        best_near_rank = -Infinity
        best_near = None
        best_damaged_rank = -Infinity
        best_damaged_near = None
        most_damage = 0
        most_damaged = None
        for to_check in members:
            damage = (to_check.creep.hitsMax - to_check.creep.hits) / to_check.creep.hitsMax
            if self.pos.isNearTo(to_check):
                specialty = to_check.findSpecialty()
                if specialty == HEAL and to_check.creep.hits < to_check.creep.hitsMax * 0.7:
                    rank = 7
                elif specialty == RANGED_ATTACK or specialty == ATTACK or specialty == WORK:
                    rank = 5
                else:
                    rank = 1
                if damage:
                    rank += damage
                    if best_damaged_rank < rank:
                        best_damaged_near = to_check
                        best_damaged_rank = rank
                if best_near_rank < rank:
                    best_near = to_check
                    best_near_rank = rank
            if damage > most_damage:
                most_damage = damage
                most_damaged = to_check
        if best_damaged_near:
            result = self.creep.heal(best_damaged_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_damaged_rank.creep, result))
        elif best_near:
            result = self.creep.heal(best_near.creep)
            if result != OK:
                self.log("Unknown result using {}.heal({}): {}"
                         .format(self.creep, best_near.creep, result))
        elif most_damaged:
            result = self.creep.rangedHeal(most_damaged.creep)
            if result != OK:
                self.log("Unknown result using {}.rangedHeal({}): {}"
                         .format(self.creep, most_damaged.creep, result))
        if not self.creep.__moved:
            if most_damaged and not self.pos.isNearTo(most_damaged):
                self.move_to(most_damaged)

    def findSpecialty(self):
        return HEAL

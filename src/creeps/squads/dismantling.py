import math

from constants import SQUAD_DISMANTLE_RANGED, rmem_key_dismantler_squad_opts, role_squad_dismantle, role_squad_heal, \
    role_squad_ranged
from creeps.roles.squads import SquadDrone
from creeps.squads.base import BasicOffenseSquad
from empire import honey, stored_data
from jstools.screeps import *
from position_management import flags, locations
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

specialty_order = [ATTACK, WORK, HEAL, RANGED_ATTACK]


def drone_role(specialty):
    if specialty == WORK:
        return role_squad_dismantle
    elif specialty == RANGED_ATTACK:
        return role_squad_ranged
    elif specialty == HEAL:
        return role_squad_heal


class DismantleSquad(BasicOffenseSquad):
    def calculate_movement_order(self):
        initial = _.sortByAll(self.members, lambda x: specialty_order.index(x.findSpecialty()), 'name')

        # if len(initial) == 4:
        #     ranged_index = _.findIndex(initial, lambda x: x.findSpecialty() == RANGED_ATTACK)
        #     if ranged_index == len(initial) - 1:
        #         temp = initial[len(initial) - 2]
        #         initial[len(initial) - 2] = initial[ranged_index]
        #         initial[ranged_index] = temp

        return initial

    # def move_to_stage_2(self, target):
    #     """
    #     :type target: position_management.locations.Location | RoomPosition
    #     """
    #     dismantler = None
    #     ranged = None
    #     healers = []
    #     for creep in self.members:
    #         specialty = creep.findSpecialty()
    #         if specialty == WORK:
    #             if dismantler is not None:
    #                 self.log("multiple dismantlers found! {} and {}: delegating to default stage 2 movement",
    #                          dismantler, creep)
    #                 return BasicOffenseSquad.move_to_stage_2(self, target)
    #             dismantler = creep
    #         elif specialty == RANGED_ATTACK:
    #             if ranged is not None:
    #                 self.log("multiple rangers found! {} and {}: delegating to default stage 2 movement",
    #                          ranged, creep)
    #                 return BasicOffenseSquad.move_to_stage_2(self, target)
    #             ranged = creep
    #         elif specialty == HEAL:
    #             healers.append(creep)
    #         else:
    #             self.log("unknown specialty creep in dismantling squad: {} ({})",
    #                      specialty, creep)
    #
    #     if dismantler is None or not len(healers):
    #         return BasicOffenseSquad.move_to_stage_2(self, target)
    #     if len(healers) > 2:
    #         return BasicOffenseSquad.move_to_stage_2(self, target)
    #     self.log("Dismantler squad moving - stage 2 - d:{}, r:{}, h:{}",
    #              dismantler.name, ranged.name if ranged else "None", _.pluck(healers, 'name'))
    #
    #     BasicOffenseSquad.move_to_stage_2(self, target)

    def is_heavily_armed(self):
        return True


def cost_of_wall_hits(hits):
    return int(math.ceil(20 * math.log(hits / (DISMANTLE_POWER * MAX_CREEP_SIZE / 2 * 40), 50)))


def is_saveable_amount(amount, resource):
    return amount > 5000 and (resource != RESOURCE_ENERGY or amount > 100 * 1000)


def can_target_struct(structure, opts):
    if '__valid_dismantle_target' not in structure:
        structure_type = structure.structureType
        invalid = (
            structure.my
            or structure_type == STRUCTURE_CONTROLLER
            or structure_type == STRUCTURE_PORTAL
            or (
                structure.store
                and _.findKey(structure.store, is_saveable_amount)
            )
            or (
                opts['just_vitals']
                and structure_type != STRUCTURE_SPAWN
                and structure_type != STRUCTURE_NUKER
                and structure_type != STRUCTURE_TOWER
                and structure_type != STRUCTURE_RAMPART
                and structure_type != STRUCTURE_POWER_SPAWN
                and structure_type != STRUCTURE_OBSERVER
            )
        )
        structure['__valid_dismantle_target'] = not invalid
    return structure['__valid_dismantle_target']


def get_opts(room_name):
    if room_name in Memory.rooms:
        room_mem = Memory.rooms[room_name]
        if rmem_key_dismantler_squad_opts in room_mem:
            return room_mem[rmem_key_dismantler_squad_opts]

    return {'just_vitals': True}


def dismantle_pathfinder_callback(room_name):
    room = Game.rooms[room_name]
    if room:
        opts = get_opts(room_name)
        plain_cost = 1
        matrix = honey.create_custom_cost_matrix(room_name, plain_cost, plain_cost * 5, 1, False)
        any_lairs = False
        for structure in room.find(FIND_STRUCTURES):
            structure_type = structure.structureType
            if structure_type == STRUCTURE_RAMPART and (structure.my or structure.isPublic):
                continue
            elif structure_type == STRUCTURE_ROAD:
                continue
            elif not can_target_struct(structure, opts):
                matrix.set(structure.pos.x, structure.pos.y, 255)
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
            elif structure_type == STRUCTURE_TOWER and structure.energy:
                initial_x = structure.pos.x
                initial_y = structure.pos.y
                for x in range(initial_x - 10, initial_x + 10):
                    for y in range(initial_y - 10, initial_y + 10):
                        distance = movement.chebyshev_distance_xy(initial_x, initial_y, x, y)
                        if distance <= 5:
                            matrix.increase_at(x, y, None, 20 * plain_cost)
                        else:
                            matrix.increase_at(x, y, None, (25 - distance) * plain_cost)
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
        print('Dismantler cost matrix for {}:\nStart.\n{}\nEnd.'.format(room_name, matrix.visual()))
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
    return matrix.cost_matrix


_dismantle_move_to_opts = {
    "maxRooms": 1,
    "maxOps": 4000,
    "reusePath": 100,
    "plainCost": 1,
    "swampCost": 5,
    "roomCallback": dismantle_pathfinder_callback,
}


def get_dismantle_condition_not_a_road(opts):
    return lambda structure: structure.structureType != STRUCTURE_ROAD and can_target_struct(structure, opts)


def creep_condition_enemy(creep):
    return not creep.my and not Memory.meta.friends.includes(creep.owner.username.lower())


class SquadDismantle(SquadDrone):
    def run_squad(self, members, target):
        """
        :type members: list[SquadDrone]
        :type target: position_management.locations.Location
        """
        if movement.chebyshev_distance_room_pos(self, target) > 150:
            return
        opts = get_opts(self.pos.roomName)
        self.log("running with opts {}", JSON.stringify(opts))
        owner = stored_data._find_room_owner(self.room.room)
        if (owner and (Memory.meta.friends.includes(owner.name.lower())
                       or owner.name == self.creep.owner.username)):
            return

        next_pos = None

        path = _.get(self.memory, ['_move', 'path'])
        if path:
            next_pos = self.creep.findNextPathPos(path)
            if not _.isObject(next_pos) or not self.pos.isNearTo(next_pos):
                next_pos = None

        if next_pos is None and self.creep.__direction_moved:
            next_pos = movement.apply_direction(self.pos, self.creep.__direction_moved)

        if next_pos is not None:
            best_structure = _.find(self.room.look_at(LOOK_STRUCTURES, next_pos),
                                    get_dismantle_condition_not_a_road(opts))
            if best_structure:
                result = self.creep.dismantle(best_structure)
                if result != OK:
                    self.log("Unknown result from {}.dismantle({}): {}", self.creep, best_structure, result)
                if result != ERR_NOT_IN_RANGE:
                    return
        elif next_pos == ERR_NOT_FOUND:
            del self.memory['_move']
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
                if not can_target_struct(structure, opts):
                    continue
                if structure.my or structure_type == STRUCTURE_CONTROLLER or structure_type == STRUCTURE_PORTAL \
                        or (structure.store and _.findKey(structure.store,
                                                          lambda amount, key: amount > 5000
                                                          and (key != RESOURCE_ENERGY or amount > 100 * 1000))):
                    print("WARNING WARNING WARNING second clause hit for {}".format(structure))
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

                hits = structure.hits

                if structure_type != STRUCTURE_RAMPART and ramparts_at:
                    rampart = ramparts_at[positions.serialize_pos_xy(structure)]
                    if rampart and rampart.hits:
                        hits += rampart.hits

                if hits < our_dismantle_power:
                    rank -= hits / our_dismantle_power
                if rank > best_rank:
                    best_rank = rank
                    best_structure = structure
        elif len(structures_around):
            best_structure = structures_around[0].structure
            if not can_target_struct(best_structure, opts):
                return
        else:
            return

        if best_structure:
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
        opts = get_opts(self.pos.roomName)
        if self.memory.tloctimeout > Game.time:
            pos = positions.deserialize_xy_to_pos(self.memory.tloc, target.roomName)
            if pos:
                if _.some(self.room.look_at(LOOK_STRUCTURES, pos), get_dismantle_condition_not_a_road(opts)):
                    return pos
        structure_target = _.find(self.room.look_at(LOOK_STRUCTURES, target), get_dismantle_condition_not_a_road(opts))
        if structure_target:
            self.memory.tloc = positions.serialize_pos_xy(structure_target)
            self.memory.tloctimeout = Game.time + 50
            return structure_target.pos

        if self.pos.roomName != target.roomName:
            return None

        best_target = None
        best_rank = -Infinity
        enemy_structures = self.room.find(FIND_HOSTILE_STRUCTURES)
        opts = get_opts(self.pos.roomName)
        for struct in enemy_structures:
            structure_type = struct.structureType
            if not can_target_struct(struct, opts):
                continue
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
            if self.pos.isNearTo(target):
                flag = _.find(flags.look_for(self.room, target, SQUAD_DISMANTLE_RANGED))
                if flag:
                    msg = "[dismantle squad][{}][{}] Dismantle job in {} completed at {}! Removing flag {} ({})." \
                        .format(self.home.name, self.name, self.pos.roomName, Game.time, flag, flag.pos)
                    self.log(msg)
                    Game.notify(msg)
                    flag.remove()
            self.memory.tloc = positions.serialize_pos_xy(target)
            self.memory.tloctimeout = Game.time + 20
            return target

    def _move_options(self, target_room, opts):
        target = locations.get(self.memory.squad)
        if target and target.roomName == self.pos.roomName and target.roomName == target_room:
            self.log("using dismantler callback for {}", target_room)
            return _dismantle_move_to_opts
        else:
            return SquadDrone._move_options(self, target_room, opts)

    def findSpecialty(self):
        return WORK

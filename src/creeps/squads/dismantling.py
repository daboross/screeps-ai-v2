import math
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Tuple, Union, cast

from constants import SQUAD_DISMANTLE_RANGED, rmem_key_dismantler_squad_opts, role_squad_dismantle, role_squad_heal, \
    role_squad_ranged
from creeps.roles.squads import SquadDrone
from creeps.squads.base import BasicOffenseSquad, squadmemkey_origin
from empire import honey, stored_data
from jstools.screeps import *
from position_management import flags, locations
from utilities import movement, positions, robjs

if TYPE_CHECKING:
    from position_management.locations import Location

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

specialty_order = [ATTACK, WORK, HEAL, RANGED_ATTACK]


def drone_role(specialty):
    # type: (str) -> str
    if specialty == WORK:
        return role_squad_dismantle
    elif specialty == RANGED_ATTACK:
        return role_squad_ranged
    elif specialty == HEAL:
        return role_squad_heal


dismemkey_gathered = "g"
dismemkey_ordered = "d"
dismemkey_regrouping = "t"


class DismantleSquad(BasicOffenseSquad):
    def calculate_movement_order(self):
        return _.sortByAll(self.members, lambda x: specialty_order.index(x.findSpecialty()), 'name')

    def move_to_stage_0(self, target):
        # type: (RoomPosition) -> None
        self.new_move(target)

    def move_to_stage_1(self, target, any_hostiles):
        # type: (RoomPosition, bool) -> None
        self.new_move(target)

    def move_to_stage_2(self, target):
        # type: (RoomPosition) -> None
        self.new_move(target)

    def move_to(self, target):
        # type: (RoomPosition) -> None
        self.new_move(target)

    def new_move(self, target):
        # type: (RoomPosition) -> None
        if not self.mem[dismemkey_gathered]:
            self.initial_gathering(target)
            return
        self.move_together(target)

    def initial_gathering(self, target):
        # type: (RoomPosition) -> None
        origin = self.find_home()
        if not self.mem[squadmemkey_origin]:
            self.set_origin(origin)
        serialized_obj = self.home.hive.honey.get_serialized_path_obj(origin, target, self.new_movement_opts())
        ordered_rooms_in_path = honey.get_room_list_from_serialized_obj(serialized_obj)

        second_from_home = ordered_rooms_in_path[1]
        path = Room.deserializePath(serialized_obj[second_from_home])
        halfway = path[int(len(path) / 2)]
        meet_at = __new__(RoomPosition(halfway.x, halfway.y, second_from_home))

        anyone_near = []
        for member in self.members:
            if member.pos.inRangeTo(meet_at, 3):
                anyone_near.append(member)

        if len(anyone_near) != len(self.members):
            for creep in self.members:
                creep.move_to(meet_at)
        else:
            self.mem[dismemkey_gathered] = True

    def target_exit_positions(self, current_room, next_room):
        # type: (str, str) -> str
        saved = self.mem['_texit']
        enemies_this_room = None
        if saved and Game.time < saved['e'] and None:
            pass
        return ''

    def move_to_exit(self, dismantle, attack, heal, exit_positions):
        # type: (List[SquadDrone], List[SquadDrone], List[SquadDrone], str) -> List[SquadDrone]
        robjs.get_str_codepoint(exit_positions, 0)
        return []

    def move_together(self, target):
        # type: (RoomPosition) -> None
        origin = self.find_home()
        serialized_obj = self.home.hive.honey.get_serialized_path_obj(origin, target, self.new_movement_opts())
        ordered_rooms_in_path = honey.get_room_list_from_serialized_obj(serialized_obj)

        dismantle = []
        attack = []
        heal = []
        for creep in self.members:
            specialty = creep.findSpecialty()
            if specialty == WORK:
                dismantle.append(creep)
            elif specialty == RANGED_ATTACK:
                attack.append(creep)
            elif specialty == HEAL:
                heal.append(creep)
            else:
                self.log("unknown specialty creep in dismantling squad: {} ({}). treating as ranged.",
                         specialty, creep)
                attack.append(creep)

        if not len(dismantle):
            self.log("dismantle squad has no dismantle creeps!")
        elif not len(heal):
            self.log("dismantle squad has no healers!")

        dismantle = _.sortBy(dismantle, 'name')
        heal = _.sortBy(heal, 'name')
        attack = _.sortBy(attack, 'name')
        groups = []
        if len(dismantle):
            groups.append(dismantle)
        if len(heal):
            groups.append(heal)
        if len(attack):
            groups.append(attack)

        self.log("dismantler squad moving: {}",
                 "<-".join(["[{}]".format(_.pluck(g, 'name')) for g in groups]))

        memory = self.mem

        if not memory[dismemkey_ordered]:
            self.log("ordering")
            ordered_now, repath = self.get_ordered(target, serialized_obj, dismantle, heal, attack)
            if not ordered_now:
                return

        current_room = groups[0][0].pos.roomName
        if self.mem[dismemkey_regrouping]:
            self.log("regrouping")
            if self.regroup(target, groups, ordered_rooms_in_path):
                return
            else:
                # TODO: don't require this! we shouldn't be relying on the main path except for the rooms,
                # and for the first reordering outside of base.
                del self.mem[dismemkey_ordered]
        elif _.any(self.members, lambda c: c.pos.roomName != current_room):
            self.log("enabling regrouping - not in same room.")
            self.mem[dismemkey_regrouping] = True
            self.regroup(target, groups, ordered_rooms_in_path)
            return

        grouped = [groups[0][0]]
        ungrouped = _.clone(self.members)
        iterations = len(ungrouped) ** 2
        for _i in range(0, iterations):
            index = 0
            while index < len(ungrouped):
                this_creep = ungrouped[index]
                any_matched = False
                for creep in grouped:
                    if this_creep.pos.isNearTo(creep):
                        any_matched = True
                        break
                if any_matched:
                    grouped.append(this_creep)
                    ungrouped.splice(this_creep, 1)
                else:
                    index += 1
        if len(ungrouped):
            self.log("enabling regrouping - in same room, but not together.")
            self.mem[dismemkey_regrouping] = True
            if not self.regroup(target, groups, ordered_rooms_in_path):
                self.log("warning: tried to stop regrouping immediately after choosing to regroup.")
            return

        if _.any(self.members, 'fatigue'):
            self.log('fatigue')
            return

        next_room = None  # type: Optional[str] # TODO: this

        exit_positions = self.target_exit_positions(current_room, next_room)

        return BasicOffenseSquad.move_to_stage_2(self, target)

    def regroup(self, target, groups, ordered_rooms_in_path):
        # type: (RoomPosition, List[List[SquadDrone]], List[str]) -> bool
        current_room = groups[0][0].pos.roomName
        room_index = robjs.rindex_list(ordered_rooms_in_path, current_room)
        last_room = ordered_rooms_in_path[room_index - 1]
        next_room = ordered_rooms_in_path[room_index + 1]
        gather_at_x = groups[0][0].pos.x
        gather_at_y = groups[0][0].pos.y
        extra_condition = None
        if next_room:
            if last_room:
                min_x = 1
                min_y = 1
                max_x = 48
                max_y = 48
                room_x_diff, room_y_diff = movement.room_diff(last_room, current_room)
                if abs(room_x_diff) > 1 or abs(room_y_diff) > 1:
                    portals = Game.rooms[current_room].find(FIND_STRUCTURES, {
                        'filter': {'structureType': STRUCTURE_PORTAL}
                    })

                    def portal_condition(x, y):
                        return not _.any(portals, lambda p: (abs(p.pos.x - x) < 5
                                                             or abs(p.pos.y - y) < 5))

                    extra_condition = portal_condition
                    self.log(".. through a portal")
                else:
                    if room_x_diff > 0:
                        min_x = 6
                    elif room_x_diff < 0:
                        max_x = 44
                    if room_y_diff > 0:
                        min_y = 6
                    elif room_y_diff < 0:
                        max_y = 44
            else:
                min_x = 6
                max_x = 44
                min_y = 6
                max_y = 44

            if gather_at_x < min_x or gather_at_x > max_x or gather_at_y < min_y or gather_at_y > max_y \
                    or (extra_condition and not extra_condition(gather_at_x, gather_at_y)):
                open_space = movement.find_an_open_space_around(current_room, gather_at_x, gather_at_y,
                                                                min_x, min_y, max_x, max_y, extra_condition)
                gather_at_x = open_space.x
                gather_at_y = open_space.y
            target_itself = False
        else:
            gather_at_x = target.x
            gather_at_y = target.y
            current_room = target.roomName
            min_x = 0
            max_x = 50
            min_y = 0
            max_y = 50
            target_itself = True

        pos = __new__(RoomPosition(gather_at_x, gather_at_y, current_room))
        last_group_gathered = True

        self.log('.. at {} (conditions: [{}-{},{}-{}])', pos, min_x, max_x, min_y, max_y)

        def move_to_closest_of(c, targets):
            # type: (SquadDrone, List[Union[RoomPosition, RoomObject, SquadDrone]]) -> bool
            target = None
            distance = Infinity
            for test_target in targets:
                test_distance = movement.chebyshev_distance_room_pos(c.pos, robjs.pos(test_target))
                if test_distance < distance:
                    distance = test_distance
                    target = test_target

            target = robjs.pos(target)
            if c.pos.roomName == target.roomName:
                if c.pos.isNearTo(target):
                    return False
                else:
                    c.move_to(target)
                    return True
            elif movement.chebyshev_distance_room_pos(c.pos, target) < 100:
                c.move_to(target)
                return True
            else:
                if 'reroute' in Game.flags and 'reroute_destination' in Game.flags:
                    reroute_start = Game.flags['reroute'].pos
                    reroute_destination = Game.flags['reroute_destination'].pos
                    if movement.chebyshev_distance_room_pos(c.pos, reroute_start) \
                            + movement.chebyshev_distance_room_pos(reroute_destination, target) \
                            < movement.chebyshev_distance_room_pos(c.pos, target):
                        target = reroute_start
                c.move_to(target)
                return True

        for creep in groups[0]:
            if move_to_closest_of(creep, [pos]):
                self.log(".. breaking in group 0")
                last_group_gathered = False
        for index in range(1, len(groups)):
            last_group = groups[index - 1]
            this_group = groups[index]
            if last_group_gathered:
                for in_group_index in range(0, len(this_group)):
                    to_test = last_group
                    this_creep = this_group[in_group_index]
                    # if in_group_index == 0:
                    #     to_test = last_group
                    # else:
                    #     last_creep = this_group[in_group_index - 1]
                    #     to_test = [last_creep]
                    #     to_test.extend(last_group)
                    if move_to_closest_of(this_creep, to_test):
                        last_group_gathered = False
                        self.log(".. breaking in group {}", index)
            else:
                for this_creep in groups[index]:
                    if target_itself:
                        move_to_closest_of(this_creep, last_group)
                    else:
                        move_to_closest_of(this_creep, [pos])
        if last_group_gathered:
            del self.mem[dismemkey_regrouping]
            return False
        else:
            return True

    def get_ordered(self,
                    target: RoomPosition,
                    serialized_obj: Dict[str, str],
                    dismantle: List[SquadDismantle],
                    heal: List[SquadDrone],
                    attack: List[SquadDrone],
                    already_repathed: bool = False) -> Tuple[bool, bool]:
        rebuilt = robjs.concat_lists(dismantle, heal, attack)
        first_creep = rebuilt[0]

        serialized_path_this_room = serialized_obj[first_creep.pos.roomName]
        if serialized_path_this_room:
            path_this_room = Room.deserializePath(serialized_path_this_room)
            total_positions_this_room = len(path_this_room)
        else:
            total_positions_this_room = 0
            path_this_room = None
        if path_this_room is not None and total_positions_this_room >= len(self.members) + 4:
            if total_positions_this_room >= len(self.members) * 2 + 4:
                first_index = int(len(path_this_room) / 2)
            else:
                first_index = len(path_this_room) - 2
            any_off = False
            for index in range(0, len(rebuilt)):
                pos = path_this_room[first_index - index]
                creep = rebuilt[index]
                pos = __new__(RoomPosition(pos.x, pos.y, first_creep.pos.roomName))
                if creep.pos.isEqualTo(pos):
                    continue
                else:
                    any_off = True
                    creep.move_to(pos)
            if not any_off:
                self.mem[dismemkey_ordered] = True
                return True, already_repathed
        else:
            next_intermediate_goal = target
            origin = _.max(self.members,
                           lambda m: movement.chebyshev_distance_room_pos(m.pos, next_intermediate_goal)).pos
            if 'reroute' in Game.flags and 'reroute_destination' in Game.flags:
                reroute_start = Game.flags['reroute'].pos
                reroute_destination = Game.flags['reroute_destination'].pos
                if movement.chebyshev_distance_room_pos(origin, reroute_start) \
                        + movement.chebyshev_distance_room_pos(reroute_destination, target) \
                        < movement.chebyshev_distance_room_pos(origin, target):
                    next_intermediate_goal = reroute_start
                    origin = _.max(self.members,
                                   lambda m: movement.chebyshev_distance_room_pos(m, next_intermediate_goal))
            self.set_origin(origin)
            serialized_obj = self.home.hive.honey.get_serialized_path_obj(origin, target, self.new_movement_opts())
            if not serialized_obj[first_creep.pos.roomName]:
                self.log("Uh-oh - path from furthest creep to target did not include the room the first creep is in."
                         " Setting origin to first creep's pos.")
                self.set_origin(first_creep.pos)
                serialized_obj = self.home.hive.honey.get_serialized_path_obj(origin, target, self.new_movement_opts())
                if not serialized_obj[first_creep.pos.roomName]:
                    self.log("Path from first creep {} to {} did not include room {}! ...",
                             first_creep.pos, target, first_creep.pos.roomName)
                    return False, False
                return self.get_ordered(target, serialized_obj, dismantle, heal, attack, True)
        return False, already_repathed

    def is_heavily_armed(self):
        return True


def cost_of_wall_hits(hits):
    # type: (int) -> int
    return int(math.ceil(20 * math.log(hits / (DISMANTLE_POWER * MAX_CREEP_SIZE / 2 * 40), 50)))


def is_saveable_amount(amount, resource):
    # type: (int, str) -> bool
    return amount > 5000 and (resource != RESOURCE_ENERGY or amount > 100 * 1000)


def can_target_struct(structure, opts):
    # type: (Structure, Dict[str, bool]) -> bool
    if '__valid_dismantle_target' not in cast(Any, structure):
        structure_type = structure.structureType
        invalid = (
            cast(OwnedStructure, structure).my
            or structure_type == STRUCTURE_CONTROLLER
            or structure_type == STRUCTURE_PORTAL
            or (
                cast(StructureContainer, structure).store
                and _.findKey(cast(StructureContainer, structure).store, is_saveable_amount)
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
        cast(Any, structure)['__valid_dismantle_target'] = not invalid
    return cast(Any, structure)['__valid_dismantle_target']


def get_opts(room_name):
    # type: (str) -> Dict[str, bool]
    if room_name in Memory.rooms:
        room_mem = Memory.rooms[room_name]
        if rmem_key_dismantler_squad_opts in room_mem:
            return cast(Dict[str, bool], room_mem[rmem_key_dismantler_squad_opts])

    return {'just_vitals': True}


def dismantle_pathfinder_callback(room_name):
    # type: (str) -> Union[PathFinder.CostMatrix, bool]
    room = Game.rooms[room_name]
    if room:
        opts = get_opts(room_name)
        plain_cost = 1
        matrix = honey.create_custom_cost_matrix(room_name, plain_cost, plain_cost * 5, 1, False)
        any_lairs = False
        for structure in cast(List[Structure], room.find(FIND_STRUCTURES)):
            structure_type = structure.structureType
            if structure_type == STRUCTURE_RAMPART and (cast(StructureRampart, structure).my
                                                        or cast(StructureRampart, structure).isPublic):
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
            elif structure_type == STRUCTURE_TOWER and cast(StructureTower, structure).energy:
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
        for site in cast(List[ConstructionSite], room.find(FIND_MY_CONSTRUCTION_SITES)):
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
    # type: (Dict[str, bool]) -> Callable[[Structure], bool]
    return lambda structure: structure.structureType != STRUCTURE_ROAD and can_target_struct(structure, opts)


def creep_condition_enemy(creep):
    # type: (Creep) -> bool
    return not creep.my and not Memory.meta.friends.includes(creep.owner.username.lower())


class SquadDismantle(SquadDrone):
    def run_squad(self, members, target):
        # type: (List[SquadDrone], Location) -> None
        if movement.chebyshev_distance_room_pos(self.pos, target) > 150:
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
            best_structure = cast(Structure, _.find(self.room.look_at(LOOK_STRUCTURES, next_pos),
                                                    get_dismantle_condition_not_a_road(opts)))
            if best_structure:
                result = self.creep.dismantle(best_structure)
                if result != OK:
                    self.log("Unknown result from {}.dismantle({}): {}", self.creep, best_structure, result)
                if result != ERR_NOT_IN_RANGE:
                    return
        elif next_pos == ERR_NOT_FOUND:
            del self.memory['_move']
        structures_around = cast(List[Dict[str, Structure]],
                                 self.room.look_for_in_area_around(LOOK_STRUCTURES, self.pos, 1))
        best_structure = None
        our_dismantle_power = DISMANTLE_POWER * self.creep.getActiveBodypartsBoostEquivalent(WORK, 'dismantle')
        if len(structures_around) > 1:
            ramparts_at = None
            for structure_obj in structures_around:
                if structure_obj[LOOK_STRUCTURES].structureType == STRUCTURE_RAMPART:
                    if ramparts_at is None:
                        ramparts_at = {}
                    ramparts_at[positions.serialize_pos_xy(structure_obj[LOOK_STRUCTURES].pos)] \
                        = structure_obj[LOOK_STRUCTURES].hits
            best_rank = -Infinity
            for structure_obj in cast(List[Dict[str, Structure]],
                                      self.room.look_for_in_area_around(LOOK_STRUCTURES, self.pos, 1)):
                structure = structure_obj[LOOK_STRUCTURES]
                if not can_target_struct(structure, opts):
                    continue
                if cast(OwnedStructure, structure).my \
                        or structure_type == STRUCTURE_CONTROLLER or structure_type == STRUCTURE_PORTAL \
                        or (cast(StructureContainer, structure).store
                            and _.findKey(cast(StructureContainer, structure).store,
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
                    rampart = ramparts_at[positions.serialize_pos_xy(structure.pos)]
                    if rampart and rampart.hits:
                        hits += rampart.hits

                if hits < our_dismantle_power:
                    rank -= hits / our_dismantle_power
                if rank > best_rank:
                    best_rank = rank
                    best_structure = structure
        elif len(structures_around):
            best_structure = structures_around[0][LOOK_STRUCTURES]
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
        # type: (Location) -> Optional[RoomPosition]
        opts = get_opts(self.pos.roomName)
        if self.memory.tloctimeout > Game.time:
            pos = positions.deserialize_xy_to_pos(self.memory.tloc, target.roomName)
            if pos:
                if _.some(self.room.look_at(LOOK_STRUCTURES, pos), get_dismantle_condition_not_a_road(opts)):
                    return pos
        structure_target = _.find(self.room.look_at(LOOK_STRUCTURES, target), get_dismantle_condition_not_a_road(opts))
        if structure_target:
            self.memory.tloc = positions.serialize_pos_xy(structure_target.pos)
            self.memory.tloctimeout = Game.time + 50
            return structure_target.pos

        if self.pos.roomName != target.roomName:
            return None

        best_target = None
        best_rank = -Infinity
        enemy_structures = cast(List[OwnedStructure], self.room.find(FIND_HOSTILE_STRUCTURES))
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
            rank -= movement.chebyshev_distance_room_pos(self.pos, struct.pos) / 20
            if structure_type != STRUCTURE_RAMPART:
                rampart = cast(StructureRampart, _.find(self.room.look_at(LOOK_STRUCTURES, struct.pos),
                                                        {'structureType': STRUCTURE_RAMPART}))
                if rampart:
                    rank -= 10 * rampart.hits / (DISMANTLE_POWER * MAX_CREEP_SIZE / 2 * CREEP_LIFE_TIME * 0.9)
            if rank > best_rank:
                best_target = struct
                best_rank = rank

        if best_target:
            self.memory.tloc = positions.serialize_pos_xy(best_target.pos)
            self.memory.tloctimeout = Game.time + 100
            return best_target.pos
        else:
            if self.pos.isNearTo(target):
                flag = flags.look_for(self.room, target, SQUAD_DISMANTLE_RANGED)
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
        # type: (str, Dict[str, Any]) -> Dict[str, Any]
        target = locations.get(self.memory.squad)
        if target and target.roomName == self.pos.roomName and target.roomName == target_room:
            self.log("using dismantler callback for {}", target_room)
            return _dismantle_move_to_opts
        else:
            return SquadDrone._move_options(self, target_room, opts)

    def findSpecialty(self):
        return WORK

import creeps.roles.squads
from constants import rmem_key_squad_memory
from empire import honey
from jstools.errorlog import try_exec
from jstools.screeps import *
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def __squad_get_mem():
    name = this.location.name
    room_mem = this.home.mem
    if not room_mem[rmem_key_squad_memory]:
        mem = {}
        room_mem[rmem_key_squad_memory] = {name: mem}
    elif name not in room_mem[rmem_key_squad_memory]:
        mem = room_mem[rmem_key_squad_memory][name] = {}
    else:
        mem = room_mem[rmem_key_squad_memory][name]

    Object.defineProperty(this, 'mem', {
        'value': mem,
        'enumerable': True,
        'configurable': True,
    })
    return mem

squadmemkey_origin = 'o'

class Squad:
    """
    :type home: rooms.room_mind.RoomMind
    :type __cached_members_movement_order: list[creeps.roles.squads.SquadDrone]
    :type members: list[creeps.roles.squads.SquadDrone]
    :type mem: dict[str, any]
    """

    def __init__(self, home, members, location):
        """
        :type home: rooms.room_mind.RoomMind
        :type members: list[creeps.roles.squads.SquadDrone]
        :type location: position_management.locations.Location
        """
        self.home = home
        self.members = members

        self.location = location

        __pragma__('skip')
        self.__cached_members_movement_order = undefined
        self.__origin = undefined
        self.mem = {}
        __pragma__('noskip')

    def log(self, message, *args):
        """
        :type message: str
        :type *args: any
        """
        if len(args):
            print("[{}][squad-{}] {}".format(self.home.name, self.location.name, message.format(*args)))
        else:
            print("[{}][squad-{}] {}".format(self.home.name, self.location.name, message))

    def find_home(self):
        return self.home.spawn or movement.find_an_open_space(self.home.name)

    def find_origin(self):
        if '__origin' not in self:
            origin_mem = self.mem[squadmemkey_origin]
            if origin_mem:
                origin = positions.deserialize_xy_to_pos(origin_mem.xy, origin_mem.room)
            else:
                origin = self.home.spawn or movement.find_an_open_space(self.home.name)
            self.__origin = origin
        return self.__origin

    def set_origin(self, origin):
        if origin.pos:
            origin = origin.pos
        origin = __new__(RoomPosition(origin.x, origin.y, origin.roomName))

        self.__origin = origin

        self.mem[squadmemkey_origin] = {'xy': positions.serialize_pos_xy(origin), 'room': origin.roomName}

    def members_movement_order(self):
        """
        :rtype list[creeps.roles.squads.SquadDrone]
        """
        if '__cached_members_movement_order' not in self:
            self.__cached_members_movement_order = self.calculate_movement_order()
        return self.__cached_members_movement_order

    def move_to_stage_0(self, target):
        """
        Stage 0 movement, for when creeps have not left the home room.

        :type target: position_management.locations.Location | RoomPosition
        """
        ordered_members = self.members_movement_order()

        self.log("Members {} moving - stage 0.", _.pluck(ordered_members, 'name'))

        for i in range(len(ordered_members) - 1, -1, -1):
            if i == 0:
                ordered_members[i].follow_military_path(self.find_origin(), target, self.new_movement_opts())
            else:
                ordered_members[i].move_to(ordered_members[i - 1])

    def move_to_stage_1(self, target, any_hostiles):
        """
        Stage 1 movement, for when creeps are still far from target room but have definitely left the home room.

        :type target: position_management.locations.Location | RoomPosition
        """
        ordered_members = self.members_movement_order()

        self.log("Members {} moving - stage 1.", _.pluck(ordered_members, 'name'))

        options = self.new_movement_opts()

        home = ordered_members[0].home
        origin = self.find_origin()

        serialized_obj = home.hive.honey.get_serialized_path_obj(origin, target, options)
        ordered_rooms_in_path = honey.get_room_list_from_serialized_obj(serialized_obj)

        room_path_lengths = []
        for room_name in ordered_rooms_in_path:
            room_path_lengths.push(len(serialized_obj[room_name]) - 1)

        members_path_positions = []
        any_member_off_path = False

        furthest_back_hurt_index = None

        for index in range(0, len(ordered_members)):
            drone = ordered_members[index]

            if drone.creep.hits < drone.creep.hitsMax:
                furthest_back_hurt_index = index

            room_index = ordered_rooms_in_path.indexOf(drone.pos.roomName)
            if not room_index:
                # if drone != ordered_members[0]:
                any_member_off_path = True
                members_path_positions.push(None)
                continue
            room_path = serialized_obj[drone.pos.roomName]

            path_index, moving_direction, reverse_dir = drone.creep.findIndexAndDirectionInPath(room_path)

            if path_index < 0:
                self.log("..: position ({},{}) is not within {} ({}, {}, {})",
                         drone.pos.x, drone.pos.y, room_path, path_index, moving_direction, reverse_dir)
                any_member_off_path = True
                members_path_positions.push(None)
                continue

            members_path_positions.push({
                'room': room_index,
                'path': path_index,
                'dir': moving_direction,
                'rev': reverse_dir,
            })

        if any_member_off_path:
            for i in range(len(ordered_members) - 1, -1, -1):
                member = ordered_members[i]

                moving_now = False
                if members_path_positions[i] is None:
                    # Since the member is definitely off the path
                    self.log("Member {} ({}) off path - individually following military path ({} -> {})..",
                             member.name, member.pos, origin, target)

                else:
                    if member.pos.x <= 2 or member.pos.x >= 48 or member.pos.y <= 2 or member.pos.y >= 48 \
                            or _.some(member.room.look_for_in_area_around(LOOK_STRUCTURES, member, 1),
                                      lambda s: s.destination):
                        moving_now = True
                    else:
                        # members near members that are off path should also move, to make room available.
                        for i2 in range(0, len(ordered_members)):
                            other_member = ordered_members[i2]
                            if members_path_positions[i2] is None \
                                    and movement.chebyshev_distance_room_pos(other_member, member) \
                                            <= len(ordered_members) + 1:
                                moving_now = True
                                break

                    if moving_now:
                        direction = members_path_positions[i].dir
                        # key code turned from findIndexAndDirectionInPath when we're at an exit and we should
                        # just say put.
                        if direction != -30:
                            result = member.creep.move(direction)
                            member.creep.__direction_moved = direction
                            if result != OK and result != ERR_TIRED:
                                member.log("Error moving by squad path ({}.move({})): {}",
                                           member.creep, direction, result)
                member.follow_military_path(origin, target, options)
        else:
            more_to_move_without_near_edge = Infinity
            # iterate backwards over every member so we can break the loop easily if any further back members are
            # too far behind.
            # ordered_members[0] is the head of the group
            any_fatigued = False
            for i in range(len(ordered_members) - 1, -1, -1):
                drone = ordered_members[i]

                if drone.creep.fatigue:
                    any_fatigued = True

                # will sometimes be undefined, but that's ok since it's only used if furthest_back_hurt_index > 1
                prev_drone = ordered_members[i + 1]
                move_obj = members_path_positions[i]

                if drone.memory.off_path_for:
                    del drone.memory.next_ppos
                    del drone.memory.off_path_for
                    del drone.memory.lost_path_at

                if more_to_move_without_near_edge <= 0 and not movement.is_edge_position(drone.pos):
                    continue
                else:
                    more_to_move_without_near_edge -= 1

                # self.log("[{}] regular stage1 movement in dir {}", drone.name, move_obj.dir)

                # key code turned from findIndexAndDirectionInPath when we're at an exit and we should
                # just say put.
                if not move_obj and i == 0:
                    drone.follow_military_path(origin, target, options)
                else:
                    if furthest_back_hurt_index > i:
                        drone.log("moving backwards to help out.")
                        if not drone.pos.isNearTo(prev_drone) and any_fatigued:
                            if move_obj.rev != -30:
                                result = drone.creep.move(move_obj.rev)
                                drone.creep.__direction_moved = move_obj.rev
                                if result != OK and result != ERR_TIRED:
                                    drone.log("Error moving by squad path ({}.move({})): {}",
                                              drone.creep, move_obj.rev, result)
                        continue

                    if move_obj.dir != -30:
                        result = drone.creep.move(move_obj.dir)
                        drone.creep.__direction_moved = move_obj.dir
                        if result != OK and result != ERR_TIRED:
                            drone.log("Error moving by squad path ({}.move({})): {}", drone.creep, move_obj.dir, result)

                if i != 0:
                    next_member_obj = members_path_positions[i - 1]

                    room_diff = next_member_obj['room'] - move_obj['room']
                    if room_diff < 0:
                        self.log("[{}] we're ahead - moving backwards ({})", drone.name, move_obj.rev)
                        if move_obj.rev != -30:
                            result = drone.creep.move(move_obj.rev)
                            drone.creep.__direction_moved = move_obj.rev
                            if result != OK and result != ERR_TIRED:
                                drone.log("Error moving by squad path ({}.move({})): {}",
                                          drone.creep, move_obj.rev, result)
                        continue
                    elif room_diff == 0:
                        abs_path_diff = next_member_obj['path'] - move_obj['path']

                        if abs_path_diff < 0:
                            self.log("[{}] we're ahead - moving backwards ({}).", drone.name, move_obj.rev)
                            if move_obj.rev != -30:
                                result = drone.creep.move(move_obj.rev)
                                drone.creep.__direction_moved = move_obj.rev
                                if result != OK and result != ERR_TIRED:
                                    drone.log("Error moving by squad path ({}.move({})): {}",
                                              drone.creep, move_obj.rev, result)
                            continue
                    elif room_diff == 1:
                        # use the room path length to see how far we are to the edge of the room, to get an accurate
                        # diff
                        abs_path_diff = (next_member_obj['path'] - 4) \
                                        + (room_path_lengths[move_obj['room']] - move_obj['path'])

                        if abs_path_diff < 0:
                            # room_path_lengths is an estimation, and may be off.
                            abs_path_diff = next_member_obj['path']
                    else:
                        # just a message that we're quite far behind.
                        abs_path_diff = 100

                    self.log("[{}] room diff: {}, path diff: {}, pos: {}",
                             drone.name, room_diff, abs_path_diff, drone.pos)
                    if abs_path_diff > 10 or (any_hostiles and abs_path_diff > 1):
                        more_to_move_without_near_edge = 0
                        continue
                    elif abs_path_diff <= 1:
                        more_to_move_without_near_edge += 1
                        # TODO: move backwards to re-unite when there are hostiles.

    def move_to_stage_2(self, target):
        """
        Stage 2 movement, where we're near the enemy base and we need to keep tight formation.

        The default method is a tight line, recommended to replace this with something more intricate.

        :type target: position_management.locations.Location | RoomPosition
        """
        ordered_members = self.members_movement_order()

        self.log("Members {} moving to {} - stage 2.", _.pluck(ordered_members, 'name'), target)

        movement_opts = self.new_movement_opts()

        for i in range(len(ordered_members) - 1, -1, -1):
            if i == 0:
                if not ordered_members[i].pos.isEqualTo(target):
                    if target == self.location:
                        ordered_members[i].follow_military_path(self.find_origin(), target, movement_opts)
                    else:
                        ordered_members[i].move_to(target, movement_opts)
            else:
                next_drone = ordered_members[i - 1]
                this_drone = ordered_members[i]
                if this_drone.pos.isNearTo(next_drone.pos) or movement.is_edge_position(next_drone.pos):
                    if this_drone.creep.fatigue and not movement.is_edge_position(next_drone.pos):
                        self.log("drone {} at {},{} breaking due to fatigue", i, this_drone.pos.x, this_drone.pos.y)
                        break
                    direction = movement.diff_as_direction(this_drone, next_drone)
                    this_drone.creep.move(direction)
                    this_drone.creep.__direction_moved = direction
                elif movement.is_edge_position(this_drone):
                    this_drone.move_to(next_drone)
                elif movement.chebyshev_distance_room_pos(this_drone, next_drone) > 3 or (
                                movement.chebyshev_distance_room_pos(this_drone, next_drone) > 1
                        and not movement.is_edge_position(next_drone)
                ):
                    this_drone.move_to(next_drone)
                    self.log("drone {} at {},{} breaking due to distance", i, this_drone.pos.x, this_drone.pos.y)
                    break
                else:
                    # for j in range(len(ordered_members) - 1, i, -1):
                    #     ordered_members[j].creep.move(
                    #         movement.diff_as_direction(ordered_members[j], ordered_members[j - 1]))
                    moved = False

                    if movement.chebyshev_distance_room_pos(this_drone, next_drone) == 2:
                        # Note: we are guaranteed not to be in an edge position because if we were, the above
                        # if would be triggered instead! This allows us to ignore the room name of the next pos.
                        next_pos = movement.next_pos_in_direction_to(this_drone, next_drone)
                        if movement.is_block_empty(this_drone.room, next_pos.x, next_pos.y):
                            other_creeps_there = this_drone.room.look_at(LOOK_CREEPS, next_pos)
                            other_drone = _.find(other_creeps_there, 'my')
                            if other_drone:
                                other_drone.move(movement.diff_as_direction(other_drone, this_drone))
                                this_drone.creep.move(movement.diff_as_direction(this_drone, next_drone))
                                moved = True
                            elif not len(other_creeps_there):
                                direction = movement.diff_as_direction(this_drone, next_drone)
                                this_drone.creep.move(direction)
                                this_drone.creep.__direction_moved = direction
                                moved = True
                    if not moved:
                        this_drone.move_to(next_drone)

    def move_to(self, target):
        """
        Method that judges distance to target, and then delegates to stage_0, stage_1 or stage_2 movement.

        :type target: position_management.locations.Location | RoomPosition
        """
        hive = self.home.hive
        home = self.find_home()
        origin = self.find_origin()

        total_distance = hive.honey.find_path_length(origin, target, self.new_movement_opts())

        min_distance_from_home = Infinity
        min_distance_to_origin = Infinity
        min_distance_to_target = movement.chebyshev_distance_room_pos(self.members_movement_order()[0], target)
        max_distance_to_target = -Infinity
        any_hostiles = False
        for member in self.members:
            distance_to_home = movement.chebyshev_distance_room_pos(member, home)
            distance_to_origin = movement.chebyshev_distance_room_pos(member, origin)
            distance_to_target = movement.chebyshev_distance_room_pos(member, target)
            if distance_to_home < min_distance_from_home:
                min_distance_from_home = distance_to_home
            if distance_to_target > max_distance_to_target:
                max_distance_to_target = distance_to_target
            if distance_to_origin < min_distance_to_origin:
                min_distance_to_origin = distance_to_origin
            if len(member.room.find(FIND_HOSTILE_CREEPS)):
                any_hostiles = True

        if min_distance_to_origin > 100:
            mv_order = self.members_movement_order()
            self.set_origin(mv_order[len(mv_order) - 1].pos)
        if min_distance_from_home < 50 and (max_distance_to_target < total_distance / 2):
            print('[squads][{}] move_to: chose stage 0 (minimum distance from home: {}, maximum distance from home: {},'
                  ' total distance: {})'
                  .format(self.location.name, min_distance_from_home, max_distance_to_target, total_distance))
            self.move_to_stage_0(target)
        elif min_distance_to_target < 300 and any_hostiles:
            self.move_to_stage_2(target)
        elif min_distance_to_target > 60 or max_distance_to_target > 200:
            # print('[squads][{}] move_to: chose stage 1 (minimum distance from home: {}, total distance: {}, '
            #       'minimum distance to target: {}, maximum distance to target: {})'
            #       .format(self.location.name, min_distance_from_home, total_distance,
            #               min_distance_to_target, max_distance_to_target))
            self.move_to_stage_1(target, any_hostiles)
        else:
            # print('[squads][{}] move_to: chose stage 2 (minimum distance from home: {}, total distance: {}, '
            #       'minimum distance to target: {}, maximum distance to target: {})'
            #       .format(self.location.name, min_distance_from_home, total_distance,
            #               min_distance_to_target, max_distance_to_target))
            self.move_to_stage_2(target)

    def new_movement_opts(self):
        """
        :rtype: dict[str, any]
        """
        if self.is_heavily_armed():
            return {'sk_ok': True, 'use_roads': False}
        else:
            return {'use_roads': False}

    def is_heavily_armed(self):
        """
        Recommended override function.

        :rtype: bool
        """
        return False

    def calculate_movement_order(self):
        """
        Recommended override function.

        Returns all of self members in a deterministic order - called once per tick when used, then cached.

        :rtype: list[creeps.roles.squads.SquadDrone]
        """
        return _.sortByAll(self.members, 'name')

    def run(self):
        """
        Recommended override function.

        Runs movement towards the target by default.
        """
        self.move_to(self.location)


Object.defineProperty(Squad, 'mem', {
    'get': __squad_get_mem,
    'enumerable': True,
    'configurable': True,
})

specialty_order = [ATTACK, WORK, HEAL, RANGED_ATTACK]


class BasicOffenseSquad(Squad):
    def calculate_movement_order(self):
        return _.sortByAll(self.members, lambda x: specialty_order.index(x.findSpecialty()), 'name')

    def run(self):
        # gets cached movement order members
        members = self.members_movement_order()
        if len(members) > 1:
            if members[0].creep.hits < members[0].creep.hitsMax * 0.6:
                temp = members[0]
                members[0] = members[1]
                members[1] = temp
                if len(members) == 4 and members[2].findSpecialty() == HEAL and members[3].findSpecialty() != HEAL:
                    temp = members[2]
                    members[2] = members[3]
                    members[3] = temp

        last_pos = members[len(members) - 1].pos
        if last_pos.roomName == self.location.roomName and not movement.is_edge_position(last_pos):
            target_here = None
            for member in members:
                target_here = member.find_target_here(self.location)
                if target_here:
                    break
            if target_here:
                members[0].creep.__moved = True
                self.move_to_stage_2(target_here)
            else:
                self.move_to(self.location)
        else:
            self.move_to(self.location)
        for member in members:
            try_exec(
                "squads",
                member.run_squad,
                lambda: "Error during run_squad for {}, a {}.".format(member.name, member.memory.role),
                members,
                self.location
            )


class ScoutSquad(Squad):
    def new_movement_opts(self):
        return {'use_roads': False, 'ignore_swamp': True}

    def run(self):
        members = self.members_movement_order()
        self.log('Running scout squad {} with members {}',
                 self.location.name, [member.name for member in members])
        if members[0].pos.isNearTo(self.location):
            for i in range(0, len(members) - 1):
                if not members[i].pos.isNearTo(members[i + 1].pos):
                    break
            else:
                return
        self.move_to(self.location)


kiting_order = [RANGED_ATTACK, HEAL]


class KitingPairSquad(Squad):
    def calculate_movement_order(self):
        return _.sortByAll(self.members, lambda x: kiting_order.index(x.findSpecialty()), 'name')

    def run(self):
        members = self.members_movement_order()
        last_pos = members[len(members) - 1].pos
        if last_pos.roomName == self.location.roomName and not movement.is_edge_position(last_pos) \
                or len(members[0].room.find(FIND_HOSTILE_CREEPS)):
            do_things = True
        else:
            do_things = False
        for member in members:
            result = try_exec(
                "squads",
                member.run_squad,
                lambda: "Error during run_squad for {}, a {}.".format(member.name, member.memory.role),
                members,
                self.location,
                do_things,
            )
            if result and not do_things:
                do_things = True
        if do_things:
            self.move_to_stage_2(members[0])
        else:
            self.move_to(self.location)

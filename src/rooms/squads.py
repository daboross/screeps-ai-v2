from constants import SQUAD_4_SCOUTS, SQUAD_DISMANTLE_RANGED, SQUAD_DUAL_ATTACK, SQUAD_DUAL_SCOUTS, SQUAD_KITING_PAIR, \
    SQUAD_TOWER_DRAIN, creep_base_full_move_attack, creep_base_scout, creep_base_squad_dismantle, \
    creep_base_squad_healer, creep_base_squad_ranged, request_priority_attack, rmem_key_alive_quads, \
    role_squad_dismantle, role_squad_drone, role_squad_final_boost, role_squad_final_renew, role_squad_heal, \
    role_squad_init, role_squad_kiting_attack, role_squad_kiting_heal, role_squad_ranged, target_single_flag
from constants.memkeys.room import cache_key_squads
from jstools.errorlog import try_exec
from jstools.js_set_map import new_map
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


def can_renew(creep):
    return not creep.creep.spawning and (
        creep.creep.ticksToLive <
        CREEP_LIFE_TIME
        - (SPAWN_RENEW_RATIO * CREEP_LIFE_TIME / CREEP_SPAWN_TIME / len(creep.creep.body))
    )


def ticks_to_renew(creep):
    if creep.creep.spawning:
        return 0
    return (
        (CREEP_LIFE_TIME - creep.creep.ticksToLive)
        / (SPAWN_RENEW_RATIO * CREEP_LIFE_TIME / CREEP_SPAWN_TIME / len(creep.creep.body))
    )


def roles_required_for(flag):
    hint = flag.hint
    if hint == SQUAD_KITING_PAIR:
        return {HEAL: 1, RANGED_ATTACK: 1}
    elif hint == SQUAD_DUAL_ATTACK:
        return {ATTACK: 1, HEAL: 1}
    elif hint == SQUAD_DUAL_SCOUTS:
        return {MOVE: 2}
    elif hint == SQUAD_4_SCOUTS:
        return {MOVE: 4}
    elif hint == SQUAD_DISMANTLE_RANGED:
        return {WORK: 1, HEAL: 2, RANGED_ATTACK: 1}
    elif hint == SQUAD_TOWER_DRAIN:
        return {HEAL: 3}
    else:
        print("[squads][roles_required_for] Unknown hint {}!".format(flag.hint))
        return {}


def get_base_for(flag, specialty):
    if flag.name in Memory.flags and Memory.flags[flag.name].size:
        size = Memory.flags[flag.name].size
    else:
        size = MAX_CREEP_SIZE
    if specialty == MOVE:
        return creep_base_scout, 1
    elif specialty == ATTACK:
        return creep_base_full_move_attack, size
    elif specialty == HEAL:
        return creep_base_squad_healer, size
    elif specialty == RANGED_ATTACK:
        return creep_base_squad_ranged, size
    elif specialty == WORK:
        return creep_base_squad_dismantle, size
    else:
        print("[squads][get_base_for] Unknown type {}!".format(specialty))
        return creep_base_scout, 1


def get_drone_role(target_hint, specialty):
    if target_hint == SQUAD_TOWER_DRAIN:
        return role_squad_heal
    if target_hint == SQUAD_KITING_PAIR:
        if specialty == RANGED_ATTACK:
            return role_squad_kiting_attack
        elif specialty == HEAL:
            return role_squad_kiting_heal
    if specialty == MOVE:
        return role_squad_drone
    elif specialty == WORK:
        return role_squad_dismantle
    elif specialty == RANGED_ATTACK:
        return role_squad_ranged
    elif specialty == HEAL:
        return role_squad_heal


_boosts_to_use = {
    HEAL: RESOURCE_CATALYZED_LEMERGIUM_ALKALIDE,
    RANGED_ATTACK: RESOURCE_CATALYZED_KEANIUM_ALKALIDE,
    WORK: RESOURCE_CATALYZED_ZYNTHIUM_ACID,
}


class SquadTactics:
    """
    :type room: rooms.room_mind.RoomMind
    :type _renewing_registered: list[creeps.base.RoleBase]
    :type _boost_registered: jstools.js_set_map.JSMap
    :type _stage0_registered_for_target: jstools.js_set_map.JSMap
    :type _stage1_registered_for_squad_id: jstools.js_set_map.JSMap
    :type _stage2_registered_for_squad_id: jstools.js_set_map.JSMap
    :type _stage3_registered_for_squad_id: jstools.js_set_map.JSMap
    """

    def __init__(self, room):
        self.room = room
        __pragma__('skip')
        self._squad_targets = undefined
        self._renewing_registered = undefined
        self._boost_registered = undefined
        self._any_high_priority_renew = undefined
        self._stage0_registered_for_target = undefined
        self._stage1_registered_for_squad_id = undefined
        self._stage2_registered_for_squad_id = undefined
        self._stage3_registered_for_squad_id = undefined
        __pragma__('noskip')

    __pragma__('fcall')

    def squad_targets(self):
        """
        :rtype: list[Flag | position_management.locations.Location]
        """
        targets = self._squad_targets
        if targets is not undefined:
            return targets
        targets = []
        cached = self.room.get_cached_property(cache_key_squads)
        if cached:
            for name in cached:
                flag = Game.flags[name]
                if flag:
                    targets.append(flag)
        else:
            cached = []
            for flag in flags.find_flags_global_multitype_shared_primary([
                SQUAD_KITING_PAIR,
                SQUAD_DUAL_SCOUTS,
                SQUAD_4_SCOUTS,
                SQUAD_DUAL_ATTACK,
                SQUAD_DISMANTLE_RANGED,
                SQUAD_TOWER_DRAIN,
            ]):
                if flags.flag_sponsor(flag) == self.room.name:
                    targets.append(flag)
                    cached.append(flag.name)
            self.room.store_cached_property(cache_key_squads, cached, 100)
        self._squad_targets = targets
        return targets

    def renew_or_depot(self, creep):
        """
        :type creep: creeps.base.RoleBase
        """
        if creep.creep.spawning:
            return
        if not can_renew(creep) or not len(self.room.spawns):
            del creep.memory.renewed_last
            creep.go_to_depot()
            return
        if self._renewing_registered is undefined:
            self._renewing_registered = []
        self._renewing_registered.append(creep)

    def boost_or_depot(self, creep):
        """
        :type creep: creeps.base.RoleBase
        """
        if not self.can_boost(creep):
            creep.go_to_depot()
            return
        if self._boost_registered is undefined:
            self._boost_registered = new_map()
        specialty = creep.findSpecialty()
        specialty_list = self._boost_registered.get(specialty)
        if not specialty_list:
            specialty_list = []
            self._boost_registered.set(specialty, specialty_list)
        specialty_list.append(creep)

    def can_boost(self, creep):
        specialty = creep.findSpecialty()
        mineral = _boosts_to_use[specialty]
        if not mineral:
            print("[{}][squads] Can't boost {} due to lack of a mineral specified for {} creeps."
                  .format(self.room.name, creep.name, specialty))
            return False
        labs = self.room.minerals.labs_for(mineral)
        if not len(labs):
            print("[{}][squads] Can't boost {} due to lack of labs for boosting with {}."
                  .format(self.room.name, creep.name, mineral))
            return False
        return _.some(creep.creep.body, lambda part: part.type == specialty and not part.boost)

    def run(self):
        if (Game.time + self.room.get_unique_owned_index()) % 25 == 5:
            targets_with_active_squads = []
        else:
            targets_with_active_squads = None
        if self._renewing_registered:
            self.run_renewal()
        if self._boost_registered:
            self.run_boosts()
        if self._stage1_registered_for_squad_id:
            self.run_stage1(targets_with_active_squads)
        if self._stage2_registered_for_squad_id:
            self.run_stage2(targets_with_active_squads)
        if self._stage3_registered_for_squad_id:
            self.run_stage3(targets_with_active_squads)
        if (Game.time + self.room.get_unique_owned_index()) % 40 == 0:
            del self.room.mem[rmem_key_alive_quads]
        if self._stage0_registered_for_target:
            self.run_stage0()
        if targets_with_active_squads:
            self.request_spawns_for_targets_excluding(targets_with_active_squads)

    def note_stage0_creep(self, creep, target):
        """
        :type creep: creeps.base.RoleBase
        :type target: Flag | position_management.locations.Location
        """
        if self._stage0_registered_for_target is undefined:
            self._stage0_registered_for_target = new_map()
        registered_so_far_tuple = self._stage0_registered_for_target.get(target.name)
        if not registered_so_far_tuple:
            registered_so_far_tuple = [target, []]
            self._stage0_registered_for_target.set(target.name, registered_so_far_tuple)
        registered_so_far_tuple[1].append(creep)

    def note_stage1_creep(self, creep, squad_id):
        """
        :type creep: creeps.base.RoleBase
        :type squad_id: str
        """
        if not self._stage1_registered_for_squad_id:
            self._stage1_registered_for_squad_id = new_map()
        members = self._stage1_registered_for_squad_id.get(squad_id)
        if not members:
            members = []
            self._stage1_registered_for_squad_id.set(squad_id, members)
        members.push(creep)

    def note_stage2_creep(self, creep, squad_id):
        """
        :type creep: creeps.base.RoleBase
        :type squad_id: str
        """
        if not self._stage2_registered_for_squad_id:
            self._stage2_registered_for_squad_id = new_map()
        members = self._stage2_registered_for_squad_id.get(squad_id)
        if not members:
            members = []
            self._stage2_registered_for_squad_id.set(squad_id, members)
        members.push(creep)

    def note_stage3_creep(self, creep, squad_id):
        """
        :type creep: creeps.base.RoleBase
        :type squad_id: str
        """
        if not self._stage3_registered_for_squad_id:
            self._stage3_registered_for_squad_id = new_map()
        members = self._stage3_registered_for_squad_id.get(squad_id)
        if not members:
            members = []
            self._stage3_registered_for_squad_id.set(squad_id, members)
        members.push(creep)

    def any_high_priority_renew(self):
        if self._renewing_registered is undefined:
            return False
        length = len(self._renewing_registered)
        if self._any_high_priority_renew is not undefined \
                and self._any_high_priority_renew[0] == length:
            return self._any_high_priority_renew[1]
        any_high_priority = False
        for creep in self._renewing_registered:
            if creep.memory.role != role_squad_init:
                any_high_priority = True
                break
        self._any_high_priority_renew = [length, any_high_priority]
        return any_high_priority

    def run_renewal(self):
        reset_high_prio_renew_status = False
        min_time_till_done = Infinity
        next_open_spawn = None
        if not self.room.next_role or self.any_high_priority_renew():
            avail_spawns = []
            for spawn in self.room.spawns:
                if not spawn.spawning:
                    avail_spawns.append(spawn)
            if len(avail_spawns):
                if len(self._renewing_registered) > 1:
                    def rank_renewing_creep(c):
                        extra = 0
                        if c.memory.role != role_squad_init:
                            extra += 1000
                        if c.memory.renewed_last:
                            extra += 200
                        return extra - ticks_to_renew(c) - movement.minimum_chebyshev_distance(c, self.room.spawns)

                    # NOTE! Below, the sorted array is essentially iterated backwards, with the last creep being the
                    # one put in the best position to renew! This array is sorted lowest priority to highest priority.
                    self._renewing_registered = _.sortBy(self._renewing_registered, rank_renewing_creep)

                while len(avail_spawns) and len(self._renewing_registered):
                    creep = self._renewing_registered.js_pop()
                    if creep.memory.role != role_squad_init:
                        reset_high_prio_renew_status = True
                    closest_spawn = None
                    closest_distance = Infinity
                    for spawn in avail_spawns:
                        distance = movement.chebyshev_distance_room_pos(creep, spawn)
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_spawn = spawn
                    _.pull(avail_spawns, closest_spawn)
                    creep.memory.renewed_last = True
                    if creep.pos.isNearTo(closest_spawn):
                        result = closest_spawn.renewCreep(creep.creep)
                        if result != OK:
                            print("[{}][squads] Unknown result from {}.renewCreep({}): {}"
                                  .format(self.room.name, closest_spawn, creep.creep, result))
                    else:
                        creep.move_to(closest_spawn)
                    time_till_done = ticks_to_renew(creep)
                    if time_till_done < min_time_till_done:
                        min_time_till_done = time_till_done
                        next_open_spawn = closest_spawn
        for creep in self._renewing_registered:
            if creep.memory.role != role_squad_init:
                reset_high_prio_renew_status = True
            del creep.memory.renewed_last
            if next_open_spawn and not creep.pos.isNearTo(next_open_spawn) and min_time_till_done \
                    < movement.chebyshev_distance_room_pos(creep.find_depot(), next_open_spawn):
                creep.move_to(next_open_spawn)
            else:
                creep.go_to_depot()
        self._any_high_priority_renew = [len(self._renewing_registered), reset_high_prio_renew_status]

    def run_boosts(self):
        for specialty, creeps in list(self._boost_registered.entries()):
            mineral = _boosts_to_use[specialty]
            creeps = _.sortBy(creeps, lambda c: c.ticksToLive)
            original_labs = self.room.minerals.labs_for(mineral)
            labs = _.clone(original_labs)
            while len(creeps):
                creep = creeps.js_pop()
                closest_lab = None
                closest_distance = Infinity
                if len(labs):
                    for lab in labs:
                        distance = movement.chebyshev_distance_room_pos(lab, creep)
                        if distance < closest_distance:
                            closest_lab = lab
                            closest_distance = distance
                    _.pull(labs, closest_lab)
                    boost_if_close = True
                else:
                    for lab in original_labs:
                        distance = movement.chebyshev_distance_room_pos(lab, creep)
                        if distance < closest_distance:
                            closest_lab = lab
                            closest_distance = distance
                    boost_if_close = False
                if creep.pos.isNearTo(closest_lab) and (boost_if_close or not closest_lab.__boosted):
                    result = closest_lab.boostCreep(creep.creep)
                    closest_lab.__boosted = True
                    if result != OK:
                        print("[{}][squads] Unknown result from {}.boostCreep({}): {}"
                              .format(self.room.name, closest_lab, creep.creep, result))
                else:
                    creep.move_to(closest_lab)

    def run_stage0(self):
        for target, registered_so_far in list(self._stage0_registered_for_target.values()):
            required = roles_required_for(target)
            for to_check in registered_so_far:
                if to_check.creep.spawning:
                    continue  # NOTE: done here but not below in spawn request calculations
                specialty = to_check.findSpecialty()
                if required[specialty] > 0:
                    required[specialty] -= 1
            any_needed = False
            for requirement in Object.keys(required):
                if required[requirement] > 0:
                    any_needed = True
            if not any_needed:
                squad_target = locations.create(target.pos, target.hint, 3000)
                print("[squads] New squad formed! Squad {} has members {}."
                      .format(squad_target, [c.name for c in registered_so_far].join(', ')))
                for creep in registered_so_far:
                    creep.targets.untarget_all(creep)
                    creep.memory = Memory.creeps[creep.name] = {
                        'home': creep.memory.home,
                        'role': role_squad_final_renew,
                        'squad': squad_target.name
                    }

    def run_stage1(self, tracking_for_targets_with_active_squads):
        for squad_id, squad_members in list(self._stage1_registered_for_squad_id.entries()):
            target = locations.get(squad_id)
            if not target:
                print("[{}] Squad at {} lost! could not find location!".format(self.room.name, squad_id))
                for member in squad_members:
                    member.memory.role = role_squad_init
                continue
            any_can_renew = False
            for creep in squad_members:
                if creep.creep.spawning or (can_renew(creep) and len(self.room.spawns)):
                    any_can_renew = True
                    break
            if not any_can_renew:
                if _.any(squad_members, lambda x: self.can_boost(x)):
                    for creep in squad_members:
                        del creep.memory.renewed_last
                        creep.memory.role = role_squad_final_boost
                else:
                    for creep in squad_members:
                        del creep.memory.renewed_last
                        creep.memory.role = get_drone_role(target.hint, creep.findSpecialty())
            if tracking_for_targets_with_active_squads:
                tracking_for_targets_with_active_squads.append(positions.serialize_xy_room_pos(target))

    def run_stage2(self, tracking_for_targets_with_active_squads):
        for squad_id, squad_members in list(self._stage2_registered_for_squad_id.entries()):
            target = locations.get(squad_id)
            if not target:
                print("[{}] Squad at {} lost! could not find location!".format(self.room.name, squad_id))
                for member in squad_members:
                    member.memory.role = role_squad_init
                continue
            any_can_boost = False
            for creep in squad_members:
                if creep.creep.spawning or self.can_boost(creep):
                    any_can_boost = True
                    break
            if not any_can_boost:
                for creep in squad_members:
                    del creep.memory.renewed_last
                    creep.memory.role = get_drone_role(target.hint, creep.findSpecialty())
            if tracking_for_targets_with_active_squads:
                tracking_for_targets_with_active_squads.append(positions.serialize_xy_room_pos(target))

    def run_stage3(self, targets_fully_alive):
        for squad_id, squad_members in list(self._stage3_registered_for_squad_id.entries()):
            target = locations.get(squad_id)
            if not target:
                print("[{}] Squad at {} lost! could not find location!"
                      .format(self.room.name, squad_id))
                continue
            target_type = target.hint
            if target_type not in squad_run_funcs:
                print("[{}][squads] Warning: couldn't find run func for squad type {}!"
                      .format(self.room.name, target_type))
            squad_run_funcs[target_type](self.room, squad_members, target)
            if targets_fully_alive:
                any_near_death = False
                distance = self.room.hive.honey.find_path_length(self.room.spawn, target, {'use_roads': False})
                for member in squad_members:
                    if member.ticksToLive < distance + CREEP_SPAWN_TIME * len(member.body):
                        any_near_death = True
                        break
                if not any_near_death:
                    targets_fully_alive.append(positions.serialize_xy_room_pos(target))

    def request_spawns_for_targets_excluding(self, targets_already_active):
        """
        :type targets_already_active: list
        """
        for target in self.squad_targets():
            if not targets_already_active.includes(positions.serialize_xy_room_pos(target)):
                required = roles_required_for(target)
                if self._stage0_registered_for_target:
                    this_init_tuple = self._stage0_registered_for_target.get(target.name)
                    if this_init_tuple:
                        for to_check in this_init_tuple[1]:
                            specialty = to_check.findSpecialty()
                            if required[specialty] > 0:
                                required[specialty] -= 1
                if target.name in Game.flags:
                    target_name = "flag-" + target.name
                else:
                    target_name = target.name
                for key in Object.keys(required):
                    base, num_sections = get_base_for(target, key)
                    for i in range(0, required[key]):
                        request_key = 'squad|{}|{}|{}'.format(target.name, key, str(10 - required[key] + i))
                        print('[{}][squads] requesting creep {}.'.format(self.room.name, request_key))
                        self.room.register_creep_request(
                            request_key,
                            request_priority_attack,
                            Game.time + 26,
                            {
                                'role': role_squad_init,
                                'targets': [[target_single_flag, target_name]],
                                'base': base,
                                'num_sections': num_sections,
                            }
                        )

    __pragma__('nofcall')


def move_to_single_file(home, ordered_members, target, basic_move=False, no_move_if_close=False):
    """
    Moves all of the members to a given target.
    :param home: The home room.
    :param ordered_members: The members
    :param target: The target
    :param basic_move: If true, move using move_to rather than follow_military_path from spawn
    :param no_move_if_close: If true, will not execute any move commands if creeps are already in position
    :type home: rooms.room_mind.RoomMind
    :type ordered_members: list[creeps.behaviors.military.MilitaryBase]
    :type target: position_management.locations.Location
    :type basic_move: bool
    :type no_move_if_close: bool
    """
    if not len(ordered_members):
        return
    if basic_move:
        near_target = True
    else:
        distance_to_spawn = movement.chebyshev_distance_room_pos(
            home.spawn or movement.find_an_open_space(home.name), target)
        distance_to_target = movement.chebyshev_distance_room_pos(ordered_members[0], target)
        near_target = (distance_to_spawn > 50) or (distance_to_target < distance_to_spawn and distance_to_spawn > 10)
    for i in range(len(ordered_members) - 1, -1, -1):
        if i == 0:
            if not no_move_if_close:
                if basic_move:
                    ordered_members[i].move_to(target)
                else:
                    ordered_members[i].follow_military_path(home.spawn, target)
        else:
            next_drone = ordered_members[i - 1]
            this_drone = ordered_members[i]
            if this_drone.pos.isNearTo(next_drone.pos) or movement.is_edge_position(next_drone.pos):
                if not no_move_if_close:
                    this_drone.creep.move(movement.diff_as_direction(this_drone, next_drone))
                if this_drone.creep.fatigue:
                    break
            elif near_target and not (movement.chebyshev_distance_room_pos(this_drone, next_drone) <= 3
                                      and (movement.is_edge_position(this_drone))):
                if no_move_if_close:
                    for j in range(len(ordered_members) - 1, i, -1):
                        ordered_members[j].creep.move(
                            movement.diff_as_direction(ordered_members[j], ordered_members[j - 1]))
                this_drone.move_to(next_drone)
                break
            else:
                if no_move_if_close:
                    for j in range(len(ordered_members) - 1, i, -1):
                        ordered_members[j].creep.move(
                            movement.diff_as_direction(ordered_members[j], ordered_members[j - 1]))
                moved = False
                if near_target:
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
                                this_drone.creep.move(movement.diff_as_direction(this_drone, next_drone))
                                moved = True
                if not moved:
                    if basic_move:
                        this_drone.move_to(target)
                    else:
                        this_drone.follow_military_path(home.spawn, target)


def run_scout_squad(home, members, target):
    """
    :type home: rooms.room_mind.RoomMind
    :type members: list[creeps.base.RoleBase]
    :type target: position_management.locations.Location
    """
    members = _.sortByAll(members, 'name')
    print('[scout squad] Running squad {} with members {}'.format(target.name, [member.name for member in members]))
    if members[0].pos.isNearTo(target):
        for i in range(0, len(members) - 1):
            if not members[i].pos.isNearTo(members[i + 1].pos):
                break
        else:
            return
    move_to_single_file(home, members, target)


specialty_order = [ATTACK, WORK, HEAL, RANGED_ATTACK]


def run_small_single_file_offense(home, members, target):
    """
    :type home: rooms.room_mind.RoomMind
    :type members: list[creeps.roles.squads.SquadDrone]
    :type target: position_management.locations.Location
    """

    if len(members) > 1:
        members = _.sortByAll(members, lambda x: specialty_order.index(x.findSpecialty()), 'name')
        if members[0].creep.hits < members[0].creep.hitsMax * 0.6:
            temp = members[0]
            members[0] = members[1]
            members[1] = temp
            if len(members) == 4 and members[2].findSpecialty() == HEAL and members[3].findSpecialty() != HEAL:
                temp = members[2]
                members[2] = members[3]
                members[3] = temp
    last_pos = members[len(members) - 1].pos
    if last_pos.roomName == target.roomName and not movement.is_edge_position(last_pos):
        target_here = None
        for member in members:
            target_here = member.find_target_here(target)
            if target_here:
                break
        if target_here:
            move_to_single_file(home, members, target_here, True)
    else:
        move_to_single_file(home, members, target)
    for member in members:
        try_exec(
            "squads",
            member.run_squad,
            lambda: "Error during run_squad for {}, a {}.".format(member.name, member.memory.role),
            members,
            target
        )


kiting_order = [RANGED_ATTACK, HEAL]


def run_kiting_pair(home, members, target):
    """
    :type home: rooms.room_mind.RoomMind
    :type members: list[creeps.roles.squads.SquadDrone]
    :type target: position_management.locations.Location
    """

    if len(members) > 1:
        members = _.sortByAll(members, lambda x: kiting_order.index(x.findSpecialty()), 'name')
    last_pos = members[len(members) - 1].pos
    if last_pos.roomName == target.roomName and not movement.is_edge_position(last_pos) \
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
            target,
            do_things,
        )
        if result and not do_things:
            do_things = True
    if do_things:
        move_to_single_file(home, members, members[0], True, not members[0].__moved)  # kind of a hack
    else:
        move_to_single_file(home, members, target)


squad_run_funcs = {
    SQUAD_DUAL_SCOUTS: run_scout_squad,
    SQUAD_4_SCOUTS: run_scout_squad,
    SQUAD_DUAL_ATTACK: run_small_single_file_offense,
    SQUAD_DISMANTLE_RANGED: run_small_single_file_offense,
    SQUAD_TOWER_DRAIN: run_small_single_file_offense,
    SQUAD_KITING_PAIR: run_kiting_pair,
}
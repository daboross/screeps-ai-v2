import math

from cache import volatile_cache
from constants import INVADER_USERNAME, RAMPART_DEFENSE, REMOTE_MINE, SK_USERNAME, rmem_key_building_priority_walls, \
    rmem_key_currently_under_siege, rmem_key_defense_mind_storage, rmem_key_stored_hostiles, role_miner, \
    role_wall_defender
from jstools.js_set_map import new_map, new_set
from jstools.screeps import *
from position_management import flags, locations
from utilities import hostile_utils, movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def _init_tough_part_multipliers():
    # This was the original code. We're now creating a constant in order to skip directly to
    # math.ceil(part.hits * MULTIPLIERS[part.boost])
    # prevented = 1 - BOOSTS[TOUGH][part.boost]['damage']
    # effective_hits = math.ceil(part.hits * (1 / prevented))
    result = {}
    input_obj = BOOSTS[TOUGH]
    for boost in Object.keys(input_obj):
        result[boost] = 1 / (1 - input_obj[boost].damage)
    return result


TOUGH_HIT_MULTIPLIERS = _init_tough_part_multipliers()


def tower_damage(range):
    """
    Gets the damage a tower will inflict by using attack() on a target at a given linear distance.

    :param range: The distance away
    :return: An integer attack damage
    :type range: int
    :rtype: int
    """
    if range > 20:
        return 150
    elif range < 5:
        return 600
    return (25 - range) * 30


def poll_hostiles(hive, run_away_checks):
    """
    Iterates through all visible rooms, adding any hostiles found to memory.

    :param hive: The hive mind to iterate through visible rooms of
    :type hive: empire.hive.HiveMind
    :param run_away_checks: A function of RoomMind to call for each room with hostiles in it
    :type run_away_checks: callable(RoomMind)
    """
    if 'hostiles' not in Memory:
        Memory.hostiles = {}
    for room in hive.visible_rooms:
        if hostile_utils.enemy_using_room(room.name):
            continue
        targets = room.defense.dangerous_hostiles()
        if len(targets):
            danger = []
            for c in targets:
                store = {
                    'user': c.owner.username,
                    'pos': c.pos.x | c.pos.y << 6,
                    'room': c.pos.roomName,
                    'id': c.id,
                    'death': Game.time + c.ticksToLive,
                    'ranged': c.getActiveBodyparts(RANGED_ATTACK),
                    'attack': c.getActiveBodyparts(ATTACK),
                    'heal': c.getActiveBodyparts(HEAL),
                    'offensive': hostile_utils.is_offensive(c),
                }
                danger.push(store)
                Memory.hostiles[c.id] = store
            if rmem_key_stored_hostiles not in room.mem:
                if room.my:
                    room.reset_planned_role()
                else:
                    for flag in flags.find_flags(room, REMOTE_MINE):
                        sponsor = hive.get_room(flags.flag_sponsor(flag))
                        if sponsor:
                            sponsor.reset_planned_role()
            room.mem[rmem_key_stored_hostiles] = danger
            run_away_checks(room)
        elif room.name in Memory.rooms:
            del room.mem[rmem_key_stored_hostiles]
            if not len(room.mem):
                del Memory.rooms[room.name]


def cleanup_stored_hostiles():
    """
    Iterates through all hostile information stored in memory, removing any which are known to be dead.
    """
    for key, hostile in _.pairs(Memory.hostiles):
        if hostile.death <= Game.time:
            del Memory.hostiles[key]
    for name, mem in _.pairs(Memory.rooms):
        if 'danger' in mem:
            danger = mem.danger
            i = 0
            while i < danger.length:
                if danger[i].id in Memory.hostiles:
                    i += 1
                else:
                    danger.splice(i, 1)
            if not len(danger):
                del mem.danger
                if not len(mem):
                    del Memory.rooms[name]


def does_need_urgent_repair(s):
    return (s.structureType == STRUCTURE_ROAD and
            (s.hits < ROAD_DECAY_AMOUNT * 3
             or (Game.map.getTerrainAt(s.pos.x, s.pos.y, s.pos.roomName) == 'swamp'
                 and s.hits < ROAD_DECAY_AMOUNT
                 * CONSTRUCTION_COST_ROAD_SWAMP_RATIO * 3))) \
           or (s.structureType == STRUCTURE_RAMPART and s.hits < RAMPART_DECAY_AMOUNT * 3)


def stored_hostiles_near(room_name):
    """
    Finds all hostile information stored in memory in rooms adjacent to the given room, and in the given room itself.

    Returns a list of hostiles defined by the following format:

        [
            {
                'user': c.owner.username,
                'pos': c.pos.x | c.pos.y << 6,
                'room': c.pos.roomName,
                'id': c.id,
                'death': Game.time + c.ticksToLive,
                'ranged': c.getActiveBodyparts(RANGED_ATTACK),
                'attack': c.getActiveBodyparts(ATTACK),
                'offensive': attack or ranged_attack active or inactive in c.body
            }, # ...
        ]

    :param room_name: The center of the search.
    :return: A list of hostiles in the searched rooms.
    :type room_name: str
    :rtype: list[dict[str, str | int]]
    """
    cache = volatile_cache.mem("stored_hostiles_near")
    if cache.has(room_name):
        return cache.get(room_name)
    room_x, room_y = movement.parse_room_to_xy(room_name)
    if room_x == 0 and room_y == 0 and room_name == 'sim':
        return stored_hostiles_in(room_name)
    result = []
    # TODO: profile this against Game.map.describeExits (which does basically the same thing + a bit more)
    for x in range(room_x - 1, room_x + 2):
        for y in range(room_y - 1, room_y + 2):
            name = movement.room_xy_to_name(x, y)
            mem = Memory.rooms[name]
            if mem is not undefined and 'danger' in mem:
                for c in mem.danger:
                    if Game.time < c.death:
                        result.push(c)
    cache.set(room_name, result)
    return result


def stored_hostiles_in(room_name):
    """
    Finds all hostile information stored about hostiles in the given room name.

    Returns a list of hostiles defined by the following format:

        [
            {
                'user': c.owner.username,
                'pos': c.pos.x << 6 | c.pos.y,
                'room': c.pos.roomName,
                'id': c.id,
                'death': Game.time + c.ticksToLive,
                'ranged': c.getActiveBodyparts(RANGED_ATTACK),
                'attack': c.getActiveBodyparts(ATTACK),
                'offensive': attack or ranged_attack active or inactive in c.body
            }, # ...
        ]

    :param room_name: The room to search for hostiles in.
    :return: A list of hostiles in the searched room.
    :type room_name: str
    :rtype: list[dict[str, str | int]]
    """
    cache = volatile_cache.mem("stored_hostiles_in")
    if cache.has(room_name):
        return cache.get(room_name)
    result = []
    mem = Memory.rooms[room_name]
    if mem is not undefined and 'danger' in mem:
        for c in mem.danger:
            if Game.time < c.death:
                result.push(c)
        if not len(result):
            del mem.danger
    cache.set(room_name, result)
    return result


class RoomDefense:
    """
    Attack mitigation, on a room-by-room basis.

    :type room: rooms.room_mind.RoomMind
    :type hive: empire.hive.HiveMind
    :type _cache: jstools.js_set_map.JSMap
    """

    def __init__(self, room):
        self.room = room
        self._cache = new_map()
        if self.room.my:
            self.mem = self.room.mem[rmem_key_defense_mind_storage]
            if self.mem == undefined:
                self.mem = self.room.mem[rmem_key_defense_mind_storage] = {}

    __pragma__('fcall')

    def _hive(self):
        return self.room.hive

    hive = property(_hive)

    def all_hostiles(self):
        """
        Finds all hostile creeps (whether dangerous or not) in the current room.

        :return: A list of hostile creeps.
        :rtype: list[Creep]
        """
        return self.room.find(FIND_HOSTILE_CREEPS)

    def any_broken_walls(self):
        """
        Polls to see if there are any locations which should have walls on them, which don't.

        :return: True if there are any broken walls, False otherwise
        :rtype: bool
        """
        if self._cache.has('any_broken_walls'):
            return self._cache.get('any_broken_walls')
        else:
            broken = False
            if self.room.being_bootstrapped() and not self.room.mem[rmem_key_building_priority_walls]:
                broken = True
            else:
                for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_WALL) \
                        .concat(flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_RAMPART)):
                    if not _.find(flag.pos.lookFor(LOOK_STRUCTURES),
                                  lambda s: s.structureType == STRUCTURE_WALL
                                  or s.structureType == STRUCTURE_RAMPART):
                        broken = True
                        break
            self._cache.set('any_broken_walls', broken)
            return broken

    def this_room_mining_ops(self):
        if self._cache.has("this_room_mining_ops"):
            return self._cache.get("this_room_mining_ops")
        else:
            any_ops = not not _.find(flags.find_flags(self, REMOTE_MINE),
                                     lambda f: f.memory.active)
            self._cache.set("this_room_mining_ops", any_ops)
            return any_ops

    def healing_possible_on(self, hostile):
        """
        Looks for enemy healers directly around a hostile, and adds up the possible damage restored if all healers
        were to heal the given creep.

        If this method is run twice on the same hostile object, a value cached on the hostile itself will be returned
        instead of a new calculation.

        :param hostile: The hostile to
        :return:
        """
        if '_possible_heal' in hostile:
            return hostile._possible_heal
        else:
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 3)
            healing_possible = 0
            for obj in nearby:
                creep = obj.creep
                distance = movement.chebyshev_distance_room_pos(hostile, creep)
                if distance <= 1:
                    healing_possible += creep.getActiveBodypartsBoostEquivalent(HEAL, 'heal') * HEAL_POWER
                else:
                    healing_possible += creep.getActiveBodypartsBoostEquivalent(HEAL, 'rangedHeal') * RANGED_HEAL_POWER
            hostile._possible_heal = healing_possible
            return healing_possible

    def defenders_near(self, hostile):
        if '_defenders_near' in hostile:
            return hostile._defenders_near
        else:
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 1)
            result = _.filter(nearby, lambda c: c.creep.my and c.creep.hasActiveBodyparts(ATTACK)
                                                and _.find(c.creep.pos.lookFor(LOOK_STRUCTURES),
                                                           lambda s: s.structureType == STRUCTURE_RAMPART))
            hostile._defenders_near = result
            return result

    def any_attack_invaders(self):
        if self._cache.has('_attack_invaders'):
            return self._cache.get('_attack_invaders')
        else:
            any_attack_invaders = _.some(
                self.all_hostiles(),
                lambda h: h.owner.username == INVADER_USERNAME and (h.hasBodyparts(ATTACK)
                                                                    or h.hasBodyparts(RANGED_ATTACK)))
            self._cache.set('_attack_invaders', any_attack_invaders)
            return any_attack_invaders

    def hostile_users(self):
        if self._cache.has('_hostile_users'):
            return self._cache.get('_hostile_users')
        else:
            hostile_users = _(self.all_hostiles()).filter(
                lambda h: h.hasBodyparts(ATTACK) or h.hasBodyparts(RANGED_ATTACK) or h.getActiveBodyparts(
                    HEAL) or h.hasBodyparts(TOUGH)).pluck('owner.username').unique().value()
            self._cache.set('_hostile_users', hostile_users)
            return hostile_users

    def _calc_danger_level(self, hostile):
        """
        Internal function to calculate the raw danger level of a hostile. Use DefenseMind.danger_level(hostile) for a
        cached version instead.

        :param hostile: Hostile to check
        :return: The integer danger level, from 0 (safe) to 5 (attack NOW!)

        :type hostile: Creep
        :rtype: int
        """
        under_siege = self.room.mem[rmem_key_currently_under_siege]
        user = hostile.owner.username
        owner_hostile = self.hostile_users().includes(user)
        if user == INVADER_USERNAME:
            if not hostile.hasBodyparts(ATTACK) and not hostile.hasBodyparts(RANGED_ATTACK):
                if self.any_attack_invaders():
                    return 0.3
                else:
                    return 0
            else:
                return 2
        elif user == SK_USERNAME:
            return 0
        elif Memory.meta.friends.includes(user.toLowerCase()):
            return 0
        elif hostile.my:
            return 0
        elif self.room.my:
            structs_near = _.some(self.room.look_for_in_area_around(LOOK_STRUCTURES, hostile, 1),
                                  lambda s: s.structure.structureType == STRUCTURE_RAMPART
                                            or s.structure.structureType == STRUCTURE_WALL
                                            or s.structure.structureType == STRUCTURE_TOWER
                                            or s.structure.structureType == STRUCTURE_SPAWN)
            if structs_near and hostile.hasBodyparts(WORK):
                return 100 + hostile.getActiveBodyparts(WORK) * DISMANTLE_POWER
            elif structs_near and hostile.hasBodyparts(ATTACK):
                return 100 + hostile.getActiveBodyparts(ATTACK) * ATTACK_POWER
            elif hostile.hasActiveBodyparts(RANGED_ATTACK):
                if under_siege:
                    return 10.04
                else:
                    return 10
            elif hostile.hasBodyparts(ATTACK) or hostile.hasBodyparts(RANGED_ATTACK):
                if (self.any_broken_walls() or structs_near or
                        _.find(self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 1),
                               lambda obj: obj.creep.my)):
                    if under_siege:
                        return 10.07
                    else:
                        return 7
                else:
                    if under_siege:
                        return 10.05
                    else:
                        return 5
            elif hostile.hasBodyparts(WORK):
                if under_siege:
                    return 10.04
                else:
                    return 5
            elif 1 < hostile.pos.x < 48 and 1 < hostile.pos.y < 48:
                return 0.2
            else:
                return 0
        else:
            if hostile.hasActiveBodyparts(RANGED_ATTACK):
                return 4
            elif hostile.hasActiveBodyparts(ATTACK):
                return 1
            elif _.find(hostile.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK):
                return 0.7
            elif (hostile.hasBodyparts(CARRY) or hostile.hasBodyparts(WORK)) and self.this_room_mining_ops():
                return 0.5
            elif hostile.hasActiveBodyparts(TOUGH):
                return 0.3
            else:
                return 0

    def danger_level(self, hostile):
        """
        Calculates the danger level of a hostile, cached per hostile.

        Danger levels:

        0: Safe, no threat to any creeps - don't attack
        1: Might become a threat in the future, but not an immediate threat - attack sparingly
        2: Definitely a threat, but not the highest priority - run away from, and attack sparingly
        3: Immediate threat, attack and run from.
        4: Not necessarily immediate, but has RANGED_ATTACK parts so attack freely anyway
        5: WORK or ATTACK creep which is currently next to one of our structures. Attack NOW!

        :param hostile: Hostile to check
        :return: The integer danger level, from 0 (safe) to 5 (attack NOW!)

        :type hostile: Creep
        :rtype: int
        """
        if self._cache.has(hostile.id):
            return self._cache.get(hostile.id)
        else:
            danger_level = self._calc_danger_level(hostile)
            self._cache.set(hostile.id, danger_level)
            return danger_level

    def dangerous_hostiles(self):
        """
        Finds all hostiles in the current room with a danger_level of one or greater - cached per-tick per-room.

        If the room is owned, all returned hostiles are sorted first by highest danger level, then by lowest distance
        from spawn/towers, then by least (hits left + possible heal around).

        If the room is owned by an enemy, an empty list is unconditionally returned.

        :return: A list of hostiles
        :rtype: list[Creep]
        """
        if self._cache.has('active_hostiles'):
            return self._cache.get('active_hostiles')
        elif self.room.enemy:
            hostiles = []
            self._cache.set('active_hostiles', hostiles)
            return hostiles
        else:
            if self.room.my and self.room.room.controller.safeMode > 1000:
                hostiles = []
            else:
                hostiles = self.all_hostiles()
            if len(hostiles):
                if self.room.my:
                    protect = self.room.spawns.concat(self.towers())
                    if self.room.room.storage:
                        protect.push(self.room.room.storage)
                    if not len(protect):
                        protect.push(movement.center_pos(self.room.name))
                    hostiles = _(hostiles) \
                        .filter(self.danger_level) \
                        .sortBy(lambda c:
                                # Higher danger level = more important
                                - self.danger_level(c) * 5000
                                # More defenders = more important
                                - len(self.defenders_near(c)) * 500
                                # Further away from closest target = less important
                                + movement.minimum_chebyshev_distance(c, protect)
                                # Further away average distance from targets = less important
                                + self.healing_possible_on(c) * 300
                                # More hits = less important
                                + _.sum(protect, lambda s: movement.chebyshev_distance_room_pos(c, s)) / len(protect)
                                  / 50
                                - (c.hitsMax - c.hits) / c.hitsMax / 100
                                ) \
                        .value()
                    if self.mem.debug:
                        print("Chose hostiles:\n{}".format(
                            '\n'.join(
                                ["{},{}: {}, {}, {}, {}, {}".format(
                                    c.pos.x, c.pos.y,

                                    # Higher danger level = more important
                                    - self.danger_level(c) * 5000,
                                    # More defenders = more important
                                    - len(self.defenders_near(c)) * 500,
                                    # Further away from closest target = less important
                                    + movement.minimum_chebyshev_distance(c, protect),
                                    # Further away average distance from targets = less important
                                    + _.sum(protect, lambda s: movement.chebyshev_distance_room_pos(c, s)) / len(
                                        protect) / 50,
                                    # More hits = less important
                                    - (c.hitsMax - c.hits + self.healing_possible_on(c)) / c.hitsMax / 100,
                                ) for c in hostiles]
                            )
                        ))
                else:
                    hostiles = _.filter(hostiles, self.danger_level)
            self._cache.set('active_hostiles', hostiles)
            return hostiles

    __pragma__('nofcall')

    def remote_hostiles(self):
        """
        Searches for all stored hostile info in remote mining rooms and subsidiaries of this room. This method does
        not find hostiles in this room, and is cached per DefenseMind.

        Each hostile in the returned list is defined by the following format:


            {
                'user': c.owner.username,
                'pos': c.pos.x << 6 | c.pos.y,
                'room': c.pos.roomName,
                'id': c.id,
                'death': Game.time + c.ticksToLive,
                'ranged': c.getActiveBodyparts(RANGED_ATTACK),
                'attack': c.getActiveBodyparts(ATTACK),
                'offensive': attack or ranged_attack active or inactive in c.body
            }


        :return: A list of hostiles
        :rtype: list[dict[str, str | int]]
        """

        if self._cache.has('remote_active_hostiles'):
            return self._cache.get('remote_active_hostiles')
        else:
            hostile_lists = []
            checked_rooms = new_set()
            for room in self.room.subsidiaries:
                # Do this instead of an active check so that all returned hostiles have the same format!
                hostiles = stored_hostiles_in(room.name)
                if len(hostiles):
                    hostile_lists.push(hostiles)
                checked_rooms.add(room.name)
            for flag in self.room.mining.active_mines:
                if flag.pos.roomName != self.room.name and not checked_rooms.has(flag.pos.roomName):
                    hostiles = stored_hostiles_in(flag.pos.roomName)
                    if len(hostiles):
                        hostile_lists.push(hostiles)
            if len(hostile_lists):
                hostiles = __pragma__('js', 'Array.prototype.concat.apply')([], hostile_lists)
            else:
                hostiles = hostile_lists  # Reuse an allocation! :D
            self._cache.set('remote_active_hostiles', hostiles)
            return hostiles

    def activate_live_defenses(self):
        if not self.room.mem[rmem_key_currently_under_siege]:
            self.room.mem[rmem_key_currently_under_siege] = True
            self.room.reset_spending_state()
            self.hive.states.calculate_room_states()
        self.mem.attack_until = Game.time + 2000
        self.room.reset_planned_role()
        message = "{} activating live defenses.".format(self.room.name)
        Game.notify(message)
        console.log(message)
        self.set_protection_all_walls()

    def set_protection_all_walls(self):
        all_nearby_hostiles = stored_hostiles_near(self.room.name)
        protect = new_map()

        if not len(all_nearby_hostiles):
            enemy_positions = [positions.deserialize_xy_to_pos(enemy.pos, enemy.room)
                               for enemy in all_nearby_hostiles]
        else:
            enemy_positions = self.room.find(FIND_EXIT)
        already_checked = []
        for enemy in enemy_positions:
            if _.some(already_checked, lambda x: movement.chebyshev_distance_room_pos(x, enemy) <= 4):
                continue
            already_checked.append(enemy)

            path_obj = self.hive.honey.find_path(enemy, self.room.spawn, {
                'use_roads': False,
                'ignore_swamp': True,
                'current_room': self.room.name
            })
            for position in path_obj:
                is_rampart = False
                is_other = False
                for struct in self.room.look_at(LOOK_STRUCTURES, position.x, position.y):
                    if struct.structureType == STRUCTURE_RAMPART:
                        is_rampart = True
                    elif struct.structureType != STRUCTURE_ROAD and struct.structureType != STRUCTURE_CONTAINER:
                        is_other = True  # Don't assign defender creeps to say, ramparts over spawns.
                if is_rampart and not is_other:
                    for creep in self.room.look_at(LOOK_CREEPS, position.x, position.y):
                        if creep.memory.role == role_miner:
                            is_other = True
                            break
                    if not is_other:
                        protect.set(positions.serialize_pos_xy(position), 0)
        current_iteration = Array.js_from(protect.entries())
        print("[defense] Found inital walls: {} from {} paths".format(len(current_iteration), len(already_checked)))
        while True:
            next_iteration = []
            for origin_xy, priority in current_iteration:
                origin_x = origin_xy & 0x3F
                origin_y = origin_xy >> 6 & 0x3F
                new_priority = priority + 1
                for x in range(origin_x - 1, origin_x + 2):
                    for y in range(origin_y - 1, origin_y + 2):
                        serialized = positions.serialize_xy(x, y)
                        if protect.has(serialized):
                            continue
                        is_rampart = False
                        is_wall = False
                        is_other = False
                        for struct in self.room.look_at(LOOK_STRUCTURES, x, y):
                            if struct.structureType == STRUCTURE_RAMPART:
                                is_rampart = True
                            elif struct.structureType == STRUCTURE_WALL:
                                is_wall = True
                                is_other = True
                            elif struct.structureType != STRUCTURE_ROAD and struct.structureType != STRUCTURE_CONTAINER:
                                is_other = True  # Don't assign defender creeps to say, ramparts over spawns.

                        if is_wall or is_rampart:
                            if is_rampart and not is_other:
                                protect.set(serialized, new_priority)
                            if new_priority < 5:
                                next_iteration.append([serialized, new_priority])
            if len(next_iteration):
                current_iteration = next_iteration
            else:
                break

        if self.mem.known_locations:
            for name in self.mem.known_locations:
                locations.delete_location(name)
            del self.mem.known_locations
        self._cache.delete('live_defender_spots')
        self.room.delete_cached_property('rcrnd')  # recently calculated ramparts needing defense

        spots = []
        hot = []
        cold = []
        for pos, priority in _.sortBy(Array.js_from(protect.entries()), lambda x: x[1]):
            loc = locations.create(pos)
            spots.push(loc.name)
            if priority <= 1:
                hot.push(loc.name)
            else:
                cold.push(loc.name)
        print("[{}][defense] Found {} ramparts to protect during initial seed.".format(
            self.room.name, len(spots)))
        self.mem.known_locations = spots
        self.room.store_cached_property('rcrnd', [hot, cold], 50)

    def towers(self):
        if self._cache.has('towers'):
            return self._cache.get('towers')
        else:
            towers = _.filter(self.room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_TOWER})
            self._cache.set('towers', towers)
            return towers

    def healing_capable(self):
        return len(self.towers())

    def set_ramparts(self, defensive):
        for rampart in _.filter(self.room.find(FIND_STRUCTURES), {"structureType": STRUCTURE_RAMPART}):
            if defensive or _.find(self.room.look_at(LOOK_STRUCTURES, rampart.pos),
                                   lambda s: s.structureType != STRUCTURE_RAMPART
                                   and s.structureType != STRUCTURE_ROAD):
                rampart.setPublic(False)
            else:
                rampart.setPublic(True)

    def tower_heal(self):
        damaged = _.filter(self.room.find(FIND_MY_CREEPS), lambda c: c.hits < c.hitsMax)
        if len(damaged):
            towers = _.filter(self.towers(), lambda x: x.energy)
            if not len(towers):
                return
            if len(damaged) > 1 and len(towers) > 1:
                for creep in _.sortBy(damaged, 'hits'):  # heal the highest health creeps first.
                    if len(towers) == 1:
                        towers[0].heal(creep)
                        break
                    elif len(towers) < 1:
                        break
                    else:
                        closest_distance = Infinity
                        closest_index = -1
                        for i in range(0, len(towers)):
                            distance = movement.chebyshev_distance_room_pos(creep.pos, towers[i].pos)
                            if distance < closest_distance:
                                closest_index = i
                                closest_distance = distance
                        tower = towers.splice(closest_index, 1)[0]
                        tower.heal(creep)
            elif len(damaged) > 1:
                towers[0].heal(_.min(damaged, lambda c: movement.chebyshev_distance_room_pos(c, towers[0])))
            else:
                towers[0].heal(damaged[0])
        elif Game.time % 7 == 0:
            urgent_repair = _.find(self.room.find(FIND_STRUCTURES), does_need_urgent_repair)
            if urgent_repair:
                for tower in self.towers():
                    tower.repair(urgent_repair)

    def alert(self):
        if self._cache.has('alert'):
            return self._cache.get('alert')
        else:
            alert = self.mem.alert
            if not alert and (self.room.my or Game.time % 3 == 1) and len(self.all_hostiles()):
                self.set_ramparts(True)
                self.mem.alert = alert = True
            self._cache.set('alert', alert)
            return alert

    def tick(self):
        if Game.time % 6 == 0 and not len(self.room.spawns) \
                and not self.room.being_bootstrapped() \
                and not _.find(self.room.find(FIND_MY_CONSTRUCTION_SITES), {'structureType': STRUCTURE_SPAWN}):
            self.room.building.refresh_building_targets(True)
            self.room.building.get_construction_targets()

        alert = self.alert()

        if not alert:
            if Game.time % 100 == 69:
                self.set_ramparts(False)
                if self.room.mem[rmem_key_currently_under_siege]:
                    if self.mem.attack_until:
                        if Game.time > self.mem.attack_until:
                            del self.room.mem[rmem_key_currently_under_siege]
                            del self.mem.attack_until
                            message = "{}: disabling active defenses.".format(self.room.name)
                            Game.notify(message)
                            console.log(message)
                    else:
                        self.mem.attack_until = Game.time + 2000
            self.tower_heal()
            return

        if self.room.mem[rmem_key_currently_under_siege] \
                and _.some(self.all_hostiles(), lambda h: h.owner.username != INVADER_USERNAME):
            self.mem.attack_until = Game.time + 2000

        if Game.time % 5 == 1:
            if not self.room.being_bootstrapped() or self.room.mem[rmem_key_building_priority_walls]:
                for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_RAMPART) \
                        .concat(flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_WALL)):
                    wall = _.find(self.room.room.lookForAt(LOOK_STRUCTURES, flag),
                                  lambda s: s.structureType == STRUCTURE_WALL or s.structureType == STRUCTURE_RAMPART)
                    if not wall:
                        if len(self.room.find(FIND_MY_CONSTRUCTION_SITES)) < 15 \
                                and not _.find(self.room.room.lookForAt(LOOK_CONSTRUCTION_SITES, flag),
                                               lambda s: s.structureType == STRUCTURE_WALL
                                               or s.structureType == STRUCTURE_RAMPART):
                            self.room.building.refresh_building_targets(True)
                    elif wall.hits < self.room.get_min_sane_wall_hits:
                        self.room.building.refresh_repair_targets(True)
                self.room.building.get_construction_targets()

        if not len(self.all_hostiles()):
            if not (self.mem.alert_for < 0):
                self.mem.alert_for = 0
            self.mem.alert_for -= 1
            if self.mem.alert_for < -5:
                self.set_ramparts(False)
                del self.mem.alert_for
                del self.mem.alert
            return

        if self.mem.alert_for > 0:
            self.mem.alert_for += 1
        else:
            self.mem.alert_for = 1

        hostiles = self.dangerous_hostiles()
        towers = _.filter(self.towers(), lambda x: x.energy)

        if len(hostiles) and (len(towers) or self.room.spawn):
            print("[{}][defense] Found danger:{}".format(
                self.room.name, ["\n(a: {}, h: {}, w: {}, r: {}, hits: {}%, pos: {},{}, prio: {})"
                                     .format(h.getActiveBodyparts(ATTACK),
                                             h.getActiveBodyparts(HEAL),
                                             h.getActiveBodyparts(WORK),
                                             h.getActiveBodyparts(RANGED_ATTACK),
                                             round(h.hits / h.hitsMax * 100),
                                             h.pos.x, h.pos.y,
                                             self.danger_level(h)) for h in hostiles].join('')))

        if len(towers):
            if Game.time % 3 == 1:
                damaged_warriors = _.filter(self.room.find(FIND_MY_CREEPS),
                                            lambda c: c.hasBodyparts(ATTACK) and c.hits < c.hitsMax)
                if len(damaged_warriors):
                    for tower in towers:
                        tower.heal(damaged_warriors[0])

            tower_index = 0
            some_left = False
            for hostile in hostiles:
                # TODO: healer confusing logic here?
                healing_possible = self.healing_possible_on(hostile)
                nearby_defenders = self.defenders_near(hostile)
                attack_possible = _.sum(nearby_defenders, lambda c: (not c.creep.defense_override
                                                                     and c.creep.getActiveBodyparts(ATTACK)) or 0) \
                                  * ATTACK_POWER \
                                  + _.sum(towers.slice(tower_index),
                                          lambda t: tower_damage(t.pos.getRangeTo(hostile)))
                if hostile.hasActiveBoostedBodyparts(TOUGH):
                    damage_to_account_for = attack_possible
                    for part in hostile.body:
                        if part.hits <= 0:
                            continue
                        if damage_to_account_for <= 0:
                            break
                        if part.boost is undefined or part.type != TOUGH:
                            damage_to_account_for -= part.hits
                            continue
                        # prevented = 1 - BOOSTS[TOUGH][part.boost]['damage']
                        # effective_hits = math.ceil(part.hits * (1 / prevented))
                        effective_hits = math.ceil(part.hits * TOUGH_HIT_MULTIPLIERS[part.boost])
                        if js_isNaN(effective_hits):
                            print("effective hits for boost {} is NaN.".format(part.boost))
                            effective_hits = part.hits
                        # If we will fully destroy this part, there's no need to do partial-destruction logic
                        if effective_hits <= damage_to_account_for:
                            damage_to_account_for -= effective_hits
                            # since we fully destroy it, just subtract how much extra damage is absorbed
                            attack_possible -= (effective_hits - part.hits)
                        else:
                            # This is the last part, and we're partially destroying it, which means... ratios!
                            actually_destroyed = math.floor((effective_hits - damage_to_account_for)
                                                            / effective_hits
                                                            * part.hits)
                            attack_possible = damage_to_account_for - actually_destroyed
                            break  # No need to zero out damage_to_account_for here, as we're done

                if healing_possible > attack_possible:
                    # TODO: request a rampart defender if this is next to a rampart and there's a small enough gap
                    #  between damage/healing power!
                    print("[{}] Not attacking hostile at {}: {} heal possible, {} damage possible."
                          .format(self.room.name, hostile.pos, healing_possible, attack_possible))
                    some_left = True
                    continue
                else:
                    print("[{}] Attacking hostile at {}: {} heal possible, {} damage possible."
                          .format(self.room.name, hostile.pos, healing_possible, attack_possible))
                for my_defender in nearby_defenders:
                    my_defender.creep.attack(hostile)
                    my_defender.creep.defense_override = True
                hits_left = hostile.hits + healing_possible
                while tower_index < len(towers) and hits_left > 0:
                    tower = towers[tower_index]
                    tower_index += 1
                    tower.attack(hostile)
                    hits_left -= tower_damage(tower.pos.getRangeTo(hostile))
                if tower_index >= len(towers):
                    some_left = True
                    break
            if some_left:
                self.check_for_noninvader_raid()
        elif self.room.spawn:
            self.check_for_noninvader_raid()

    def check_for_noninvader_raid(self):
        if self.room.mem[rmem_key_currently_under_siege]:
            return
        total_noninvader = 0
        hostiles = self.dangerous_hostiles()
        user = None
        for hostile in hostiles:
            if hostile.owner.username != INVADER_USERNAME:
                user = hostile.owner.username
                for part in hostile.body:
                    if part.type == ATTACK:
                        if part.boost:
                            total_noninvader += _.get(BOOSTS, [ATTACK, part.boost, 'attack'], 1)
                        else:
                            total_noninvader += 1
                    elif part.type == RANGED_ATTACK:
                        if part.boost:
                            total_noninvader += _.get(BOOSTS, [RANGED_ATTACK, part.boost, 'rangedAttack'], 1)
                        else:
                            total_noninvader += 1
                    elif part.type == HEAL:
                        if part.boost:
                            total_noninvader += _.get(BOOSTS, [HEAL, part.boost, 'heal'], 1) * 2
                        else:
                            total_noninvader += 2
                    elif part.type == WORK:
                        if part.boost:
                            total_noninvader += _.get(BOOSTS, [WORK, part.boost, 'dismantle'], 1)
                        else:
                            total_noninvader += 0.5
        if total_noninvader >= 10:
            message = (
                "\nDANGER: -----"
                "\nOver 10 hostile player bodyparts detected directly in {}. Game time: {}"
                "\n"
                "\nCreeps:"
                "\n{}"
                "\n"
                "\nThis has triggered active-defense mode in {}"
                "\nDANGER: -----"
            ).format(
                self.room.name, Game.time,
                "\n".join(["owner: {}, body: {}".format(h.owner.username, JSON.stringify(_.countBy(h.body, 'type')))
                           for h in hostiles if h.owner.username != INVADER_USERNAME]),
                self.room.name,
            )
            console.log(message)
            Game.notify(message)
            self.activate_live_defenses()

    def get_current_defender_spots(self):
        if self._cache.has('live_defender_spots'):
            return self._cache.get('live_defender_spots')
        cached = self.room.get_cached_property('rcrnd')  # recently calculated ramparts needing defense
        if cached:
            hot, cold = cached
            hot = _(hot).map(locations.get).filter().value()
            cold = _(cold).map(locations.get).filter().value()
            self._cache.set('live_defender_spots', [hot, cold])
            return hot, cold

        last_used = self.mem.kllu  # known locations last used
        if last_used == undefined:
            last_used = self.mem.kllu = {}
        if not len(self.dangerous_hostiles()):
            hot = []
            cold = []
            if self.mem.known_locations:
                to_remove = []
                for name in self.mem.known_locations:
                    location = locations.get(name)
                    if location is not None:
                        if name not in last_used:
                            last_used[name] = Game.time
                        elif Game.time - last_used[name] > 1500:
                            to_remove.push(name)
                        cold.push(location)
                if len(to_remove):
                    _.pull(self.mem.known_locations, to_remove)
                    if self.mem.ods:  # old defender spots
                        existing_old = new_set()
                        for name in self.mem.ods:
                            existing_old.add(locations.serialized(name))
                        for name in to_remove:
                            if not existing_old.has(locations.serialized(name)):
                                self.mem.ods.push(name)
                        if len(self.mem.ods) > len(self.room.role_count(role_wall_defender)):
                            self.mem.ods.splice(0, len(self.mem.ods)
                                                - len(self.room.role_count(role_wall_defender)))
                    else:
                        self.mem.ods = to_remove
            self.room.store_cached_property('rcrnd', [hot, cold], 30)
            self._cache.set('live_defender_spots', [hot, cold])
            return hot, cold
        serialized_locations = self.mem.known_locations

        hot_found = new_set()
        hot_spots = []
        cold_spots = []
        if serialized_locations != undefined:
            old_locs = []
            for name in serialized_locations:
                location = locations.get(name)
                if location:
                    nearby = self.room.look_for_in_area_around(LOOK_CREEPS, location, 1)
                    if _.some(nearby,
                              lambda x: not x.creep.my and not Memory.meta.friends.includes(x.creep.owner.username)):
                        hot_spots.append(location)
                        hot_found.add(positions.serialize_pos_xy(location))
                    else:
                        cold_spots.append(location)
                else:
                    old_locs.append(name)
            if len(old_locs):
                _.pull(serialized_locations, old_locs)
        else:
            serialized_locations = self.mem.known_locations = []
        ramparts_undefended = []  # Slow, but faster than lodash
        for rampart in self.room.find(FIND_MY_STRUCTURES):
            if rampart.setPublic:  # method only accessible for STRUCTURE_RAMPART, faster than checking structureType
                serialized = positions.serialize_pos_xy(rampart)
                if not hot_found.has(serialized):
                    is_other = False
                    for structure in self.room.look_at(LOOK_STRUCTURES, rampart):
                        if not structure.setPublic:
                            is_other = True
                    for creep in self.room.look_at(LOOK_CREEPS, rampart):
                        if creep.memory.role == role_miner:
                            is_other = True
                    if is_other:
                        continue
                    nearby = self.room.look_for_in_area_around(LOOK_CREEPS, rampart, 1)
                    total_offense = 0
                    for obj in nearby:
                        creep = obj.creep
                        if not creep.my and not Memory.meta.friends.includes(creep.owner.username.toLowerCase()):
                            offense = max(creep.getBodyparts(WORK) * DISMANTLE_POWER,
                                          creep.getBodyparts(ATTACK) * ATTACK_POWER)
                            if _.some(hot_spots, lambda x: movement.chebyshev_distance_room_pos(x, creep) <= 1):
                                offense /= 3
                            total_offense += offense
                    if total_offense:
                        ramparts_undefended.push([rampart, total_offense])
        # NOTE: This code may very well prioritize stocking multiple ramparts directly next to each other (all in range
        #  of a single creep), over defending all different points of invasion. However undesirable this is, it seems
        #  to be a reasonable behavior given that the alternative would use that much more CPU.
        # NOTE again: the above is only true if two creeps target during the same cache period.
        num_undefended = len(ramparts_undefended)
        if num_undefended:
            if num_undefended > 1 and len(cold_spots):
                ramparts_undefended = _.sortBy(ramparts_undefended, lambda x: x[1])
            for rampart, in ramparts_undefended:
                if len(cold_spots):
                    nearest = None
                    nearest_distance = Infinity
                    for spot in cold_spots:
                        distance = movement.chebyshev_distance_room_pos(spot, rampart)
                        if distance < nearest_distance:
                            nearest_distance = distance
                            nearest = spot
                    assert isinstance(nearest, locations.Location)
                    nearest.update(rampart.pos.x, rampart.pos.y, rampart.pos.roomName)
                    _.pull(cold_spots, [nearest])
                    hot_spots.append(nearest)
                else:
                    new_obj = locations.create(rampart, RAMPART_DEFENSE, 2000)
                    hot_spots.push(new_obj)
                    serialized_locations.push(new_obj.name)
        self._cache.set('live_defender_spots', [hot_spots, cold_spots])
        self.room.store_cached_property('rcrnd', [[s.name for s in hot_spots],
                                                  [s.name for s in cold_spots]], 3)
        for loc in hot_spots:
            last_used[loc.name] = Game.time
        return [hot_spots, cold_spots]

    def get_old_defender_spots(self):
        if self._cache.has('old_defender_spots'):
            return self._cache.get('old_defender_spots')
        result = []
        if self.mem.ods:  # old defender spots
            for name in self.mem.ods:
                loc = locations.get(name)
                if loc is not None:
                    result.push(loc)
        self._cache.set('old_defender_spots', result)
        return result

    broken_walls = property(any_broken_walls)

import flags
from constants import INVADER_USERNAME, SK_USERNAME
from tools import profiling
from utilities import movement, hostile_utils, volatile_cache
from utilities.screeps_constants import *
from utilities.screeps_constants import new_set

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


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


def poll_hostiles(hive):
    """
    Iterates through all visible rooms, adding any hostiles found to memory.

    :param hive: The hive mind to iterate through visible rooms of
    :type hive: control.hivemind.HiveMind
    """
    if 'hostiles' not in Memory:
        Memory.hostiles = {}
    for room in hive.visible_rooms:
        if hostile_utils.enemy_room(room.room_name):
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
                    'offensive': hostile_utils.is_offensive(c),
                }
                danger.push(store)
                Memory.hostiles[c.id] = store
            if 'danger' not in room.mem:
                if room.my:
                    room.reset_planned_role()
                else:
                    for flag in flags.find_flags(room, flags.REMOTE_MINE):
                        sponsor = hive.get_room(flag.memory.sponsor)
                        if sponsor:
                            sponsor.reset_planned_role()
            room.mem.danger = danger
        elif room.room_name in Memory.rooms:
            if 'danger' in room.mem:
                if room.my:
                    room.reset_planned_role()
                else:
                    for flag in flags.find_flags(room, flags.REMOTE_MINE):
                        sponsor = hive.get_room(flag.memory.sponsor)
                        if sponsor:
                            sponsor.reset_planned_role()
            del room.mem.danger


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
    cache = volatile_cache.mem("stored_hostiles_in")
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
    result = []
    mem = Memory.rooms[room_name]
    if mem is not undefined and 'danger' in mem:
        for c in mem.danger:
            if Game.time < c.death:
                result.push(c)
        if not len(result):
            del mem.danger
    return result


class RoomDefense:
    """
    Attack mitigation, on a room-by-room basis.

    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    :type _cache: utilities.screeps_constants.JSMap
    """

    def __init__(self, room):
        self.room = room
        self._cache = new_map()

    def _hive(self):
        return self.room.hive_mind

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
            any_ops = not not _.find(flags.find_flags(self, flags.REMOTE_MINE),
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
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 1)
            healing_possible = _.sum(nearby, lambda obj: not obj.creep.my and obj.creep.getActiveBodyparts(HEAL)) * 12
            hostile._possible_heal = healing_possible
            return healing_possible

    def defenders_near(self, hostile):
        if '_defenders_near' in hostile:
            return hostile._defenders_near
        else:
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 1)
            result = _.filter(nearby, lambda c: c.creep.my and c.creep.getActiveBodyparts(ATTACK))
            hostile._defenders_near = result
            return result

    def _calc_danger_level(self, hostile):
        """
        Internal function to calculate the raw danger level of a hostile. Use DefenseMind.danger_level(hostile) for a
        cached version instead.

        :param hostile: Hostile to check
        :return: The integer danger level, from 0 (safe) to 5 (attack NOW!)

        :type hostile: Creep
        :rtype: int
        """
        user = hostile.owner.username
        if user == INVADER_USERNAME:
            return 2
        elif user == SK_USERNAME:
            return 0
        elif Memory.meta.friends.includes(user):
            return 0
        elif self.room.my:
            structs_near = len(self.room.look_for_in_area_around(LOOK_STRUCTURES, hostile, 1))
            if structs_near and hostile.getActiveBodyparts(WORK):
                return 6
            elif structs_near and hostile.getActiveBodyparts(ATTACK):
                return 5
            elif hostile.getActiveBodyparts(RANGED_ATTACK):
                return 4
            elif hostile.getActiveBodyparts(ATTACK):
                if (self.any_broken_walls() or structs_near or
                        _.find(self.room.look_for_in_area_around(LOOK_CREEPS, hostile, 1),
                               lambda obj: obj.creep.my)):
                    return 3
                else:
                    return 2
            elif hostile.getActiveBodyparts(WORK):
                return 2
            elif 1 < hostile.pos.x < 48 and 1 < hostile.pos.y < 48:
                # Specifically for E17N55, so we don't attack haulers who have wondered just on the room boundary
                return 1
            else:
                return 0
        else:
            if hostile.getActiveBodyparts(RANGED_ATTACK):
                return 4
            elif hostile.getActiveBodyparts(ATTACK):
                return 1
            elif _.find(hostile.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK):
                return 0.7
            elif hostile.getActiveBodyparts(CARRY) or hostile.getActiveBodyparts(WORK) and self.this_room_mining_ops():
                return 0.5
            elif hostile.getActiveBodyparts(TOUGH):
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
        4: Not neccesarily immediate, but has RANGED_ATTACK parts so attack freely anyway
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

        If the room is owned, all returned hostiles are sorted first by highestdanger level, then by lowest distance
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
            hostiles = self.all_hostiles()
            if len(hostiles):
                if self.room.my:
                    protect = self.room.spawns.concat(self.towers())
                    if self.room.room.storage:
                        protect.push(self.room.room.storage)
                    # if len(protect):
                    #     center = movement.average_pos_same_room(protect)
                    # else:
                    #     center = __new__(RoomPosition(25, 25, self.room.room_name))
                    if not len(protect):
                        protect.push(__new__(RoomPosition(25, 25, self.room.room_name)))
                    hostiles = _(hostiles) \
                        .filter(self.danger_level) \
                        .sortBy(lambda c:
                                # Higher danger level = more important
                                - self.danger_level(c) * 200
                                # More defenders = more important
                                - len(self.defenders_near(c)) * 100
                                # Further away = less important
                                + _.sum(protect, lambda s: movement.chebyshev_distance_room_pos(c, s)) / len(protect)
                                # More hits = less important
                                - (c.hitsMax - c.hits - self.healing_possible_on(c)) / 50
                                ) \
                        .value()
                else:
                    hostiles = _.filter(hostiles, self.danger_level)
            self._cache.set('active_hostiles', hostiles)
            return hostiles

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
                hostiles = stored_hostiles_in(room.room_name)
                if len(hostiles):
                    hostile_lists.push(hostiles)
                checked_rooms.add(room.room_name)
            for flag in self.room.mining.active_mines:
                if flag.pos.roomName != self.room.room_name and not checked_rooms.has(flag.pos.roomName):
                    hostiles = stored_hostiles_in(flag.pos.roomName)
                    if len(hostiles):
                        hostile_lists.push(hostiles)
            if len(hostile_lists):
                hostiles = __pragma__('js', 'Array.prototype.concat.apply')([], hostile_lists)
            else:
                hostiles = hostile_lists  # Reuse an allocation! :D
            self._cache.set('remote_active_hostiles', hostiles)
            return hostiles

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
            towers = self.towers()
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
                            distance = movement.distance_squared_room_pos(creep.pos, towers[i].pos)
                            if distance < closest_distance:
                                closest_index = i
                                closest_distance = distance
                        tower = towers.splice(closest_index, 1)[0]
                        tower.heal(creep)
            elif len(damaged) > 1:
                towers[0].heal(_.min(damaged, lambda c: movement.distance_squared_room_pos(c, towers[0])))
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
            alert = self.room.mem.alert
            if not alert and (self.room.my or Game.time % 3 == 1) and len(self.all_hostiles()):
                self.set_ramparts(True)
                self.room.mem.alert = alert = True
            self._cache.set('alert', alert)
            return alert

    def tick(self):
        if Game.time % 6 == 0 and not len(self.room.spawns) \
                and not self.room.being_bootstrapped() \
                and not _.find(self.room.find(FIND_MY_CONSTRUCTION_SITES), {'structureType': STRUCTURE_SPAWN}):
            self.room.building.refresh_building_targets(True)
            self.room.building.next_priority_construction_targets()

        alert = self.alert()

        if not alert:
            if Game.time % 100 == 69:
                self.set_ramparts(False)
            self.tower_heal()
            return

        for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_RAMPART) \
                .concat(flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_WALL)):
            wall = _.find(self.room.room.lookForAt(LOOK_STRUCTURES, flag),
                          lambda s: s.structureType == STRUCTURE_WALL or s.structureType == STRUCTURE_RAMPART)
            if not wall:
                self.room.building.refresh_building_targets(True)
            elif wall.hits < self.room.get_min_sane_wall_hits:
                self.room.building.refresh_repair_targets(True)
        self.room.building.next_priority_construction_targets()

        if not len(self.all_hostiles()):
            if not (self.room.mem.alert_for < 0):
                self.room.mem.alert_for = 0
            self.room.mem.alert_for -= 1
            if self.room.mem.alert_for < -5:
                self.set_ramparts(False)
                del self.room.mem.alert_for
                self.room.mem.alert = False
            return

        if self.room.mem.alert_for > 0:
            self.room.mem.alert_for += 1
        else:
            self.room.mem.alert_for = 1

        hostiles = self.dangerous_hostiles()
        towers = self.towers()

        if len(hostiles) and (len(towers) or len(self.room.creeps) or self.room.spawn):
            print("[{}][defense] Found danger:{}".format(self.room.room_name,
                                                         ["\n(a: {}, h: {}, hits: {}%, pos: {},{})"
                                                         .format(h.getActiveBodyparts(ATTACK),
                                                                 h.getActiveBodyparts(HEAL),
                                                                 round(h.hits / h.hitsMax * 100),
                                                                 h.pos.x,
                                                                 h.pos.y) for h in hostiles]))

        if len(towers):
            tower_index = 0
            for hostile in hostiles:
                # TODO: healer confusing logic here?
                healing_possible = self.healing_possible_on(hostile)
                nearby_defenders = self.defenders_near(hostile)
                attack_possible = _.sum(nearby_defenders, lambda c: (not c.creep.defense_override
                                                                     and c.creep.getActiveBodyparts(ATTACK)) or 0) * 30 \
                                  + _.sum(towers.slice(tower_index),
                                          lambda t: tower_damage(t.pos.getRangeTo(hostile)))
                if healing_possible > attack_possible:
                    print("[{}] Not attacking hostile at {}: {} heal possible, {} damage possible."
                          .format(self.room.room_name, hostile.pos, healing_possible, attack_possible))
                    continue
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
                    break

    broken_walls = property(any_broken_walls)


profiling.profile_whitelist(RoomDefense, ["tick", "tower_heal"])

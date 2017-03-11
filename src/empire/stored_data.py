"""
Stored data!

Stores data in memory via room name keys, using the metadata module powered by Protocol Buffers to encode data.
"""
from constants import INVADER_USERNAME, SK_USERNAME
from constants.memkeys import global_mem_key_room_data
from jstools.js_set_map import new_map, new_set
from jstools.screeps import *
from position_management import flags
from utilities import positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

_cache_created = Game.time
_cached_data = new_map()


def _mem():
    mem = Memory[global_mem_key_room_data]
    if not mem:
        mem = Memory[global_mem_key_room_data] = {}
    return mem


def _get_serialized_data(room_name):
    return _mem()[room_name] or None


def _deserialize_data(data):
    # NOTE: this cache is only ever reset as a last resort, in normal operation the server should reset the global
    # before this is reached.
    global _cached_data, _cache_created
    if Game.time - _cache_created > 1000:
        _cached_data = new_map()
        _cache_created = Game.time
    deserialized = _cached_data.get(data)
    if deserialized:
        return deserialized
    deserialized = StoredRoom.decode(data)
    _cached_data.set(data, deserialized)
    return deserialized


def _set_new_data(room_name, data):
    _mem()[room_name] = encoded = data.encode()
    _cached_data.set(encoded, data)
    if not len(encoded):
        print("[storage] Warning: would have set empty data for room {}!".format(room_name))
        del _mem()[room_name]


_my_username = None


def get_my_username():
    global _my_username
    if _my_username is None:
        struct = _.find(Game.structures, 'my')
        _my_username = struct.owner.username
    return _my_username


def _find_obstacles(room):
    """
    :type room: Room
    :rtype: list[StoredObstacle]
    """
    result = []
    any_lairs = False
    for structure in room.find(FIND_STRUCTURES):
        orig_type = structure.structureType
        if orig_type == STRUCTURE_PORTAL or orig_type == STRUCTURE_CONTAINER:
            continue
        elif orig_type == STRUCTURE_RAMPART and structure.my:
            continue
        elif orig_type == STRUCTURE_ROAD:
            stored_type = StoredObstacleType.ROAD
        elif orig_type == STRUCTURE_CONTROLLER:
            stored_type = StoredObstacleType.CONTROLLER
        elif orig_type == STRUCTURE_KEEPER_LAIR:
            stored_type = StoredObstacleType.SOURCE_KEEPER_LAIR
            any_lairs = True
        else:
            stored_type = StoredObstacleType.OTHER_IMPASSABLE
        result.append(__new__(StoredObstacle(structure.pos.x, structure.pos.y, stored_type)))
    for source in room.find(FIND_SOURCES):
        if any_lairs:
            stored_type = StoredObstacleType.SOURCE_KEEPER_SOURCE
        else:
            stored_type = StoredObstacleType.SOURCE
        result.append(__new__(StoredObstacle(source.pos.x, source.pos.y, stored_type, source.energyCapacity)))
    for mineral in room.find(FIND_MINERALS):
        if any_lairs:
            stored_type = StoredObstacleType.SOURCE_KEEPER_MINERAL
        else:
            stored_type = StoredObstacleType.MINERAL
        result.append(__new__(StoredObstacle(mineral.pos.x, mineral.pos.y, stored_type)))
    return result


def _find_room_reservation_end(room):
    """
    :type room: Room
    :rtype: int
    """
    if room.controller and room.controller.reservation and room.controller.reservation.username == get_my_username():
        return Game.time + room.controller.reservation.ticksToEnd
    else:
        return 0


def _find_room_owner(room):
    """
    :type room: Room
    :rtype: StoredEnemyRoomOwner
    """
    name = None
    state = None
    controller = room.controller
    if controller:
        if controller.owner and not controller.my:
            name = controller.owner.username
            state = StoredEnemyRoomState.FULLY_FUNCTIONAL
        elif controller.reservation and controller.reservation.username != get_my_username():
            name = controller.reservation.username
            state = StoredEnemyRoomState.RESERVED

    if state is None:
        enemy_creeps = room.find(FIND_HOSTILE_CREEPS)
        if len(enemy_creeps):
            for source in room.find(FIND_SOURCES).concat(room.find(FIND_MINERALS)):
                near = _.find(enemy_creeps, lambda c: (c.owner.username != INVADER_USERNAME
                                                       and c.owner.username != SK_USERNAME
                                                       and c.hasActiveBodyparts(WORK)
                                                       and c.pos.isNearTo(source)))
                if near:
                    name = near.owner.username
                    state = StoredEnemyRoomState.JUST_MINING
                    break

    if state is None:
        return None
    else:
        return __new__(StoredEnemyRoomOwner(name, state))


def update_data_for_visible_rooms():
    """
    Updates all visible rooms with structure, owner and reservation data.
    """
    for name in Object.keys(Game.rooms):
        room = Game.rooms[name]
        if not room.my:
            update_data(room)


def update_old_structure_data_for_visible_rooms():
    """
    Updates structure data older than 3000 ticks for visible rooms.
    """
    for name in Object.keys(Game.rooms):
        room = Game.rooms[name]
        if not room.my:
            if get_last_updated_tick(name) + 3000 < Game.time:
                update_data(room)


def find_oldest_room_data_in_observer_range_of(room_name):
    """
    :type room_name: str
    :rtype: str
    """
    pass


def update_data(room):
    """
    Updates stored data about the given room, based off of the room's current state.

    Updates stored structures, room owner, and reservation end time.
    :param room: The raw Screeps Room object
    :type room: Room
    """
    room_name = room.name
    serialized = _get_serialized_data(room_name)
    if serialized:
        # don't use decoding cache, since then we would invalidate the cache for the old encoded string
        data = StoredRoom.decode(serialized)
    else:
        data = __new__(StoredRoom())
    data.obstacles = _find_obstacles(room)
    data.last_updated = Game.time
    data.owner = _find_room_owner(room)
    data.reservation_end = _find_room_reservation_end(room)
    _set_new_data(room_name, data)


def get_data(room_name):
    """
    Gets the full stored information on a room
    :param room_name: The room name
    :return: The stored data, decoded.
    :type room_name: str
    :rtype: StoredRoom
    """
    serialized = _get_serialized_data(room_name)
    if serialized:
        return _deserialize_data(serialized)
    else:
        return None


def get_reservation_end_time(room_name):
    """
    Returns the end time of our reservation on a room, or 0 if not found.
    :param room_name: The room name
    :type room_name: str
    """
    data = get_data(room_name)
    if data:
        return data.reservation_end
    else:
        return 0


def get_last_updated_tick(room_name):
    """
    Returns the last time the structure data for a room was updated, or 0 if not found.
    :param room_name: The room name
    :type room_name: str
    """
    data = get_data(room_name)
    if data:
        return data.last_updated
    else:
        return 0


def set_reservation_time(room_name, reservation_time):
    """
    Sets / updates the reservation time in room data.
    :param room_name: The room name
    :param reservation_time: The time left on the reservation
    :type room_name: str
    :type reservation_time: int
    """
    serialized = _get_serialized_data(room_name)
    if serialized:
        # don't use decoding cache, since then we would invalidate the cache for the old encoded string
        data = StoredRoom.decode(serialized)
    else:
        data = __new__(StoredRoom())
    data.reservation_end = Game.time + reservation_time
    _set_new_data(room_name, data)


def migrate_old_data():
    definition = flags.flag_definitions[flags.SK_LAIR_SOURCE_NOTED]
    if Memory.enemy_rooms:
        for room_name in Memory.enemy_rooms:
            set_as_enemy(room_name, 'Unknown / migrated from Memory.enemy_rooms')
            print('[storage] Removing migrated enemy_rooms.')
        del Memory.enemy_rooms
    sk_flags = _(Game.flags).filter(lambda f: f.color == definition[0] and f.secondaryColor == definition[1]) \
        .groupBy('pos.roomName').value()
    if not _.isEmpty(sk_flags):
        for room_name in Object.keys(sk_flags):
            flags_here = sk_flags[room_name]
            serialized = _get_serialized_data(room_name)
            if serialized:
                # don't use decoding cache, since then we would invalidate the cache for the old encoded string
                data = StoredRoom.decode(serialized)
            else:
                data = __new__(StoredRoom())
            already_existing = new_set()
            for obstacle in data.obstacles:
                if obstacle.type == StoredObstacleType.SOURCE_KEEPER_LAIR \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_MINERAL \
                        or obstacle.type == StoredObstacleType.SOURCE_KEEPER_SOURCE:
                    already_existing.add(positions.serialize_pos_xy(obstacle))
            new_stored = []
            for flag in flags_here:
                serialized = positions.serialize_pos_xy(flag)
                if not already_existing.has(serialized):
                    new_stored.append(__new__(StoredObstacle(
                        flag.pos.x, flag.pos.y, StoredObstacleType.SOURCE_KEEPER_LAIR)))
                    already_existing.add(serialized)
                    print('[storage] Successfully migrated SK flag in {} at {},{} to data storage.'
                          .format(room_name, flag.pos.x, flag.pos.y))
            if len(new_stored):
                _set_new_data(room_name, data)
            for flag in flags_here:
                print('[storage] Removing migrated SK flag {} in {} at {},{}.'
                      .format(flag.name, flag.pos.roomName, flag.pos.x, flag.pos.y))
                flag.remove()


def set_as_enemy(room_name, username=None):
    if username is None:
        username = "Manually set"
    stored = get_data(room_name)
    if stored:
        if stored.owner and (stored.owner.state is StoredEnemyRoomState.FULLY_FUNCTIONAL
                             or stored.owner.state is StoredEnemyRoomState.RESERVED):
            return
        new_data = StoredRoom.decode(_get_serialized_data(room_name))
    else:
        new_data = __new__(StoredRoom())
    new_data.owner = __new__(StoredEnemyRoomOwner(username, StoredEnemyRoomState.FULLY_FUNCTIONAL))
    print("[storage] Successfully added {} as an enemy room.".format(room_name))
    _set_new_data(room_name, new_data)

"""
Stored data!

Stores data in memory via room name keys, using the metadata module powered by Protocol Buffers to encode data.
"""
from constants import INVADER_USERNAME, SK_USERNAME
from constants.memkeys import global_mem_key_room_data
from jstools.js_set_map import new_map
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_my_username = None
_cached_data = None
_cached_mem = None
_cached_data_reset_tick = 0


def _find_my_username():
    global _my_username
    if _my_username is None:
        struct = _.find(Game.structures, 'my')
        _my_username = struct.owner.username
    return _my_username


def _find_structures(room):
    """
    :type room: Room
    :rtype: list[StoredStructure]
    """
    result = []
    any_lairs = False
    for structure in room.find(FIND_STRUCTURES):
        orig_type = structure.structureType
        if orig_type == STRUCTURE_PORTAL or orig_type == STRUCTURE_CONTAINER:
            continue
        elif orig_type == STRUCTURE_ROAD:
            stored_type = StoredStructureType.ROAD
        elif orig_type == STRUCTURE_CONTROLLER:
            stored_type = StoredStructureType.CONTROLLER
        elif orig_type == STRUCTURE_KEEPER_LAIR:
            stored_type = StoredStructureType.SOURCE_KEEPER_LAIR
            any_lairs = True
        else:
            stored_type = StoredStructureType.OTHER_IMPASSABLE
        result.append(__new__(StoredStructure(structure.pos.x, structure.pos.y, stored_type)))
    for source in room.find(FIND_SOURCES):
        if any_lairs:
            stored_type = StoredStructureType.SOURCE_KEEPER_SOURCE
        else:
            stored_type = StoredStructureType.SOURCE
        result.append(__new__(StoredStructure(source.pos.x, source.pos.y, stored_type, source.energyCapacity)))
    for mineral in room.find(FIND_MINERALS):
        if any_lairs:
            stored_type = StoredStructureType.SOURCE_KEEPER_MINERAL
        else:
            stored_type = StoredStructureType.MINERAL
        result.append(__new__(StoredStructure(mineral.pos.x, mineral.pos.y, stored_type)))
    return result


def _find_room_reservation_end(room):
    """
    :type room: Room
    :rtype: int
    """
    if room.controller and room.controller.reservation and room.controller.reservation.username == _find_my_username():
        return Game.time + room.controller.reservation.ticksToEnd
    else:
        return 0


def _find_room_owner(room):
    """
    :type room: Room
    :rtype: StoredRoomOwner
    """
    name = None
    state = None
    controller = room.controller
    if controller:
        if controller.owner and not controller.my:
            name = controller.owner.username
            state = RoomOwnedState.FULLY_FUNCTIONAL
        elif controller.reservation and controller.reservation.username != _find_my_username():
            name = controller.reservation.username
            state = RoomOwnedState.RESERVED

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
                    state = RoomOwnedState.JUST_MINING
                    break

    if state is None:
        return None
    else:
        return __new__(StoredRoomOwner(name, state))


def _check_tick():
    global _cached_data_reset_tick, _cached_data, _cached_mem
    if _cached_data_reset_tick != Game.time:
        _cached_data_reset_tick = Game.time
        _cached_data = new_map()
        _cached_mem = Memory[global_mem_key_room_data]
        if not _cached_mem:
            _cached_mem = Memory[global_mem_key_room_data] = {}


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
    Updates structure data older than 100 ticks for visible rooms.
    """
    for name in Object.keys(Game.rooms):
        room = Game.rooms[name]
        if not room.my:
            data = get_data(name)
            if not data or data.structures_last_updated + 100 < Game.time:
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
    _check_tick()
    room_name = room.name
    data = get_data(room_name)
    if not data:
        data = __new__(StoredRoom())
    data.structures = _find_structures(room)
    data.structures_last_updated = Game.time
    data.owner = _find_room_owner(room)
    data.reservation_end = _find_room_reservation_end(room)
    _cached_mem[room_name] = data.encode()


def get_data(room_name):
    """
    Gets the full stored information on a room
    :param room_name: The room name
    :return: The stored data, decoded.
    :type room_name: str
    :rtype: StoredRoom
    """
    _check_tick()
    data = _cached_data.get(room_name)
    if data is not undefined:
        return data

    serialized = _cached_mem[room_name]
    if serialized:
        return StoredRoom.decode(serialized)
    else:
        return None


def get_reservation_time(room_name):
    """
    Returns the end time of our reservation on a room, or 0 if not found.
    :param room_name: The room name
    :type room_name: str
    """
    data = get_data(room_name)
    if data is not None:
        return data.reservation_end
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
    _check_tick()
    data = get_data(room_name)
    if data is None:
        data = __new__(StoredRoom())
    data.reservation_end = Game.time + reservation_time
    _cached_mem[room_name] = data.encode()


def cpu_test():
    start = Game.cpu.getUsed()
    _check_tick()
    num_rooms = 0
    num_structures = 0
    for name in Object.keys(_cached_mem):
        data = get_data(name)
        num_rooms += 1
        num_structures += len(data.structures)
    end = Game.cpu.getUsed()
    return "Used {} cpu decoding {} rooms, including {} structures.".format(end - start, num_rooms, num_structures)

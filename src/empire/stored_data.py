"""
Stored data!

Stores data in memory via room name keys, using the metadata module powered by Protocol Buffers to encode data.
"""
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, cast

from constants import INVADER_USERNAME, SK_USERNAME
from constants.memkeys import deprecated_global_mem_key_room_data, \
    deprecated_global_mem_key_stored_room_data_segment_mapping, global_mem_key_segments_last_updated, \
    meta_segment_key_stored_room_data_segment_mapping
from jstools.js_set_map import new_map, new_set
from jstools.screeps import *
from utilities import movement

if TYPE_CHECKING:
    from empire.hive import HiveMind
    from jstools.js_set_map import JSMap, JSSet

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_cache_created = Game.time
_cached_data = new_map()

_metadata_segment = 14
_segments_to_use = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
_room_data_segments = [5, 6, 7, 8, 9, 10]
_old_room_data_segments = [11, 12, 13]

_segments_cache = new_map()  # type: JSMap[int, _Memory]
_segments_last_retrieved = new_map()  # type: JSMap[int, int]
_modified_segments = new_set()  # type: JSSet[int]
_segment_change_reasons = new_map()  # type: JSMap[int, List[str]]


def initial_modification_check():
    # TODO: periodic check which balances segments which have too much data stored in them, and runs
    # emergency trim if we're hitting the limits on more than half of the segments.

    modified_mem = Memory[global_mem_key_segments_last_updated]
    if not modified_mem:
        Memory[global_mem_key_segments_last_updated] = modified_mem = {}
    for segment in _segments_to_use:
        last_modified = modified_mem[segment]
        last_retrieved = _segments_last_retrieved.get(segment)
        if last_modified and last_retrieved and last_modified > last_retrieved:
            _segments_cache.delete(segment)
            _segments_last_retrieved.delete(segment)
            _modified_segments.delete(segment)


def final_modification_save():
    current_tick = Game.time
    modified_mem = Memory[global_mem_key_segments_last_updated]
    if not modified_mem:
        Memory[global_mem_key_segments_last_updated] = modified_mem = {}

    for segment in list(_modified_segments.values()):
        print("[stored_data] {} changed: {}".format(segment, ', '.join(_segment_change_reasons.get(segment))))
        RawMemory.segments[segment] = JSON.stringify(_segments_cache.get(segment))
        modified_mem[segment] = current_tick
        _segments_last_retrieved.set(segment, current_tick)
    _modified_segments.js_clear()
    _segment_change_reasons.js_clear()


def _parse_json_checked(raw_data, segment_name):
    # type: (str, int) -> _Memory
    try:
        return cast(_Memory, JSON.parse(raw_data))
    except:
        msg = "segment {} data corrupted: invalid json! clearing data: {}".format(segment_name, raw_data)
        print(msg)
        Game.notify(msg)
        return cast(_Memory, {})


def _get_segment(segment: int, optional: bool = False) -> Optional[Dict[str, str]]:
    """
    Gets data from a segment, raising AssertionError if it's one of the known segments and it isn't loaded.

    If it isn't a known segment and it isn't loaded, returns None.

    If the segment is modified, the ID should be marked by using `_mark_modified(segment)`

    :param segment: segment id
    :return: parsed segment memory
    """
    segment = int(segment)
    segment_data = _segments_cache.get(segment)
    if segment_data:
        return segment_data

    raw_data = RawMemory.segments[segment]

    if raw_data == undefined:
        if _.includes(_segments_to_use, segment):
            RawMemory.setActiveSegments(_segments_to_use)
            # TODO: some way for requests to stored data to have an alternate action here.

            msg = "segment {} not available! Bailing action so it can complete next tick.".format(segment)
            if optional:
                return None
            else:
                raise AssertionError(msg)
        else:
            return None

    if raw_data == "":
        segment_data = {}
    else:
        segment_data = _parse_json_checked(raw_data, segment)

    _segments_last_retrieved.set(segment, Game.time)
    _segments_cache.set(segment, segment_data)

    return segment_data


def _mark_modified(segment, reason):
    _modified_segments.add(segment)
    if _segment_change_reasons.has(segment):
        _segment_change_reasons.get(segment).append(reason)
    else:
        _segment_change_reasons.set(segment, [reason])


def _migrate_old_data(new_room_name_to_segment: Dict[str, int]):
    old_memory = Memory[deprecated_global_mem_key_room_data] or None
    if old_memory is None:
        return
    segments = []
    for segment_name in _room_data_segments:
        segments.append((segment_name, _get_segment(segment_name)))

    for room_name, data in _.pairs(old_memory):
        segment_name, segment_data = _.sample(segments)
        new_room_name_to_segment[room_name] = segment_name
        segment_data[room_name] = data
        _mark_modified(segment_name, "migrated " + room_name)


def _room_name_to_segment() -> Dict[str, int]:
    meta_mem = _get_segment(_metadata_segment, deprecated_global_mem_key_stored_room_data_segment_mapping in Memory)
    if not meta_mem:
        return Memory[deprecated_global_mem_key_stored_room_data_segment_mapping]
    mem = meta_mem[meta_segment_key_stored_room_data_segment_mapping]
    if not mem:
        if deprecated_global_mem_key_stored_room_data_segment_mapping in Memory:  # hardcoded old value
            mem = meta_mem[meta_segment_key_stored_room_data_segment_mapping] = \
                Memory[deprecated_global_mem_key_stored_room_data_segment_mapping]
            _mark_modified(_metadata_segment, "migrated room name to segment mapping")
            del Memory[deprecated_global_mem_key_stored_room_data_segment_mapping]
        elif deprecated_global_mem_key_room_data in Memory:
            mem = meta_mem[meta_segment_key_stored_room_data_segment_mapping] = {}
            _migrate_old_data(mem)
            _mark_modified(_metadata_segment, "migrated room name to segment mapping")

    return mem


def _get_serialized_data(room_name) -> Optional[str]:
    room_name_to_segment = _room_name_to_segment()
    segment = room_name_to_segment[room_name]
    if segment:
        segment_data = _get_segment(segment)

        if not segment_data:
            # not a segment we store data in!
            msg = "[stored_data] room name {} stored in segment {}, which is not a known segment for storing " \
                  "serialized data! discarding segment name association!".format(room_name, segment)
            print(msg)
            Game.notify(msg)
            del room_name_to_segment[room_name]
            _mark_modified(_metadata_segment, "fixed metadata mapping inconsistency")
            return None

        room_data = segment_data[room_name]

        if room_data:
            return room_data
        else:
            msg = "[stored_data] room name {} stored in segment {}, but no data for that room in that segment! " \
                  "discarding segment name association!".format(room_name, segment)
            print(msg)
            Game.notify(msg)
            del room_name_to_segment[room_name]
            _mark_modified(_metadata_segment, "fixed metadata mapping inconsistency")
            return None
    else:
        return None


def _deserialize_data(data: str) -> StoredRoom:
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


def _set_new_data(room_name: str, data: StoredRoom) -> None:
    room_name_to_segment = _room_name_to_segment()
    segment_name = room_name_to_segment[room_name]
    segment_data = None
    if segment_name:
        segment_data = _get_segment(segment_name)
    if not segment_data:
        segment_name = _.sample(_room_data_segments)
        segment_data = _get_segment(segment_name)
        room_name_to_segment[room_name] = segment_name
        _mark_modified(_metadata_segment, "added new mapping for room " + room_name)

    _mark_modified(segment_name, "updated data for room " + room_name)

    segment_data[room_name] = encoded = data.encode()
    _cached_data.set(encoded, data)


def cleanup_old_data(hive: HiveMind) -> None:
    room_name_to_segment = _room_name_to_segment()
    for room_name, associated_segment in _.pairs(room_name_to_segment):
        nearest_room = hive.get_closest_owned_room(room_name)
        if nearest_room:
            distance = movement.room_chebyshev_distance(nearest_room.name, room_name)
            if distance > 9:
                msg = "[stored_data] Removing data on room {}: closest room, {}, is {} rooms away.".format(
                    room_name,
                    nearest_room,
                    distance,
                )
                print(msg)
                Game.notify(msg)
                segment_name = room_name_to_segment[room_name]
                del _get_segment(segment_name)[room_name]
                del room_name_to_segment[room_name]
                _mark_modified(segment_name, "removed old room " + room_name)
                _mark_modified(_metadata_segment, "removed mapping for old room " + room_name)


_my_username = None  # type: Optional[str]


def get_my_username() -> str:
    global _my_username
    if _my_username is None:
        struct = _.find(Game.structures, 'my')
        _my_username = struct.owner.username
    return _my_username


def _find_obstacles(room: Room) -> List[StoredObstacle]:
    result = []
    any_lairs = False
    for structure in cast(List[Structure], room.find(FIND_STRUCTURES)):
        orig_type = structure.structureType
        if orig_type == STRUCTURE_PORTAL or orig_type == STRUCTURE_CONTAINER:
            continue
        elif orig_type == STRUCTURE_RAMPART and cast(StructureRampart, structure).my:
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
    for source in cast(List[Source], room.find(FIND_SOURCES)):
        if any_lairs:
            stored_type = StoredObstacleType.SOURCE_KEEPER_SOURCE
        else:
            stored_type = StoredObstacleType.SOURCE
        result.append(__new__(StoredObstacle(source.pos.x, source.pos.y, stored_type, source.energyCapacity)))
    for mineral in cast(List[Mineral], room.find(FIND_MINERALS)):
        if any_lairs:
            stored_type = StoredObstacleType.SOURCE_KEEPER_MINERAL
        else:
            stored_type = StoredObstacleType.MINERAL
        result.append(__new__(StoredObstacle(mineral.pos.x, mineral.pos.y, stored_type)))
    return result


def _find_room_reservation_end(room: Room) -> int:
    if room.controller and room.controller.reservation and room.controller.reservation.username == get_my_username():
        return Game.time + room.controller.reservation.ticksToEnd
    else:
        return 0


def _find_room_owner(room: Room) -> Optional[StoredEnemyRoomOwner]:
    name = None
    state = None
    controller = room.controller
    if controller:
        if controller.owner and not controller.my:
            name = controller.owner.username
            if (len(room.find(FIND_HOSTILE_STRUCTURES, {
                'filter': {
                    'owner': {'username': name},
                    'structureType': STRUCTURE_SPAWN
                }
            })) and len(room.find(FIND_HOSTILE_STRUCTURES, {
                'filter': {
                    'owner': {'username': name},
                    'structureType': STRUCTURE_TOWER
                }
            }))):
                state = StoredEnemyRoomState.FULLY_FUNCTIONAL
            else:
                state = StoredEnemyRoomState.OWNED_DEAD
        elif controller.reservation and controller.reservation.username != get_my_username():
            name = controller.reservation.username
            state = StoredEnemyRoomState.RESERVED

    if state is None:
        enemy_creeps = cast(List[Creep], room.find(FIND_HOSTILE_CREEPS))
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


def update_old_structure_data_for_visible_rooms() -> None:
    """
    Updates structure data older than 3000 ticks for visible rooms.
    """
    for name in Object.keys(Game.rooms):
        room = Game.rooms[name]
        if not room.controller or not room.controller.my:
            if get_last_updated_tick(name) + 3000 < Game.time:
                update_data(room)


def find_oldest_rooms_to_check_in_observer_range_of(center_room_name, saved_pos=None):
    # type: (str, Optional[int]) -> Tuple[int, List[str]]
    """
    :type saved_pos: int
    :type center_room_name: str
    :rtype: (int, list[str])
    """
    if saved_pos == -1:
        saved_pos = None

    this_room_x, this_room_y = movement.parse_room_to_xy(center_room_name)
    now = Game.time

    result = []

    relative_x = 0
    relative_y = 0
    dx = 0
    dy = -1
    for i in range(10 ** 2):
        if saved_pos is None:
            room_name = movement.room_xy_to_name(this_room_x + relative_x, this_room_y + relative_y)
            last_updated = get_last_updated_tick(room_name)
            if last_updated == 0:
                to_update = (abs(relative_x) <= 3 and abs(relative_y) <= 3)
            else:
                to_update = now - last_updated > 5000
            if to_update:
                result.append(room_name)
                if len(result) >= 20:
                    new_saved_pos = i
                    break
        elif i == saved_pos:
            saved_pos = None
        if relative_x == relative_y or (relative_x < 0 and relative_x == -relative_y) \
                or (relative_x > 0 and relative_x == 1 - relative_y):
            dx, dy = -dy, dx
        relative_x = relative_x + dx
        relative_y = relative_y + dy
    else:
        new_saved_pos = -1

    return new_saved_pos, result


def update_data(room: Room) -> None:
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


def get_data(room_name: str) -> Optional[StoredRoom]:
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


def get_reservation_end_time(room_name: str) -> int:
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


def get_last_updated_tick(room_name: str) -> int:
    """
    Returns the last time the structure data for a room was updated, or 0 if not found.
    :param room_name: The room name
    :type room_name: str
    """
    data = get_data(room_name)
    if data:
        return data.last_updated or 0
    else:
        return 0


def set_reservation_time(room_name: str, reservation_time: int) -> None:
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


def set_as_enemy(room_name: str, username: str = None) -> None:
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
    print("[storage] added as manual enemy room: {}".format(room_name))
    _set_new_data(room_name, new_data)


def avoid_always(room_name: str) -> str:
    stored = get_data(room_name)
    if stored:
        if stored.avoid_always:
            return "already avoiding {}.".format(room_name)
        new_data = StoredRoom.decode(_get_serialized_data(room_name))
    else:
        new_data = __new__(StoredRoom())
    new_data.avoid_always = True
    print("[storage] now avoiding room: {}".format(room_name))
    _set_new_data(room_name, new_data)
    return "set {} as always avoid room.".format(room_name)


def unavoid_always(room_name: str) -> str:
    stored = get_data(room_name)
    if stored:
        if not stored.avoid_always:
            return "already not avoiding {}.".format(room_name)
        new_data = StoredRoom.decode(_get_serialized_data(room_name))
    else:
        new_data = __new__(StoredRoom())
    new_data.avoid_always = False
    print("[storage] no longer avoiding room: {}".format(room_name))
    _set_new_data(room_name, new_data)
    return "set {} as not avoid room.".format(room_name)


def recalculate_room_mapping() -> None:
    room_name_to_segment = _room_name_to_segment()
    for key in Object.keys(room_name_to_segment):
        del room_name_to_segment[key]
    print("keys left on room segment mappings after clearing: {}".format(Object.keys(room_name_to_segment)))
    for segment_id in _old_room_data_segments:
        segment_to_move_from = _get_segment(segment_id)
        for room_name in Object.keys(segment_to_move_from):
            pos = movement.parse_room_to_xy(room_name)
            if pos[0] != 0 or pos[1] != 0:
                new_segment = _.sample(_room_data_segments)
                _get_segment(new_segment)[room_name] = segment_to_move_from[room_name]
                del segment_to_move_from[room_name]
                _mark_modified(segment_id, "removed room " + room_name)
                _mark_modified(new_segment, "added room " + room_name)
            else:
                print("[stored_data] *not* migrating {} away from segment {}".format(room_name, segment_id))
    for segment_id in _room_data_segments:
        segment_data = _get_segment(segment_id)
        for room_name in Object.keys(segment_data):
            if room_name in room_name_to_segment:
                print("[stored_data] duplicate data: {} in segments {} *and* {}"
                      .format(room_name, room_name_to_segment[room_name], segment_id))
                if room_name_to_segment[room_name] != segment_id:
                    del segment_data[room_name]
                    _mark_modified(segment_id, "removed room " + room_name)
            else:
                room_name_to_segment[room_name] = segment_id
    _mark_modified(_metadata_segment, "recalculated room mappings")

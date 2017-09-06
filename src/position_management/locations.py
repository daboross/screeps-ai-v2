from typing import Dict, Optional, Union, cast

from jstools.screeps import *
from utilities import naming

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_mem_hints = None  # type: Optional[Dict[str, int]]
_mem_expirations = None  # type: Optional[Dict[str, int]]
_mem = None
_created_objects = None
_last_update = 0

__pragma__('skip')


# Python-style class imitating DeserializedPos
# noinspection PyPep8Naming
class Location(RoomPosition):
    """
    :type name: str
    :type hint: int
    """

    def __init__(self, x: int, y: int, roomName: str, name: str, hint: int):
        super().__init__(x, y, roomName)
        self.name = name
        self.hint = hint

    def update(self, x: int, y: int, roomName: str = None):
        """
        :type x: int
        :type y: int
        :type roomName: str
        """
        self.x = x
        self.y = y
        if roomName is not None:
            self.roomName = roomName


__pragma__('noskip')


# Old-style JavaScript class for the sake of performance
# noinspection PyPep8Naming
def DeserializedPos(string, name):
    # type: (str, str) -> Location
    xy_str, room, expiration_str = string.split('|')
    xy = int(xy_str)
    this.x = xy & 0x3F
    this.y = xy >> 6 & 0x3F
    this.roomName = room
    this.name = name
    if expiration_str != undefined:
        _mem_expirations[name] = Game.time + int(expiration_str)
    return cast(Location, undefined)


__pragma__('js', '{}', """
DeserializedPos.prototype = Object.create(RoomPosition.prototype);
""")

deserialized_proto = __pragma__('js', 'DeserializedPos.prototype')


def _update_deserialized_pos_xy(x, y, room_name):
    # type: (int, int, str) -> None
    this.x = x
    this.y = y
    if room_name != undefined:
        this.roomName = room_name
    _mem[this.name] = _serialize(this)


def _get_hint():
    # type: () -> Optional[int]
    hint = _mem_hints[this.name]
    if hint is undefined:
        hint = None
    Object.defineProperty(this, 'hint', {
        'get': __pragma__('js', '{}', '() => hint'),
        'set': _set_hint,
        'enumerable': True,
        'configurable': True,
    })
    return hint


def _get_pos():
    return this


def _set_hint(hint):
    # type: (str) -> None
    Object.defineProperty(this, 'hint', {
        'get': __pragma__('js', '{}', '() => hint'),
        'set': _set_hint,
        'enumerable': True,
        'configurable': True,
    })
    _mem_hints[this.name] = hint


def _deserialized_pos_to_string():
    # type: () -> str
    things = [
        "[Location ",
        this.name,
    ]
    if this.hint:
        things.push(" (type: ", this.hint, ")")
    things.push(
        ": ",
        this.x,
        ",",
        this.y,
        " ",
        this.roomName,
        "]"
    )
    return ''.join(things)


deserialized_proto.update = _update_deserialized_pos_xy

Object.defineProperty(deserialized_proto, 'hint', {
    'get': _get_hint,
    'set': _set_hint,
    'enumerable': True,
    'configurable': True,
})

Object.defineProperty(deserialized_proto, 'pos', {
    'get': _get_pos,
    'enumerable': False,
    'configurable': True,
})

deserialized_proto.toString = _deserialized_pos_to_string


def _deserialize(string, name):
    # type: (str, str) -> Location
    return __new__(DeserializedPos(string, name))


def _serialize(position, expiration=None):
    # type: (Union[RoomPosition, RoomObject], Optional[int]) -> str
    if cast(RoomObject, position).pos is not undefined:
        pos = cast(RoomObject, position).pos
    else:
        pos = cast(RoomPosition, position)

    if pos.x == undefined or pos.y == undefined or pos.roomName == undefined:
        raise AssertionError("Invalid position: {}".format(pos))
    parts = [str(pos.x | pos.y << 6), pos.roomName]
    if expiration != undefined:
        parts.append(str(expiration))
    return '|'.join(parts)


def init():
    # type: () -> None
    global _mem, _mem_hints, _mem_expirations
    if '_locations' not in Memory:
        # use a dash here to force JavaScript to turn this into a 'random access' object rather than a regular object.
        Memory['_locations'] = {'-': None}
    if '_hints' not in Memory:
        Memory['_hints'] = {'-': None}
    if '_exp' not in Memory:
        Memory['_exp'] = {'-': None}
    _mem = Memory['_locations']
    _mem_hints = Memory['_hints']
    _mem_expirations = Memory['_exp']


def serialized(name):
    # type: (Optional[str]) -> Optional[str]
    """
    Returns the serialized position from the give name (in the form of {x | y << 6}'|'{roomName}).

    Warning: does not update expirations memory!
    :param name: The name
    :return: The serialized position, or None
    :type name: str
    :rtype: str | None
    """
    result = _mem[name]
    if result is undefined:
        return None
    else:
        return result


def get(name):
    # type: (str) -> Optional[Location]
    """
    Gets an existing location with the given name. Updates expiration date.
    :type name: str
    :param name: The name of the location to get
    :return: The location object, or None
    :rtype: Location | None
    """
    serialized_result = _mem[name]
    if serialized_result == undefined:
        return None
    else:
        return _deserialize(serialized_result, name)


def create(position, hint=None, expiration=None):
    # type: (Union[RoomObject, RoomPosition], Optional[int], Optional[int]) -> Location
    """
    Creates a location with the given position and hint.
    :param position: An object with x, y, and roomName properties
    :param hint: The hint
    :param expiration: Time after no use that the position should expire (defaults to 10,000 ticks). -1 to disable.
    :return: A location object
    :type position: Any
    :type hint: int
    :type expiration: int
    :rtype: Location
    """
    name = naming.random_digits()
    while name in _mem:
        name += naming.random_digits()
    if expiration == undefined:
        expiration = 10 * 1000
    elif expiration <= 0:
        expiration = None
    _mem[name] = _serialize(position, expiration)
    if hint != undefined:
        _mem_hints[name] = hint

    return get(name)  # The first get operation will set _mem_expirations


def delete_location(name):
    # type: (str) -> None
    """
    Deletes a location with the given name
    :param name: The name to delete
    :type name: str
    """
    del _mem_expirations[name]
    del _mem_hints[name]
    del _mem[name]


def clean_old_positions():
    # type: () -> None
    for name in Object.keys(_mem_expirations):
        if name != '-' and _mem_expirations[name] < Game.time:
            exp = _mem_expirations[name]
            print("[locations] Expiring location {}: {} < {}".format(get(name), exp, Game.time))
            del _mem_expirations[name]
            del _mem_hints[name]
            del _mem[name]

from tools import naming
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_mem_hints = None
_mem = None
_created_objects = None
_last_update = 0

__pragma__('skip')


# Python-style class imitating DeserializedPos
# noinspection PyPep8Naming
class Location:
    """
    :type x: int
    :type y: int
    :type roomName: str
    :type name: str
    :type hint: int
    """

    def __init__(self, x, y, roomName, name, hint):
        self.x = x
        self.y = y
        self.roomName = roomName
        self.name = name
        self.hint = hint

    def update(self, x, y, roomName=None):
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
    xy_str, room = string.split('|')
    xy = int(xy_str)
    this.x = xy & 0x3F
    this.y = xy >> 6 & 0x3F
    this.roomName = room
    this.name = name


DeserializedPos.prototype = Object.create(RoomPosition.prototype)


def _update_deserialized_pos_xy(x, y, room_name):
    this.x = x
    this.y = y
    if room_name != undefined:
        this.roomName = room_name
    _mem[this.name] = _serialize(this)


def _get_hint():
    hint = _mem_hints[this.name]
    if hint is undefined:
        hint = None
    Object.defineProperty(this, 'hint', {
        'value': hint,
        'set': _set_hint,
        'enumerable': True,
        'configurable': True,
    })
    return hint


def _set_hint(hint):
    Object.defineProperty(this, 'hint', {
        'value': hint,
        'set': _set_hint,
        'enumerable': True,
        'configurable': True,
    })
    _mem_hints[this.name] = hint


DeserializedPos.prototype.update = _update_deserialized_pos_xy

Object.defineProperty(DeserializedPos.prototype, 'hint', {
    'get': _get_hint,
    'set': _set_hint,
    'enumerable': True,
    'configurable': True,
})


def _deserialize(string, name):
    return __new__(DeserializedPos(string, name))


def _serialize(position):
    if position.pos is not undefined:
        position = position.pos
    return '|'.join([position.x | position.y << 6, position.roomName])


def init():
    global _mem, _mem_hints, _created_objects
    if '_locations' not in Memory:
        # use a dash here to force JavaScript to turn this into a 'random access' object rather than a regular object.
        Memory['_locations'] = {'-': None}
    if '_hints' not in Memory:
        Memory['_hints'] = {'-': None}
    _mem = Memory['_locations']
    _mem_hints = Memory['_hints']


def serialized(name):
    """
    Returns the serialized position from the give name (in the form of {x | y << 6}'|'{roomName})
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
    """
    Gets an existing location with the given name
    :type name: str
    :param name: The name of the location to get
    :return: The location object, or None
    :rtype: Location | None
    """
    serialized_result = _mem[name]
    if serialized_result is undefined:
        return None
    else:
        return _deserialize(serialized_result, name)


def create(position, hint=None):
    """
    Creates a location with the given position and hint.
    :param position: An object with x, y, and roomName properties
    :param hint: The hint
    :return: A location object
    :type position: Any
    :type hint: int
    :rtype: Location
    """
    name = naming.random_digits()
    while name in _mem:
        name += naming.random_digits()
    _mem[name] = _serialize(position)
    if hint != undefined:
        _mem_hints[name] = hint
    return get(name)

from typing import Any, List, TYPE_CHECKING, TypeVar, Union, cast

from jstools.screeps import *

if TYPE_CHECKING:
    from creeps.base import RoleBase
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


def energy(obj):
    # type: (RoomObject) -> int
    if cast(Union[StructureLink, StructureSpawn, StructureExtension], obj).energy:
        return cast(Union[StructureLink, StructureSpawn, StructureExtension], obj).energy

    if cast(Union[StructureContainer, StructureStorage], obj).store:
        return cast(Union[StructureContainer, StructureStorage], obj).store[RESOURCE_ENERGY] or 0

    if cast(Creep, obj).carry:
        return cast(Creep, obj).carry[RESOURCE_ENERGY] or 0

    return 0


def capacity(obj):
    # type: (RoomObject) -> int
    if cast(Union[StructureLink, StructureSpawn, StructureExtension], obj).energyCapacity:
        return cast(Union[StructureLink, StructureSpawn, StructureExtension], obj).energyCapacity

    if cast(Union[StructureContainer, StructureStorage], obj).storeCapacity:
        return cast(Union[StructureContainer, StructureStorage], obj).storeCapacity

    if cast(Creep, obj).carryCapacity:
        return cast(Creep, obj).carryCapacity

    return 0


def pos(obj):
    # type: (Union[RoomObject, RoomPosition, RoleBase, Location]) -> RoomPosition
    return obj if obj == undefined else (cast(Union[RoomObject, RoleBase], obj).pos
                                         or cast(Union[RoomPosition, Location], obj))


__pragma__('skip')
_L = TypeVar('_L')
__pragma__('noskip')


def rindex_list(_list: List[_L], item: _L) -> int:
    return cast(Any, _list).lastIndexOf(item)


def concat_lists(*lists: List[_L]) -> List[_L]:
    if not len(lists):
        return []

    result = lists[0]
    for _list in cast(Any, lists).slice(1):
        result = result.concat(_list)

    return result


def slice_list(_list: List[_L], start: int, end: int = undefined) -> List[_L]:
    return cast(Any, _list).slice(start, end)

def get_str_codepoint(_str: str, index: int) -> int:
    return cast(Any, _str).codePointAt(index)
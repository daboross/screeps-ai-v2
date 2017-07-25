from empire import stored_data
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def is_offensive(creep):
    # type: (Creep) -> bool
    return not not _.find(creep.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK)


def not_sk(creep):
    # type: (Creep) -> bool
    return creep.owner.username != "Source Keeper"


def enemy_using_room(room_name):
    # type: (str) -> bool
    data = stored_data.get_data(room_name)
    if not data or not data.owner:
        return False
    return (
        data.owner.state is StoredEnemyRoomState.FULLY_FUNCTIONAL
        or data.owner.state is StoredEnemyRoomState.RESERVED
        or data.owner.state is StoredEnemyRoomState.JUST_MINING
    )


def enemy_owns_room(room_name):
    # type: (str) -> bool
    data = stored_data.get_data(room_name)
    if not data or not data.owner:
        return False
    return (
        data.owner.state is StoredEnemyRoomState.FULLY_FUNCTIONAL
        or data.owner.state is StoredEnemyRoomState.OWNED_DEAD
    )

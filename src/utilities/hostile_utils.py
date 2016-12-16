from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def is_offensive(creep):
    return not not _.find(creep.body, lambda p: p.type == ATTACK or p.type == RANGED_ATTACK)


def not_sk(creep):
    return creep.owner.username != "Source Keeper"


def enemy_room(name):
    return 'enemy_rooms' in Memory and Memory.enemy_rooms.indexOf(name) != -1

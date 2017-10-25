from typing import List, cast

from constants.memkeys import global_mem_key_end_stage
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def start_ending():
    Memory[global_mem_key_end_stage] = 1


def is_ending():
    return not not Memory[global_mem_key_end_stage]


def run_end():
    if not is_ending():
        print("ending: not running (stage < 1).")
        return
    stage = +Memory[global_mem_key_end_stage]
    if stage == 1:
        _end_stage_1()
    elif stage == 2:
        _end_stage_2()
    elif stage == 3:
        _end_stage_3()
    elif stage == 4:
        _end_stage_4()
    elif stage == 5:
        _end_stage_5()
    elif stage == 6:
        _end_stage_6()
    elif stage == 7:
        _end_stage_7()
    elif stage == 8:
        _end_stage_8_and_9()


def _end_stage_1():
    print("ending: running stage 1")
    print("ending: killing all creeps")
    for creep in _.values(Game.creeps):
        result = creep.suicide()
        if result != OK:
            print("ending: error: result {} from creep ({}).suicide()"
                  .format(result, creep))
            return
    Memory[global_mem_key_end_stage] = 2


def _end_stage_2():
    print("ending: running stage 2")
    print("ending: destroying all structures")
    for room_name in Object.keys(Game.rooms):
        room = Game.rooms[room_name]
        if room.controller and room.controller.my:
            for structure in cast(List[Structure], room.find(FIND_STRUCTURES)):
                if structure.structureType != STRUCTURE_STORAGE:
                    result = structure.destroy()
                    if result != OK:
                        print("ending: error: result {} from structure ({}).destroy()"
                              .format(result, structure))
    Memory[global_mem_key_end_stage] = 3


def _end_stage_3():
    print("ending: running stage 3")
    print("ending: clearing main memory")
    js_global.Memory = {global_mem_key_end_stage: 4}
    RawMemory.setPublicSegments([])
    RawMemory.setDefaultPublicSegment(None)


def _end_stage_4():
    print("ending: running stage 4")

    mem_key = 'end_segment_section'
    segment_section = Memory[mem_key]
    print("ending: clearing segments: {}".format(', '.join(str(x) for x in Object.keys(RawMemory.segments))))
    if not segment_section:
        segment_section = 0
    for key in Object.keys(RawMemory.segments):
        RawMemory.segments[key] = ''

    if segment_section > 10:
        js_global.Memory = {global_mem_key_end_stage: 5}
        RawMemory.setActiveSegments([])
    else:
        RawMemory.setActiveSegments(list(range(segment_section, segment_section + 10)))
        Memory[mem_key] = segment_section + 1


def _end_stage_5():
    print("ending: running stage 5")
    print("ending: removing all market orders")
    for order_id in Object.keys(Game.market.orders):
        order = Game.market.orders[order_id]
        result = Game.market.cancelOrder(order.id)
        if result != OK:
            print("ending: error: result {} from Game.market.cancelOrder({})"
                  .format(result, order.id))
            return
    Memory[global_mem_key_end_stage] = 6


def _end_stage_6():
    print("ending: running stage 6")
    print("ending: final pass for killing all creeps")
    for creep in _.values(Game.creeps):
        result = creep.suicide()
        if result != OK:
            print("ending: error: result {} from creep ({}).suicide()"
                  .format(result, creep))
            return
    Memory[global_mem_key_end_stage] = 7


def _end_stage_7():
    print("ending: running stage 7")
    print("ending: removing all flags")
    for flag_name in Object.keys(Game.flags):
        flag = Game.flags[flag_name]
        result = flag.remove()
        if result != OK:
            print("ending: error: result {} from flag ({}).remove()"
                  .format(result, flag))
            return
    Memory[global_mem_key_end_stage] = 8


def _end_stage_8_and_9():
    global Memory
    owned_rooms = _.filter(Game.rooms, {'controller': {'my': True}})
    if len(owned_rooms) > 1:
        print("ending: running stage 8")
        print("ending: removing all but one controller")
        for room in owned_rooms[1:]:
            result = room.controller.unclaim()
            if result != OK:
                print("ending: error: result {} from controller {}.unclaim()"
                      .format(result, room.controller))
                return
    else:
        print("ending: running stage 9")
        print("ending: completely clearing memory")
        Memory = {}
        print("ending: removing last controller")
        result = owned_rooms[0].controller.unclaim()
        if result != OK:
            print("ending: error: result {} from controller {}.unclaim()"
                  .format(result, owned_rooms[0].controller))
            Memory = {global_mem_key_end_stage: 6}
            return

        print("ending complete.")

from typing import Any, Optional

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

###
# Creep role recording
###

_recording_now = False
_main_recording_now = False
_sub_recording_now = False
_single_record_start = 0  # type: int
_sub_record_start = 0  # type: int
_main_loop_record_start = 0  # type: int
_averages = None  # type: _Memory
_sub_records = None  # type: _Memory


def prep_recording():
    # type: () -> None
    global _recording_now, _main_recording_now, _averages, _sub_recording_now, _sub_records
    _averages = Memory['_averages']
    if not _averages:
        _averages = Memory['_averages'] = {}
    _recording_now = not not _averages['_recording_now']
    _main_recording_now = _recording_now or not not _averages['_only_recording_main']
    _sub_recording_now = _averages['_sub_recording_now'] or False
    if _sub_recording_now:
        _sub_records = _averages['_sub_records']
        if not _sub_records:
            _sub_records = _averages['_sub_records'] = {}


def start_recording():
    # type: () -> None
    Memory['_averages']['_recording_now'] = True


def start_recording_main_only():
    # type: () -> None
    Memory['_averages']['_only_recording_main'] = True


def stop_recording():
    # type: () -> None
    Memory['_averages']['_recording_now'] = False
    Memory['_averages']['_sub_recording_now'] = False


def start_sub_recording():
    # type: () -> None
    Memory['_averages']['_sub_recording_now'] = True
    Memory['_averages']['_recording_now'] = True


def reset_records():
    # type: () -> None
    Memory['_averages'] = {}


def start_record():
    # type: () -> None
    if _recording_now:
        global _single_record_start
        _single_record_start = Game.cpu.getUsed()


def finish_record(identity):
    # type: (str) -> None
    if _recording_now and _single_record_start is not None:
        end = Game.cpu.getUsed()
        if identity in _averages:
            _averages[identity].calls += 1
            _averages[identity].time += end - _single_record_start
        else:
            _averages[identity] = {
                'calls': 1,
                'time': end - _single_record_start,
            }


def start_sub_record():
    # type: () -> None
    if _sub_recording_now:
        global _sub_record_start
        _sub_record_start = Game.cpu.getUsed()


def finish_sub_record(identity):
    # type: (str) -> None
    global _sub_record_start
    if _sub_recording_now and _sub_record_start is not None:
        end = Game.cpu.getUsed()
        if identity in _sub_records:
            _sub_records[identity].calls += 1
            _sub_records[identity].time += end - _sub_record_start
        else:
            _sub_records[identity] = {
                'calls': 1,
                'time': end - _sub_record_start,
            }
        _sub_record_start = None  # type: Optional[int]


def start_main_record():
    # type: () -> None
    if _main_recording_now:
        global _main_loop_record_start
        _main_loop_record_start = Game.cpu.getUsed()


def finish_main_record():
    # type: () -> None
    if _main_recording_now and _main_loop_record_start is not None:
        end = Game.cpu.getUsed()
        if '_main' in _averages:
            _averages['_main'] += end - _main_loop_record_start
        else:
            _averages['_main'] = end - _main_loop_record_start
        if '_total' in _averages:
            _averages['_total'] += end
        else:
            _averages['_total'] = end
        if '_ticks' in _averages:
            _averages['_ticks'] += 1
        else:
            _averages['_ticks'] = 1
        if _sub_recording_now:
            if '_ticks' in _sub_records:
                _sub_records['_ticks'] += 1
            else:
                _sub_records['_ticks'] = 1


def record_memory_amount(time):
    # type: (int) -> None
    if _main_recording_now:
        if 'memory.init' in _averages:
            _averages['memory.init'].calls += 1
            _averages['memory.init'].time += time
        else:
            _averages['memory.init'] = {
                'calls': 1,
                'time': time,
            }


# `(a / b).toFixed(2)` is incorrectly translated to `a / b.toFixed(2)` instead of `(a / b).toFixed(2)`
def display_num(num, val = 2):
    # type: (Any, int) -> str
    return num.toFixed(val)


def output_records_full():
    # type: () -> str
    rows = ["time\tcalls\ttime/t\tcalls/t\taverage\tname"]
    total_time_in_records = 0
    for identity, obj in _(_averages).pairs().sortBy(lambda t: -t[1].time).value():
        if identity.startswith('_'):
            continue
        if identity != 'memory.init' and identity != 'code.compile':
            total_time_in_records += obj.time
        rows.push("\n{}\t{}\t{}\t{}\t{}\t{}".format(
            display_num(obj.time),
            display_num(obj.calls, 1),
            display_num(obj.time / _averages['_ticks']),
            display_num(obj.calls / _averages['_ticks']),
            display_num(obj.time / obj.calls),
            identity,
        ))
    missing_time = _averages['_main'] - total_time_in_records
    rows.push("\n{}\t{}\t{}\t{}\t{}\t{}".format(
        display_num(missing_time),
        display_num(_averages['_ticks']),
        display_num(missing_time / _averages['_ticks']),
        display_num(1),
        display_num(missing_time / _averages['_ticks']),
        'unprofiled',
    ))
    rows.push("\n{}\t{}\t{}\t{}\t{}\t{}".format(
        display_num(_averages['_main']),
        display_num(_averages['_ticks']),
        display_num(_averages['_main'] / _averages['_ticks']),
        display_num(1),
        display_num(_averages['_main'] / _averages['_ticks']),
        'total.main_loop',
    ))
    compile_time = _averages['_total'] - _averages['_main'] - _averages['memory.init']
    rows.push("\n{}\t{}\t{}\t{}\t{}\t{}".format(
        display_num(compile_time),
        display_num(_averages['_ticks']),
        display_num(compile_time / _averages['_ticks']),
        display_num(1),
        display_num(compile_time / _averages['_ticks']),
        'total.compile'.format(Game.cpu.limit),
    ))
    rows.push("\n{}\t{}\t{}\t{}\t{}\t{}".format(
        display_num(_averages['_total']),
        display_num(_averages['_ticks']),
        display_num(_averages['_total'] / _averages['_ticks']),
        display_num(1),
        display_num(_averages['_total'] / _averages['_ticks']),
        'total (limit: {})'.format(Game.cpu.limit),
    ))
    return "".join(rows)


def output_records():
    # type: () -> str
    if not _averages['_ticks']:
        return "no data collected"
    rows = ["time/t\tcalls/t\taverage\tname"]
    total_time_in_records = 0
    for identity, obj in _(_averages).pairs().sortBy(lambda t: -t[1].time).value():
        if identity.startswith('_'):
            continue

        if identity != 'memory.init' and identity != 'code.compile':
            total_time_in_records += obj.time

        rows.push("\n{}\t{}\t{}\t{}".format(
            display_num(obj.time / _averages['_ticks']),
            display_num(obj.calls / _averages['_ticks'], 1),
            display_num(obj.time / obj.calls),
            identity,
        ))
    missing_time = _averages['_main'] - total_time_in_records
    rows.push("\n{}\t{}\t{}\t{}".format(
        display_num(missing_time / _averages['_ticks']),
        display_num(1, 1),
        display_num(missing_time / _averages['_ticks']),
        'unprofiled',
    ))
    rows.push("\n{}\t{}\t{}\t{}".format(
        display_num(_averages['_main'] / _averages['_ticks']),
        display_num(1, 1),
        display_num(_averages['_main'] / _averages['_ticks']),
        'total.main_loop'.format(Game.cpu.limit),
    ))
    compile_time = _averages['_total'] - _averages['_main'] - _averages['memory.init'].time
    rows.push("\n{}\t{}\t{}\t{}".format(
        display_num(compile_time / _averages['_ticks']),
        display_num(1, 1),
        display_num(compile_time / _averages['_ticks']),
        'total.compile'.format(Game.cpu.limit),
    ))
    rows.push("\n{}\t{}\t{}\t{}".format(
        display_num(_averages['_total'] / _averages['_ticks']),
        display_num(1, 1),
        display_num(_averages['_total'] / _averages['_ticks']),
        'total (limit: {})'.format(Game.cpu.limit),
    ))
    return "".join(rows)


def output_sub_records():
    # type: () -> str
    if not _sub_records['_ticks']:
        return "no data collected"
    rows = ["time/t\tcalls/t\taverage\tname"]
    total_time_in_records = 0
    for identity, obj in _(_sub_records).pairs().sortBy(lambda t: -t[1].time).value():
        if identity.startswith('_'):
            continue

        if identity != 'memory.init' and identity != 'code.compile':
            total_time_in_records += obj.time

        rows.push("\n{}\t{}\t{}\t{}".format(
            display_num(obj.time / _sub_records['_ticks']),
            display_num(obj.calls / _sub_records['_ticks'], 1),
            display_num(obj.time / obj.calls),
            identity,
        ))
    return "".join(rows)

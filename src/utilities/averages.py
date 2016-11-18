from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def start_main_loop():
    if 'cpu_usage' not in Memory:
        Memory.cpu_usage = {}
    volatile_cache.volatile().set("main_loop_start_cpu", Game.cpu.getUsed())
    clean_and_prepare_memory_array("bucket")
    Memory.cpu_usage["bucket"].push(Game.cpu.bucket)


def clean_and_prepare_memory_array(name):
    array = Memory.cpu_usage[name]
    if array is undefined:
        Memory.cpu_usage[name] = []
    elif len(array) > 400:
        Memory.cpu_usage[name] = array.slice(len(array) - 300)


def end_main_loop():
    clean_and_prepare_memory_array("with-cl")
    clean_and_prepare_memory_array("without-cl")
    clean_and_prepare_memory_array("creep-count")
    Memory.cpu_usage["without-cl"].push(round(Game.cpu.getUsed()
                                              - volatile_cache.volatile().get("main_loop_start_cpu")))
    Memory.cpu_usage["with-cl"].push(round(Game.cpu.getUsed()))
    Memory.cpu_usage["creep-count"].push(_.size(Game.creeps))


def get_average(name, count=None):
    tick_array = Memory.cpu_usage and Memory.cpu_usage[name] or []
    if count and count < len(tick_array):
        tick_array = tick_array.slice(len(tick_array) - count)
    if len(tick_array):
        sum = 0
        for x in tick_array:
            sum += x
        return display_num(sum / len(tick_array))


def get_average_range(name, start, end):
    tick_array = Memory.cpu_usage and Memory.cpu_usage[name] or []
    if end < 0 or start > len(tick_array) or end > len(tick_array) or not end < start:
        return None
    sum = 0
    for i in range(len(tick_array) - end, len(tick_array) - start):
        sum += tick_array[i]
    return display_num(sum / len(tick_array))


def get_bucket_trend(end_ago, start_ago):
    tick_array = _.get(Memory, 'cpu_usage.bucket', [])
    if not (end_ago < start_ago < len(tick_array)):
        return "not enough data"
    value = tick_array[len(tick_array) - 1 - end_ago] - tick_array[len(tick_array) - 1 - start_ago]
    if value > 0:
        return "+{}".format(value)
    else:
        return value


def get_average_visual():
    # TODO: do this better
    with_cl = get_average("with-cl")
    without_cl = get_average("without-cl")
    creeps = get_average("creep-count")
    with_cl50 = get_average("with-cl", 50)
    without_cl50 = get_average("without-cl", 50)
    creeps50 = get_average("creep-count", 50)
    return (
        "\nReport:"
        "\n1000 ticks:"
        "\nAvg CPU: {}"
        "\t(Runtime: {})"
        "\ncreep #: {}"
        "\tCPU/creep: {}"
        "\n50 ticks average:"
        "\nCPU: {}"
        "\t(Runtime: {})"
        "\ncreep #: {}"
        "\tCPU/creep: {}"
        "\nBucket trends:"
        "\t(now: {})"
        "\n50: {}"
        "\t100: {}"
        "\t500: {}"
        "\t1000: {}".format(
            with_cl,
            without_cl,
            creeps,
            round(with_cl / creeps * 10) / 10,
            with_cl50,
            without_cl50,
            creeps50,
            round(with_cl50 / creeps50 * 10) / 10,
            Game.cpu.bucket,
            get_bucket_trend(0, 50),
            get_bucket_trend(0, 100),
            get_bucket_trend(0, 500),
            get_bucket_trend(0, 1000),
        )
    )


###
# Creep role recording
###

_recording_now = False
_single_record_start = None
_main_loop_record_start = None
_averages = None


def prep_recording():
    global _recording_now, _averages
    _averages = Memory['_averages']
    if not _averages:
        _averages = Memory['_averages'] = {}
    _recording_now = not not _averages['_recording_now']


def start_recording():
    Memory['_averages']['_recording_now'] = True


def stop_recording():
    Memory['_averages']['_recording_now'] = False


def reset_records():
    Memory['_averages'] = {}


def start_record():
    if _recording_now:
        global _single_record_start
        _single_record_start = Game.cpu.getUsed()


def finish_record(identity):
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


def start_main_record():
    if _recording_now:
        global _main_loop_record_start
        _main_loop_record_start = Game.cpu.getUsed()


def finish_main_record():
    if _recording_now and _main_loop_record_start is not None:
        end = Game.cpu.getUsed()
        if '_main' in _averages:
            _averages['_main'] += end - _main_loop_record_start
        else:
            _averages['_main'] = end - _main_loop_record_start
        if '_ticks' in _averages:
            _averages['_ticks'] += 1
        else:
            _averages['_ticks'] = 1


def record_memory_amount(time):
    if _recording_now:
        if 'memory.init' in _averages:
            _averages['memory.init'].calls += 1
            _averages['memory.init'].time += time
        else:
            _averages['memory.init'] = {
                'calls': 1,
                'time': time,
            }


# `(a / b).toFixed(2)` is incorrectly translated to `a / b.toFixed(2)` instead of `(a / b).toFixed(2)`
def display_num(num, val=2):
    """
    :type num:  float
    """
    return num.toFixed(val)


def output_records_full():
    rows = ["time\tcalls\ttime/t\tcalls/t\taverage\tname"]
    total_time_in_records = 0
    for identity, obj in _(_averages).pairs().sortBy(lambda t: -t[1].time).value():
        if identity == '_recording_now' or identity == '_ticks' or identity == '_main':
            continue
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
    return "".join(rows)


def output_records():
    if not _averages['_ticks']:
        return "no data collected"
    rows = ["time/t\tcalls/t\taverage\tname"]
    total_time_in_records = 0
    for identity, obj in _(_averages).pairs().sortBy(lambda t: -t[1].time).value():
        if identity == '_recording_now' or identity == '_ticks' or identity == '_main':
            continue

        total_time_in_records += obj.time

        rows.push("\n{}\t{}\t{}\t{}".format(
            display_num(obj.time / _averages['_ticks']),
            display_num(obj.calls / _averages['_ticks'], 1),
            display_num(obj.time / obj.calls),
            identity,
        ))
    missing_time = _averages['_main'] + _averages['memory.init'].time - total_time_in_records
    rows.push("\n{}\t{}\t{}\t{}".format(
        display_num(missing_time / _averages['_ticks']),
        display_num(1, 1),
        display_num(missing_time / _averages['_ticks']),
        'unprofiled',
    ))
    return "".join(rows)

/**
 * Recording module, for very specific top-level CPU recording.
 *
 * Example usage:
 *

 // with other imports
 const records = require('records');

 module.exports.loop = function() {
    // must be run before any other records function within each tick
    records.prep_recording();
    // usually run at start of loop to gather maximum data
    records.start_main_record();

    // ...

    // throughout function, surround each separate piece with this:
    records.start_record();
    // do things
    records.finish_record('description.of.thing.just.done');
    // for example:
    for (let name in Game.creeps) {
        records.start_record();
        let creep = Game.creeps[name];
        roleFunctions[creep.memory.role]();
        records.finish_record('roles.' + creep.memory.role);
    }
    if (Game.time % 10 === 0) {
        records.start_record();
        cleanupMemory();
        records.finish_record('memory.cleanup');
    }

    // IMPORTANT NOTE:
    // Records is built to be lean and fast, and thus does not support recording multiple things at the same time.
    // You can't both do a 'total creep' and a 'per-creep' record, you must only be running a single record at a time.
    // It won't error if you do do multiple at the same time, but only the inner-most record will recorded successfully,
    // and all other records running at the same time will recieve incorrect data.

    // ...

    // at the very end of your main loop, run this to commit all records and track the total CPU used.
    records.finish_main_record();
}

 * Then, via console, you can control the records module!
 *
 * To enable all recording functions, run in the console:
 * > records.start()
 * To output everything gathered so far, run in the console:
 * > records.output()
 * To reset all data and stop recording, run in the console:
 * > records.reset()
 * To stop recording, but keep data to be resumed on next start, run in the console:
 * > records.stop()
 *
 * Here's some example output! Taken from my project, using records.js.
 *
> py.records.output()
time/t	calls/t	average	name
32.28	72.79	0.44	hauler
22.10	68.80	0.32	miner
12.56	1.00	12.56	memory.init
9.92	19.46	0.51	builder
7.92	13.96	0.57	upgrader
6.87	20.89	0.33	tower_fill
6.16	31.00	0.20	spawn.tick
5.52	238.82	0.02	hive.wrap-creep
4.72	1.00	4.72	hive.poll-creeps
3.79	12.03	0.32	spawn_fill
3.75	4.32	0.87	kiting_offense
3.58	12.00	0.30	links.tick
2.85	1.00	2.85	defense.poll-hostiles
1.95	12.00	0.16	defense.tick
1.85	11.00	0.17	link_manager
1.31	4.50	0.29	remote_reserve_controller
1.18	0.02	49.97	code.compile
1.16	0.25	4.62	building.roads.cache-checks-only
0.88	1.00	0.88	auto.pickup
0.81	0.61	1.32	simple_defender
0.60	12.00	0.05	room.tick
0.57	1.00	0.57	local_mineral_hauler
0.46	8.27	0.06	scout
0.37	1.00	0.37	hive.init
0.25	12.00	0.02	building.ramparts
0.23	12.00	0.02	terminal.tick
0.20	1.00	0.20	local_mineral_miner
0.20	0.06	3.55	mining.cleanup_flags
0.13	0.18	0.71	recycling
0.04	0.00	7.79	building.roads.check-pavement
0.02	1.00	0.02	bucket.check
0.02	1.00	0.02	deathwatch.check
0.01	0.02	0.76	auto.running-memory-cleanup
0.01	0.04	0.26	defense.clean-hostiles
0.01	1.00	0.01	locations.init
0.01	1.00	0.01	hive.poll-rooms
0.00	1.00	0.00	flags.move
2.45	1.00	2.45	unprofiled
123.01	1.00	123.01	total.main_loop
2.49	1.00	2.49	total.compile
138.05	1.00	138.05	total (limit: 140)
 *
 */
let _recording_now;
let _sub_recording_now;
let _single_record_start;
let _sub_record_start;
let _main_loop_record_start;
let _averages;
let _sub_records;
function prep_recording() {
    _averages = Memory['_averages'];
    if (!_averages) {
        Memory['_averages'] = _averages = {};
    }
    _recording_now = !!_averages['_recording_now'];
}
function start_recording() {
    Memory['_averages']['_recording_now'] = true;
}
function stop_recording() {
    Memory['_averages']['_recording_now'] = false;
    Memory['_sub_recording_now'] = false;
}
function start_sub_recording() {
    Memory['_averages']['_sub_recording_now'] = true;
    Memory['_averages']['_recording_now'] = true;
}
function reset_records() {
    Memory['_averages'] = {};
}
function start_record() {
    if (_recording_now) {
        _single_record_start = Game.cpu.getUsed();
    }
}
function finish_record(identity) {
    if (_recording_now && _single_record_start !== null) {
        const end = Game.cpu.getUsed();
        if ((identity in _averages)) {
            _averages[identity].calls++;
            _averages[identity].time += end - _single_record_start;
        }
        else {
            _averages[identity] = {'calls': 1, 'time': end - _single_record_start};
        }
    }
}
function start_main_record() {
    if (_recording_now) {
        _main_loop_record_start = Game.cpu.getUsed();
    }
}
function finish_main_record() {
    if (_recording_now && _main_loop_record_start !== null) {
        const end = Game.cpu.getUsed();
        if (('_main' in _averages)) {
            _averages['_main'] += end - _main_loop_record_start;
        }
        else {
            _averages['_main'] = end - _main_loop_record_start;
        }
        if (('_total' in _averages)) {
            _averages['_total'] += end;
        }
        else {
            _averages['_total'] = end;
        }
        if (('_ticks' in _averages)) {
            _averages['_ticks']++;
        }
        else {
            _averages['_ticks'] = 1;
        }
        if (_sub_recording_now) {
            if (('_ticks' in _sub_records)) {
                _sub_records['_ticks']++;
            }
            else {
                _sub_records['_ticks'] = 1;
            }
        }
    }
}
function record_memory_amount(time) {
    if (_recording_now) {
        if (('memory.init' in _averages)) {
            _averages['memory.init'].calls++;
            _averages['memory.init'].time += time;
        }
        else {
            _averages['memory.init'] = {'calls': 1, 'time': time};
        }
    }
}
function record_compile_amount(time) {
    if (_recording_now) {
        if (('code.compile' in _averages)) {
            _averages['code.compile'].calls++;
            _averages['code.compile'].time += time;
        }
        else {
            _averages['code.compile'] = {'calls': 1, 'time': time};
        }
    }
}
function output_records() {
    if (!(_averages['_ticks'])) {
        return 'no data collected';
    }
    const averages_sorted = _(_averages).pairs().sortBy(t => -t[1].time).value();
    const total_ticks = _averages['_ticks'];
    const rows = ['time/t\tcalls/t\taverage\tname'];
    let total_time_in_records = 0;
    for (let [identity, obj] of averages_sorted) {
        if (identity.startswith('_')) {
            continue;
        }
        if (identity != 'memory.init' && identity != 'code.compile') {
            total_time_in_records += obj.time;
        }
        rows.push(`\n${(obj.time / total_ticks).toFixed(2)
                      }\t${(obj.calls / total_ticks).toFixed(2)
                      }\t${(obj.time / obj.calls).toFixed(2)
                      }\t${identity}`);
    }

    const total_time_main = _averages['_main'];
    const total_total = _averages['_total'];
    const missing_time = total_time_main - total_time_in_records;
    const compile_time = total_total - total_time_main - (_averages['memory.init'] ? _averages['memory.init'].time : 0);
    rows.push(`\n${(missing_time / total_ticks).toFixed(2)
                  }\t${(1).toFixed(2)
                  }\t${(missing_time / total_ticks).toFixed(2)
                  }\tunprofiled`);

    rows.push(`\n${(total_time_main / total_ticks).toFixed(2)
                  }\t${(1).toFixed(2)
                  }\t${(total_time_main / total_ticks).toFixed(2)
                  }\ttotal.main_loop`);
    rows.push(`\n${(compile_time / total_ticks).toFixed(2)
                  }\t${(1).toFixed(2)
                  }\t${(compile_time / total_ticks).toFixed(2)
                  }\ttotal.compile`);
    rows.push(`\n${(total_total / total_ticks).toFixed(2)
                  }\t${(1).toFixed(2)
                  }\t${(total_total / total_ticks).toFixed(2)
                  }\ttotal (limit: ${Game.cpu.limit})`);

    return ''.join(rows);
}

// Console commands
const records_export_obj = {
    // Trigger to start recording.
    'start': start_recording,
    // Trigger to stop recording.
    'stop': stop_recording,
    // Trigger to reset all records and stop recording
    'reset': reset_records,
    // Trigger to output all records to console
    'output': output_records,
    // Function which must be run once per tick whether recording or not, before any other function is called.
    'prep_recording': prep_recording,
    // Function to run at start of main loop.
    'start_main_record': start_main_record,
    // Function to run at end of main loop.
    'finish_main_record': finish_main_record,
    // Function to run before each specific profiled thing.
    'start_record': start_record,
    // Function to run after each specific profiled thing (with a identity parameter to identify it with)
    'finish_record': finish_record,
};

// gives access to run via console with just, 'records.start()', 'records.output()', 'records.reset()'
global.records = records_export_obj;

module.exports = records_export_obj;
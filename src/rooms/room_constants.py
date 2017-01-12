from jstools.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

min_total_pause_remote_mining = 950 * 1000
min_energy_pause_remote_mining = 150 * 1000
max_total_resume_remote_mining = 700 * 1000
max_energy_resume_remote_mining = 50 * 1000
min_work_mass_per_source_for_full_storage_use = 15

min_energy_enable_full_storage_use = 10 * 1000
max_energy_disable_full_storage_use = 5 * 1000
energy_to_resume_upgrading = 14 * 1000
energy_to_pause_upgrading = 8 * 1000
rcl8_energy_to_resume_upgrading = 100 * 1000
rcl8_energy_to_pause_upgrading = 50 * 1000
energy_to_pause_building = 14 * 1000
energy_to_resume_building = 28 * 1000
min_stored_energy_to_draw_from_before_refilling = 20 * 1000

rcl_to_min_wall_hits = [
    1,  # RCL 1
    20 * 1000,  # RCL 2
    50 * 1000,  # RCL 3
    150 * 1000,  # RCL 4
    500 * 1000,  # RCL 5
    1000 * 1000,  # RCL 6
    3 * 1000 * 1000,  # RCL 7
    10 * 1000 * 1000,  # RCL 8
]
rcl_to_sane_wall_hits = [
    2,  # RCL 1
    40 * 1000,  # RCL 2
    80 * 1000,  # RCL 3
    250 * 1000,  # RCL 4
    1000 * 1000,  # RCL 5
    1500 * 1000,  # RCL 6
    5 * 1000 * 1000,  # RCL 7
    100 * 1000 * 1000  # RCL 8
]

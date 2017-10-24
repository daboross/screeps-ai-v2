from constants import ABANDON_ALL
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

rcl_to_target_wall_hits = [
    1,  # RCL 1
    20 * 1000,  # RCL 2
    50 * 1000,  # RCL 3
    150 * 1000,  # RCL 4
    500 * 1000,  # RCL 5
    1000 * 1000,  # RCL 6
    3 * 1000 * 1000,  # RCL 7
    10 * 1000 * 1000,  # RCL 8
]
rcl_to_max_wall_hits = [
    2,  # RCL 1
    40 * 1000,  # RCL 2
    80 * 1000,  # RCL 3
    250 * 1000,  # RCL 4
    1000 * 1000,  # RCL 5
    1500 * 1000,  # RCL 6
    5 * 1000 * 1000,  # RCL 7
    20 * 1000 * 1000 if ABANDON_ALL else WALL_HITS_MAX,  # RCL 8
]

if ABANDON_ALL:
    energy_to_keep_always_in_reserve = STORAGE_CAPACITY / 10
    energy_to_keep_always_in_reserve_when_supporting_sieged = energy_to_keep_always_in_reserve * 0.25
    energy_pre_rcl8_scaling_balance_point = energy_to_keep_always_in_reserve * 1.1
    energy_pre_rcl8_building_when_upgrading_balance_point = energy_pre_rcl8_scaling_balance_point * 1.5
    energy_balance_point_for_rcl8_upgrading = energy_to_keep_always_in_reserve * 1.1
    energy_balance_point_for_rcl8_building = energy_balance_point_for_rcl8_upgrading * 1.1
    energy_balance_point_for_rcl8_supporting = energy_balance_point_for_rcl8_upgrading * 1.1
    energy_balance_point_for_rcl8_selling = energy_to_keep_always_in_reserve * 0.6
    energy_at_which_to_stop_supporting = energy_to_keep_always_in_reserve * 1.5

    energy_to_keep_always_in_reserve_urgent = STORAGE_CAPACITY / 20
    energy_to_keep_always_in_reserve_when_supporting_sieged_urgent = energy_to_keep_always_in_reserve_urgent * 0.25
    energy_pre_rcl8_scaling_balance_point_urgent = energy_to_keep_always_in_reserve_urgent * 1.1
    energy_balance_point_for_rcl8_upgrading_urgent = energy_to_keep_always_in_reserve_urgent * 1.1
    energy_balance_point_for_rcl8_building_urgent = energy_balance_point_for_rcl8_upgrading_urgent * 1.1
    energy_balance_point_for_rcl8_supporting_urgent = energy_balance_point_for_rcl8_upgrading_urgent * 1.1
    energy_balance_point_for_rcl8_selling_urgent = energy_to_keep_always_in_reserve_urgent * 0.6
    energy_at_which_to_stop_supporting_urgent = energy_to_keep_always_in_reserve_urgent * 1.5

    max_minerals_to_keep = 2000

    energy_for_terminal_when_selling = TERMINAL_CAPACITY / 2
else:
    energy_to_keep_always_in_reserve = STORAGE_CAPACITY / 2
    energy_to_keep_always_in_reserve_when_supporting_sieged = energy_to_keep_always_in_reserve * 0.25
    energy_pre_rcl8_scaling_balance_point = energy_to_keep_always_in_reserve * 1.1
    energy_pre_rcl8_building_when_upgrading_balance_point = energy_pre_rcl8_scaling_balance_point * 1.5
    energy_balance_point_for_rcl8_upgrading = energy_to_keep_always_in_reserve * 1.1
    energy_balance_point_for_rcl8_building = energy_balance_point_for_rcl8_upgrading * 1.1
    energy_balance_point_for_rcl8_supporting = energy_balance_point_for_rcl8_upgrading * 1.1
    energy_balance_point_for_rcl8_selling = energy_to_keep_always_in_reserve * 0.6
    energy_at_which_to_stop_supporting = energy_to_keep_always_in_reserve * 1.5

    energy_to_keep_always_in_reserve_urgent = STORAGE_CAPACITY / 8
    energy_to_keep_always_in_reserve_when_supporting_sieged_urgent = energy_to_keep_always_in_reserve_urgent * 0.25
    energy_pre_rcl8_scaling_balance_point_urgent = energy_to_keep_always_in_reserve_urgent * 1.1
    energy_balance_point_for_rcl8_upgrading_urgent = energy_to_keep_always_in_reserve_urgent * 1.1
    energy_balance_point_for_rcl8_building_urgent = energy_balance_point_for_rcl8_upgrading_urgent * 1.1
    energy_balance_point_for_rcl8_supporting_urgent = energy_balance_point_for_rcl8_upgrading_urgent * 1.1
    energy_balance_point_for_rcl8_selling_urgent = energy_to_keep_always_in_reserve_urgent * 0.6
    energy_at_which_to_stop_supporting_urgent = energy_to_keep_always_in_reserve_urgent * 1.5

    max_minerals_to_keep = STORAGE_CAPACITY / 4

    energy_for_terminal_when_selling = TERMINAL_CAPACITY / 2

room_spending_state_building = 'b'
room_spending_state_upgrading = 'u'
room_spending_state_rcl8_building = '8'
room_spending_state_saving = 's'
room_spending_state_supporting = 'p'
room_spending_state_supporting_sieged = 'r'
room_spending_state_under_siege = 'n'
room_spending_state_selling = 'l'
room_spending_state_selling_and_rcl8building = 'a'
room_spending_state_selling_and_building = 'c'
room_spending_state_selling_and_upgrading = 'd'
room_spending_state_selling_and_supporting = 'e'

# s/room_spending_state_([^ \n]+) = '([^'\n]+)'\n/'$2': "$1",\n/
room_spending_state_visual = {
    'b': "building",
    'u': "upgrading",
    '8': "rcl8_building",
    's': "saving",
    'p': "supporting",
    'r': "supporting_sieged",
    'n': "under_siege",
    'l': "selling",
    'a': "selling_and_rcl8building",
    'c': "selling_and_building",
    'd': "selling_and_upgrading",
    'e': "selling_and_supporting"
}

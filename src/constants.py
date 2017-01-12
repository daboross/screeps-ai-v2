from jstools.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

# Creep base parts
creep_base_worker = "worker"
creep_base_1500miner = "fast_small_miner"
creep_base_3000miner = "fast_big_miner"
creep_base_4000miner = "faster_bigger_miner"
creep_base_carry3000miner = "fast_miner_with_carry"
creep_base_hauler = "med_hauler"
creep_base_half_move_hauler = "hm_hauler"
creep_base_work_full_move_hauler = "fw_fm_hauler"
creep_base_work_half_move_hauler = "fw_hm_hauler"
creep_base_full_upgrader = "min_carry_worker"
creep_base_reserving = "remote_reserve"
creep_base_claiming = "strong_claim"
creep_base_claim_attack = "claim_attack"
creep_base_defender = "simple_defender"
creep_base_mammoth_miner = "mammoth_miner"
creep_base_half_move_healer = "hm_healer"
creep_base_full_move_healer = "fm_healer"
creep_base_goader = "med_goader"
creep_base_full_move_goader = "fm_goader"
creep_base_dismantler = "med_dismantle"
creep_base_full_move_dismantler = "fm_dismantle"
creep_base_power_attack = "power_attack"
creep_base_full_move_power_attack = "fm_power_attack"
creep_base_scout = "scout"
creep_base_rampart_defense = "rampart_defender"
creep_base_ranged_offense = "ranged_offensive"
creep_base_3h = "ranged_3h"

# TODO: 1-move "observer" base/role which moves to another room and then just pathfinds away from the edges of the room,
# and away from enemies. (or improve scout)

# Hive Mind TargetMind possible targets
# Generic targets: 0*
target_source = 0
target_closest_energy_site = 1
target_single_flag = 2
target_single_flag2 = 3
target_home_flag = 4
target_refill = 5
# Builder targets: 1*
target_construction = 10
target_repair = 11
target_big_repair = 12
target_big_big_repair = 13
target_destruction_site = 14
# Spawn filler / tower filler: 2*
target_spawn_deposit = 20
target_tower_fill = 21
# Energy miner / hauler: 3*
target_energy_miner_mine = 30
target_energy_hauler_mine = 31
target_reserve_now = 32
# Other military: 4*
target_rampart_defense = 40

role_upgrader = "upgrader"
role_spawn_fill_backup = "spawn_fill_backup"
role_spawn_fill = "spawn_fill"
role_upgrade_fill = "ufiller"
role_builder = "builder"
role_tower_fill = "tower_fill"
role_tower_fill_once = "tfo"
role_miner = "miner"
role_hauler = "hauler"
role_remote_mining_reserve = "remote_reserve_controller"
role_link_manager = "link_manager"
role_defender = "simple_defender"
role_wall_defender = "melee_wall_defender"
role_ranged_offense = "kiting_offense"
role_colonist = "colonist"
role_simple_claim = "simple_claim"
role_room_reserve = "top_priority_reserve"
role_cleanup = "simple_cleanup"
role_temporary_replacing = "currently_replacing"
role_recycling = "recycling"
role_mineral_steal = "steal_minerals"
role_mineral_miner = "local_mineral_miner"
role_mineral_hauler = "local_mineral_hauler"
role_td_healer = "tower_drain_healer"
role_td_goad = "tower_drain_goader"
role_simple_dismantle = "simple_dismantler"
role_energy_grab = "egrab"
role_power_attack = "attack_power"
role_power_cleanup = "power_cleanup"
role_scout = "scout"

old_role_names = {
    "ufiller": "upgrade_fill",
    "remote_miner": "miner",
    "remote_hauler": "hauler",
    "basic_colonist": "colonist",
}

role_bases = {
    role_spawn_fill_backup: creep_base_worker,
    role_spawn_fill: creep_base_hauler,
    role_upgrade_fill: creep_base_hauler,
    role_builder: creep_base_worker,
    role_tower_fill: creep_base_hauler,
    role_remote_mining_reserve: creep_base_reserving,
    role_link_manager: creep_base_half_move_hauler,
    role_defender: creep_base_defender,
    role_wall_defender: creep_base_rampart_defense,
    role_cleanup: creep_base_hauler,
    role_colonist: creep_base_worker,
    role_simple_claim: creep_base_claiming,
    role_room_reserve: creep_base_reserving,
    role_mineral_miner: creep_base_mammoth_miner,
    role_mineral_hauler: creep_base_hauler,
    role_simple_dismantle: creep_base_dismantler,
    role_scout: creep_base_scout,
    role_mineral_steal: creep_base_half_move_hauler,
}

default_roles = {
    creep_base_worker: role_spawn_fill_backup,
    creep_base_1500miner: role_miner,
    creep_base_3000miner: role_miner,
    creep_base_4000miner: role_miner,
    creep_base_carry3000miner: role_miner,
    creep_base_hauler: role_hauler,
    creep_base_work_full_move_hauler: role_hauler,
    creep_base_work_half_move_hauler: role_hauler,
    creep_base_reserving: role_remote_mining_reserve,
    creep_base_defender: role_defender,
    creep_base_mammoth_miner: role_mineral_miner,
    creep_base_goader: role_td_goad,
    creep_base_full_move_goader: role_td_goad,
    creep_base_half_move_healer: role_td_healer,
    creep_base_full_move_healer: role_td_healer,
    creep_base_dismantler: role_simple_dismantle,
    creep_base_full_move_dismantler: role_simple_dismantle,
    creep_base_full_upgrader: role_upgrader,
    creep_base_scout: role_scout,
    creep_base_power_attack: role_power_attack,
    creep_base_full_move_power_attack: role_power_attack,
    creep_base_rampart_defense: role_wall_defender,
    creep_base_claim_attack: role_simple_claim,
}

# Flag types / hints

# Generic / home-type flags flags: 0*
DEPOT = 0
UPGRADER_SPOT = 1
SPAWN_FILL_WAIT = 2
# PathFinding flags: 1*
REROUTE = 10
REROUTE_DESTINATION = 11
SLIGHTLY_AVOID = 12
SK_LAIR_SOURCE_NOTED = 13
# Energy miner / hauler: 2*
REMOTE_MINE = 20
LOCAL_MINE = 21
RESERVE_NOW = 22
CLAIM_LATER = 23
# Military: 5*
SCOUT = 50
RANGED_DEFENSE = 51
ATTACK_DISMANTLE = 52
ENERGY_GRAB = 53
RAMPART_DEFENSE = 54
RAID_OVER = 59
# Overly specific / soon to be removed military: 6*
TD_H_H_STOP = 60
TD_H_D_STOP = 61
TD_D_GOAD = 62
ATTACK_POWER_BANK = 65
REAP_POWER_BANK = 66
# Find constants

PYFIND_REPAIRABLE_ROADS = 1001
PYFIND_BUILDABLE_ROADS = 1002
PYFIND_HURT_CREEPS = 1003
INVADER_USERNAME = "Invader"
SK_USERNAME = "Source Keeper"

recycle_time = 50

request_priority_imminent_threat_defense = 1
request_priority_economy = 5
request_priority_helping_party = 9
request_priority_low = 20

min_repath_mine_roads_every = 200 * 1000
max_repath_mine_roads_every = 250 * 1000

min_repave_mine_roads_every = 20 * 1000
max_repave_mine_roads_every = 25 * 1000

global_cache_mining_roads_suffix = '_mrd'

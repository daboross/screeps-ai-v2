from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

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

# TODO: 1-move "observer" base/role which moves to another room and then just pathfinds away from the edges of the room,
# and away from enemies. (or improve scout)

# Hive Mind TargetMind possible targets
target_source = "source"
target_big_source = "dedicated_miner_source"
target_construction = "construction_site"
target_repair = "repair_site"
target_big_repair = "extra_repair_site"
target_destruction_site = "destruction_site"
target_spawn_deposit = "spawn_deposit_site"
target_tower_fill = "fillable_tower"
target_remote_mine_miner = "remote_miner_mine"
target_remote_mine_hauler = "remote_mine_hauler"
target_closest_energy_site = "generic_deposit"
target_reserve_now = "top_priority_reserve"
target_single_flag = "sccf"  # single creep, closest flag
target_single_flag2 = "sccf2"  # single creep, closest flag
target_refill = "refill"
target_rampart_defense = "rampart_def"

role_upgrader = "upgrader"
role_spawn_fill_backup = "spawn_fill_backup"
role_spawn_fill = "spawn_fill"
role_builder = "builder"
role_tower_fill = "tower_fill"
role_miner = "remote_miner"
role_hauler = "remote_hauler"
role_remote_mining_reserve = "remote_reserve_controller"
role_link_manager = "link_manager"
role_defender = "simple_defender"
role_colonist = "basic_colonist"
role_wall_defender = "melee_wall_defender"
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
role_power_attack = "attack_power"
role_power_cleanup = "power_cleanup"
role_scout = "scout"

role_bases = {
    role_spawn_fill_backup: creep_base_worker,
    role_spawn_fill: creep_base_hauler,
    role_builder: creep_base_worker,
    role_tower_fill: creep_base_hauler,
    role_remote_mining_reserve: creep_base_reserving,
    role_link_manager: creep_base_hauler,
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
}

PYFIND_REPAIRABLE_ROADS = 101  #"pyfind_repairable_roads"
PYFIND_BUILDABLE_ROADS = 102  #"pyfind_buildable_roads"
PYFIND_HURT_CREEPS = 103  #"pyfind_hurt_creeps"
INVADER_USERNAME = "Invader"
SK_USERNAME = "Source Keeper"

recycle_time = 50

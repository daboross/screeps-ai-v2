from utilities.screeps_constants import *

__pragma__('noalias', 'name')

# Creep base parts
creep_base_worker = "worker"
creep_base_local_miner = "dedicated_miner"
creep_base_full_miner = "fast_big_miner"
creep_base_hauler = "med_hauler"
creep_base_work_full_move_hauler = "fw_fm_hauler"
creep_base_work_half_move_hauler = "fw_hm_hauler"
creep_base_full_upgrader = "min_carry_worker"
creep_base_reserving = "remote_reserve"
creep_base_defender = "simple_defender"
creep_base_mammoth_miner = "mammoth_miner"
creep_base_half_move_healer = "hm_healer"
creep_base_goader = "med_goader"
creep_base_dismantler = "med_dismantle"

# TODO: 1-move "observer" base/role which moves to another room and then just pathfinds away from the edges of the room, and
# away from enemies.

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
creep_base_scout = "scout"

role_upgrader = "upgrader"
role_spawn_fill_backup = "spawn_fill_backup"
role_spawn_fill = "spawn_fill"
role_dedi_miner = "dedicated_miner"
role_builder = "builder"
role_tower_fill = "tower_fill"
role_remote_miner = "remote_miner"
role_remote_hauler = "remote_hauler"
role_remote_mining_reserve = "remote_reserve_controller"
role_local_hauler = "local_hauler"
role_link_manager = "link_manager"
role_defender = "simple_defender"
role_colonist = "basic_colonist"
role_simple_claim = "simple_claim"
role_room_reserve = "top_priority_reserve"
role_cleanup = "simple_cleanup"
role_temporary_replacing = "currently_replacing"
role_recycling = "recycling"
role_mineral_miner = "local_mineral_miner"
role_mineral_hauler = "local_mineral_hauler"
role_td_healer = "tower_drain_healer"
role_td_goad = "tower_drain_goader"
role_simple_dismantle = "simple_dismantler"
role_scout = "scout"

role_bases = {
    role_upgrader: "ask",
    role_spawn_fill_backup: creep_base_worker,
    role_spawn_fill: creep_base_hauler,
    role_dedi_miner: creep_base_local_miner,
    role_builder: creep_base_worker,
    role_tower_fill: creep_base_hauler,
    role_remote_miner: creep_base_full_miner,
    role_remote_hauler: "ask",
    role_remote_mining_reserve: creep_base_reserving,
    role_local_hauler: creep_base_hauler,
    role_link_manager: creep_base_hauler,
    role_defender: creep_base_defender,
    role_cleanup: creep_base_hauler,
    role_colonist: creep_base_worker,
    role_simple_claim: creep_base_reserving,
    role_room_reserve: creep_base_reserving,
    role_mineral_miner: creep_base_mammoth_miner,
    role_mineral_hauler: creep_base_hauler,
    role_td_goad: creep_base_goader,
    role_td_healer: creep_base_half_move_healer,
    role_simple_dismantle: creep_base_dismantler,
    role_scout: creep_base_scout,
}

default_roles = {
    creep_base_worker: role_spawn_fill_backup,
    creep_base_local_miner: role_dedi_miner,
    creep_base_full_miner: role_remote_miner,
    creep_base_hauler: role_cleanup,
    creep_base_work_full_move_hauler: role_remote_hauler,
    creep_base_work_half_move_hauler: role_remote_hauler,
    creep_base_reserving: role_remote_mining_reserve,
    creep_base_defender: role_defender,
    creep_base_mammoth_miner: role_mineral_miner,
    creep_base_goader: role_td_goad,
    creep_base_half_move_healer: role_td_healer,
    creep_base_dismantler: role_simple_dismantle,
    creep_base_full_upgrader: role_upgrader,
    creep_base_scout: role_recycling,
}

PYFIND_REPAIRABLE_ROADS = "pyfind_repairable_roads"
PYFIND_BUILDABLE_ROADS = "pyfind_buildable_roads"

recycle_time = 50

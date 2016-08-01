from utils.screeps_constants import *

__pragma__('noalias', 'name')

# Creep base parts
creep_base_worker = "worker"
creep_base_big_harvester = "big_harvester"
creep_base_full_miner = "fast_big_miner"
creep_base_small_hauler = "small_hauler"
creep_base_hauler = "med_hauler"
creep_base_reserving = "remote_reserve"
creep_base_defender = "simple_defender"

# Hive Mind TargetMind possible targets
target_source = "source"
target_big_source = "big_h_source"
target_construction = "construction_site"
target_repair = "repair_site"
target_big_repair = "extra_repair_site"
target_source_local_hauler = "local_hauler"
target_harvester_deposit = "harvester_deposit_site"
target_tower_fill = "fillable_tower"
target_remote_mine_miner = "remote_miner_mine"
target_remote_mine_hauler = "remote_mine_hauler"
target_remote_reserve = "remote_reserve"
target_closest_deposit_site = "generic_deposit"

role_upgrader = "upgrader"
role_spawn_fill = "harvester"
role_dedi_miner = "big_harvester"
role_builder = "builder"
role_tower_fill = "tower_fill"
role_remote_miner = "remote_miner"
role_remote_hauler = "remote_hauler"
role_remote_mining_reserve = "remote_reserve_controller"
role_local_hauler = "local_hauler"
role_link_manager = "link_manager"
role_defender = "simple_defender"

role_bases = {
    role_upgrader: creep_base_worker,
    role_spawn_fill: creep_base_worker,
    role_dedi_miner: creep_base_big_harvester,
    role_builder: creep_base_worker,
    role_tower_fill: creep_base_worker,
    role_remote_miner: creep_base_full_miner,
    role_remote_hauler: creep_base_hauler,
    role_remote_mining_reserve: creep_base_reserving,
    role_local_hauler: creep_base_hauler,
    role_link_manager: creep_base_small_hauler,
    role_defender: creep_base_defender,
}

default_roles = {
    creep_base_worker: role_upgrader,
    creep_base_big_harvester: role_dedi_miner,
    creep_base_full_miner: role_remote_miner,
    creep_base_small_hauler: role_local_hauler,
    creep_base_hauler: role_local_hauler,
    creep_base_reserving: role_remote_mining_reserve,
    creep_base_defender: role_defender,
}

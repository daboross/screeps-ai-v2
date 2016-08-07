from utilities.screeps_constants import *

__pragma__('noalias', 'name')

# Creep base parts
creep_base_worker = "worker"
creep_base_local_miner = "dedicated_miner"
creep_base_full_miner = "fast_big_miner"
creep_base_small_hauler = "small_hauler"
creep_base_hauler = "med_hauler"
creep_base_reserving = "remote_reserve"
creep_base_defender = "simple_defender"

# Hive Mind TargetMind possible targets
target_source = "source"
target_big_source = "dedicated_miner_source"
target_construction = "construction_site"
target_repair = "repair_site"
target_big_repair = "extra_repair_site"
target_harvester_deposit = "spawn_deposit_site"
target_tower_fill = "fillable_tower"
target_remote_mine_miner = "remote_miner_mine"
target_remote_mine_hauler = "remote_mine_hauler"
target_remote_reserve = "remote_reserve"
target_closest_deposit_site = "generic_deposit"

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
role_cleanup = "simple_cleanup"
role_temporary_replacing = "currently_replacing"

role_bases = {
    role_upgrader: creep_base_worker,
    role_spawn_fill_backup: creep_base_worker,
    role_spawn_fill: creep_base_hauler,
    role_dedi_miner: creep_base_local_miner,
    role_builder: creep_base_worker,
    role_tower_fill: creep_base_hauler,
    role_remote_miner: creep_base_full_miner,
    role_remote_hauler: creep_base_hauler,
    role_remote_mining_reserve: creep_base_reserving,
    role_local_hauler: creep_base_hauler,
    role_link_manager: creep_base_small_hauler,
    role_defender: creep_base_defender,
    role_cleanup: creep_base_hauler,
}

default_roles = {
    creep_base_worker: role_spawn_fill_backup,
    creep_base_local_miner: role_dedi_miner,
    creep_base_full_miner: role_remote_miner,
    creep_base_small_hauler: role_local_hauler,
    creep_base_hauler: role_cleanup,
    creep_base_reserving: role_remote_mining_reserve,
    creep_base_defender: role_defender,
}

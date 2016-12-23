from constants import *
from roles import building, defensive, smart_offensive
from roles import colonizing
from roles import exploring
from roles import generic
from roles import minerals
from roles import mining
from roles import offensive
from roles import spawn_fill
from roles import tower_fill
from roles import upgrading
from roles import utility
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

role_classes = {
    role_upgrader: upgrading.Upgrader,
    role_spawn_fill: spawn_fill.SpawnFill,
    role_spawn_fill_backup: spawn_fill.SpawnFill,
    role_upgrade_fill: upgrading.DedicatedUpgradeFiller,
    role_link_manager: utility.LinkManager,
    role_builder: building.Builder,
    role_tower_fill: tower_fill.TowerFill,
    role_miner: mining.EnergyMiner,
    role_hauler: mining.EnergyHauler,
    role_remote_mining_reserve: mining.RemoteReserve,
    role_defender: defensive.RoleDefender,
    role_wall_defender: defensive.WallDefender,
    role_ranged_offense: smart_offensive.KitingOffense,
    role_cleanup: utility.Cleanup,
    role_temporary_replacing: generic.ReplacingExpendedCreep,
    role_colonist: colonizing.Colonist,
    role_simple_claim: colonizing.Claim,
    role_room_reserve: colonizing.ReserveNow,
    role_mineral_steal: colonizing.MineralSteal,
    role_recycling: generic.Recycling,
    role_mineral_miner: minerals.MineralMiner,
    role_mineral_hauler: minerals.MineralHauler,
    role_td_healer: offensive.TowerDrainHealer,
    role_td_goad: offensive.TowerDrainer,
    role_simple_dismantle: offensive.Dismantler,
    role_scout: exploring.Scout,
    role_power_attack: offensive.PowerAttack,
    role_power_cleanup: offensive.PowerCleanup,
    role_energy_grab: offensive.EnergyGrab,
}


def wrap_creep(hive, targets, home, creep):
    """
    Wraps a given creep with it's role wrapper.
    :param hive: The active hive mind
    :param targets: The active target mind
    :param home: The creep's home room
    :param creep: The creep to wrap
    :return: The role class, providing methods specific to the role, including run()
    :rtype: role_base.RoleBase
    """
    role = creep.memory.role
    if role in role_classes:
        return role_classes[role](hive, targets, home, creep)
    elif role in old_role_names:
        creep.memory.role = role = old_role_names[role]
        return role_classes[role](hive, targets, home, creep)
    else:
        return None

# wrap_creep = profiling.profiled(wrap_creep, "creep_wrappers.wrap_creep")

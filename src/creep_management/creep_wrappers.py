from constants import *
from creeps.roles import building, colonizing, defensive, exploring, generic, minerals, mining, offensive, sacrificial, \
    smart_offensive, spawn_fill, squads, support, tower_fill, upgrading, utility
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

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
    role_sacrifice: sacrificial.Sacrifice,
    role_sacrificial_cleanup: sacrificial.SacrificialCleanup,
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
    role_tower_fill_once: tower_fill.TowerFillOnce,
    role_squad_init: squads.SquadInit,
    role_squad_final_renew: squads.SquadFinalRenew,
    role_squad_final_boost: squads.SquadFinalBoost,
    role_squad_drone: squads.SquadDrone,
    role_squad_dismantle: squads.SquadDismantle,
    role_squad_heal: squads.SquadHeal,
    role_squad_ranged: squads.SquadRangedAttack,
    role_squad_all_attack: squads.SquadAllAttack,
    role_squad_kiting_attack: squads.SquadKitingRangedAttack,
    role_squad_kiting_heal: squads.SquadDirectSupportHeal,
    role_support_builder: support.SupportBuilder,
    role_support_miner: support.SupportMiner,
    role_support_hauler: support.SupportHauler,
    role_sign: exploring.Rndrs,
}


def wrap_creep(hive, targets, home, creep):
    """
    Wraps a given creep with it's role wrapper.
    :param hive: The active hive mind
    :param targets: The active target mind
    :param home: The creep's home room
    :param creep: The creep to wrap
    :return: The role class, providing methods specific to the role, including run()
    :rtype: creeps.base.RoleBase
    """
    role = creep.memory.role
    if role in role_classes:
        return role_classes[role](hive, targets, home, creep)
    elif role in old_role_names:
        creep.memory.role = role = old_role_names[role]
        return role_classes[role](hive, targets, home, creep)
    else:
        return None

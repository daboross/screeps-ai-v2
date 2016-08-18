import context
from constants import *
from roles import building
from roles import colonizing
from roles import dedi_miner
from roles import generic
from roles import military
from roles import minerals
from roles import remote_mining
from roles import spawn_fill
from roles import tower_fill
from roles import upgrading
from roles import utility
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

role_classes = {
    role_upgrader: upgrading.Upgrader,
    role_spawn_fill: spawn_fill.SpawnFill,
    role_spawn_fill_backup: spawn_fill.SpawnFill,
    role_link_manager: utility.LinkManager,
    role_dedi_miner: dedi_miner.DedicatedMiner,
    role_local_hauler: dedi_miner.LocalHauler,
    role_builder: building.Builder,
    role_tower_fill: tower_fill.TowerFill,
    role_remote_miner: remote_mining.RemoteMiner,
    role_remote_hauler: remote_mining.RemoteHauler,
    role_remote_mining_reserve: remote_mining.RemoteReserve,
    role_defender: military.RoleDefender,
    role_cleanup: utility.Cleanup,
    role_temporary_replacing: generic.ReplacingExpendedCreep,
    role_colonist: colonizing.Colonist,
    role_simple_claim: colonizing.Claim,
    role_room_reserve: colonizing.ReserveNow,
    role_recycling: generic.Recycling,
    role_mineral_miner: minerals.MineralMiner,
    role_mineral_hauler: minerals.MineralHauler,
    role_td_healer: military.TowerDrainHealer,
    role_td_goad: military.TowerDrainer,
    role_simple_dismantle: military.Dismantler,
}


def wrap_creep(creep):
    """
    Wraps a given creep with it's role wrapper.
    :param creep: The creep to wrap
    :return: The role class, providing methods specific to the role, including run()
    :rtype: role_base.RoleBase
    """
    role = creep.memory.role
    if role in role_classes:
        return role_classes[role](context.targets(), creep)
    else:
        return None


wrap_creep = profiling.profiled(wrap_creep, "creep_wrappers.wrap_creep")

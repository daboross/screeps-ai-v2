import constants
import context
import flags
import hivemind
import spawning
import speach
import tower
from constants import *
from hivemind import TargetMind, HiveMind
from role_base import RoleBase
from roles import building, remote_mining, dedi_miner, spawn_fill, tower_fill, upgrading, utility
from roles import military
from tools import profiling
from utils import consistency
from utils import movement
from utils.screeps_constants import *

__pragma__('noalias', 'name')

require("perf")()

role_classes = {
    role_upgrader: upgrading.Upgrader,
    role_spawn_fill: spawn_fill.SpawnFill,
    role_link_manager: utility.LinkManager,
    role_dedi_miner: dedi_miner.DedicatedMiner,
    role_local_hauler: dedi_miner.LocalHauler,
    role_builder: building.Builder,
    role_tower_fill: tower_fill.TowerFill,
    role_remote_miner: remote_mining.RemoteMiner,
    role_remote_hauler: remote_mining.RemoteHauler,
    role_remote_mining_reserve: remote_mining.RemoteReserve,
    role_defender: military.RoleDefender,
}


def main():
    if not Memory.meta:
        Memory.meta = {"pause": False, "quiet": False, "friends": []}
    if Memory.meta.pause:
        return

    PathFinder.use(True)

    target_mind = TargetMind()
    hive_mind = HiveMind(target_mind)
    context.set_targets(target_mind)
    context.set_hive(hive_mind)

    hive_mind.poll_all_creeps()
    hive_mind.poll_hostiles()

    if not Memory.creeps:
        Memory.creeps = {}
        for name in Object.keys(Game.creeps):
            Memory.creeps[name] = {}

    time = Game.time
    if not Memory.meta or Memory.meta.clear_now or \
            not Memory.meta.clear_next or time > Memory.meta.clear_next:
        print("Clearing memory")
        consistency.clear_memory(target_mind)
        for room in hive_mind.my_rooms:
            room.recalculate_roles_alive()
            consistency.reassign_room_roles(room)
            # Recalculate spawning - either because a creep death just triggered our clearing memory, or we haven't
            # recalculated in the last 500 ticks.
            # TODO: do we really need to recalculate every 500 ticks? even though it really isn't expensive
            room.reset_planned_role()
        Memory.meta.clear_now = False

    for room in hive_mind.my_rooms:
        context.set_room(room)
        for creep in room.creeps:
            try:
                if creep.spawning:
                    continue
                if not creep.memory.base:
                    creep.memory.base = spawning.find_base_type(creep)
                role = creep.memory.role
                if role in role_classes:
                    creep_instance = role_classes[role](target_mind, creep)
                else:
                    role = default_roles[creep.memory.base]
                    if not role:
                        base = RoleBase(target_mind, creep)
                        base.go_to_depot()
                        base.report(speach.base_no_role)
                        continue
                    room.add_to_role(role)
                    creep_instance = role_classes[role](target_mind, creep)
                rerun = creep_instance.run()
                if rerun:
                    rerun = creep_instance.run()
                if rerun:
                    rerun = creep_instance.run()
                if rerun:
                    print("[{}: {}] Tried to rerun three times!".format(creep.name, role))
            except Error as e:
                Game.notify("Error running role {}! Creep {} not run this tick.\n{}".format(
                    role if role else "<no role>", creep.name, e.stack
                ), 10)
                print("[{}] Error running role {}!".format(creep.name, role if role else "<no role>"))
                print(e.stack)

    for name in Object.keys(Game.spawns):
        spawn = Game.spawns[name]
        room = hive_mind.get_room(spawn.pos.roomName)
        spawning.run(room, spawn)

    tower.run()


module.exports.loop = profiling.wrap_main(main)

__pragma__('js', 'global').py = {
    "context": context,
    "consistency": consistency,
    "movement": movement,
    "hivemind": hivemind,
    "flags": flags,
    "constants": constants,
}

RoomPosition.prototype.createFlag2 = lambda pos: flags.create_flag(this, pos)

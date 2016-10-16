import speech
from constants import *
from control import pathdef
from goals.refill import Refill
from role_base import RoleBase
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

immediately_replace_roles = []
let_live_roles = [
    role_spawn_fill_backup,
    role_spawn_fill,
    role_upgrader,
    role_tower_fill,
    role_builder,
    role_cleanup,
    role_colonist,
    role_hauler,
    role_miner,  # We need this and mining reserve to let them use the cached paths.
    role_remote_mining_reserve,
    role_mineral_steal,
    role_mineral_hauler,
]


class ReplacingExpendedCreep(RoleBase):
    def run(self):
        old_name = self.memory.replacing
        if not old_name:
            self.creep.say("REPLACE?")  # TODO: temp message, move to speech.py
            self.go_to_depot()
            return

        role = self.memory.replacing_role

        old_creep = Game.creeps[old_name]

        if not old_creep or not Memory.creeps[old_name] or Memory.creeps[old_name].role == role_recycling \
                or let_live_roles.includes(role):
            # self.log("Now switching to role {}, to replace past-dead {}.".format(
            #     self.memory.replacing_role, self.memory.replacing
            # ))
            # He isn't alive anymore, we're too late.
            home = self.memory.home
            self.memory = Memory.creeps[self.name]
            Memory.creeps[self.name] = {"role": role, "home": home}
            self.home.register_to_role(self)
            return

        if immediately_replace_roles.includes(role) and not self.creep.spawning:
            Memory.creeps[old_creep.name] = {"role": role_recycling, "home": self.memory.home,
                                             "last_role": "replaced-{}".format(self.memory.role)}
            self.targets.untarget_all(old_creep)
            home = self.memory.home
            self.memory = Memory.creeps[self.name]
            Memory.creeps[self.name] = {"role": role, "home": home}
            self.home.register_to_role(self)
            self.home.mem.meta.clear_next = 0  # clear next tick
            return

        if old_creep.ticksToLive > 1:
            if self.creep.spawning:
                return
            if not self.creep.pos.isNearTo(old_creep):
                self.move_to(old_creep)
                return

        if self.pos.isNearTo(old_creep.pos) and not self.creep.spawning:
            self.creep.move(pathdef.direction_to(self.pos, old_creep.pos))
            old_creep.move(pathdef.direction_to(old_creep.pos, self.pos))
            mineral = _.findKey(old_creep.carry)
            if mineral:
                old_creep.transfer(self.creep, mineral)

        # self.log("Sending {} to recycling, and taking over as a {}.".format(
        #     old_name, self.memory.replacing_role,
        # ))
        Memory.creeps[self.name] = {}
        _.assign(Memory.creeps[self.name], Memory.creeps[old_name])
        # TODO: this works because memory isn't a property, but set during construction. However, memory should probably
        # be turned into a property in the future.
        self.targets.assume_identity(old_name, self.creep.name)  # needs to happen before switching memory.
        self.memory = Memory.creeps[self.name]
        del Memory.creeps[old_name]
        Memory.creeps[old_name] = {"role": role_recycling, "home": self.memory.home,
                                   "last_role": "replaced-{}".format(self.memory.role)}
        del self.memory.calculated_replacement_time
        del self.memory.replacement
        del self.memory._path
        del self.memory.last_checkpoint

        # TODO: Merge this code stolen from consistency back into it somehow?
        role = self.memory.role

        if role == role_remote_mining_reserve:
            room = self.memory.claiming
            if room:
                Memory.reserving[room] = self.name
        # TODO: instead of doing this, just somehow get hivemind to re-gen the replacement-time to include this creep

        self.home.mem.meta.clear_next = 0  # clear next tick

    def _calculate_time_to_replace(self):
        return 0


profiling.profile_whitelist(ReplacingExpendedCreep, ["run"])


class Recycling(Refill):
    def should_pickup(self, resource_type=None):
        return self.creep.ticksToLive > 100

    def run(self):
        # flag to other creeps
        self.memory.filling = False
        if _.sum(self.creep.carry) > 0:
            storage = self.home.room.storage
            if storage:
                if self.creep.pos.isNearTo(storage.pos):
                    for rtype in Object.keys(self.creep.carry):
                        if self.creep.carry[rtype] > 0:
                            result = self.creep.transfer(storage, rtype)
                            if result == OK:
                                break
                            else:
                                self.log("Unknown result from recycling-creep.transfer({}, {}): {}".format(
                                    storage, rtype, result))
                else:
                    self.move_to(storage)
                return False
            else:
                return self.refill_creeps()

        self.report(speech.recycling)
        self.recycle_me()

    def _calculate_time_to_replace(self):
        return 0

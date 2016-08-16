import speech
from constants import role_dedi_miner, target_big_source, role_remote_miner, target_remote_mine_miner, \
    role_remote_mining_reserve, target_remote_reserve, role_recycling
from role_base import RoleBase
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class ReplacingExpendedCreep(RoleBase):
    def run(self):
        old_name = self.memory.replacing
        if not old_name:
            self.creep.say("REPLACE?")  # TODO: temp message, move to speech.py
            self.go_to_depot()
            return

        old_creep = Game.creeps[old_name]

        if not old_creep or not Memory.creeps[old_name] or Memory.creeps[old_name].role == role_recycling:
            self.log("Now switching to role {}, to replace past-dead {}.".format(
                self.memory.replacing_role, self.memory.replacing
            ))
            # He isn't alive anymore, we're too late.
            role = self.memory.replacing_role
            base = self.memory.base
            home = self.memory.home
            self.memory = Memory.creeps[self.name]
            Memory.creeps[self.name] = {
                "role": role, "base": base, "home": home
            }
            self.home.register_to_role(self)
            return

        if old_creep.ticksToLive > 1:
            if self.creep.spawning:
                return
            if not self.creep.pos.isNearTo(old_creep):
                self.pick_up_available_energy()
                self.move_to(old_creep)
                return

        self.log("Sending {} to recycling, and taking over as a {}.".format(
            old_name, self.memory.replacing_role,
        ))
        Memory.creeps[self.name] = {}
        _.assign(Memory.creeps[self.name], Memory.creeps[old_name])
        # TODO: this works because memory isn't a property, but set during construction. However, memory should probably
        # be turned into a property in the future.
        self.target_mind.assume_identity(old_name, self.creep.name)  # needs to happen before switching memory.
        self.memory = Memory.creeps[self.name]
        del Memory.creeps[old_name]
        Memory.creeps[old_name] = {"role": role_recycling, "home": self.memory.home, "body": self.memory.body,
                                   "last_role": "replaced-{}".format(self.memory.role)}
        del self.memory.calculated_replacement_time
        del self.memory.replacement
        del self.memory.stationary
        del self.memory._path
        del self.memory.work
        del self.memory.carry
        self.memory.replaced = True

        # TODO: Merge this code stolen from consistency back into it somehow?
        role = self.memory.role

        if role == role_dedi_miner:
            source = self.target_mind.get_existing_target(self, target_big_source)
            if source:
                Memory.dedicated_miners_stationed[source.id] = self.creep.name
        elif role == role_remote_miner:
            flag = self.target_mind.get_existing_target(self, target_remote_mine_miner)
            if flag and flag.memory and flag.memory.remote_miner_targeting == old_name:
                flag.memory.remote_miner_targeting = self.creep.name
                flag.memory.remote_miner_death_tick = Game.time + self.creep.ticksToLive
        elif role == role_remote_mining_reserve:
            controller = self.target_mind.get_existing_target(self, target_remote_reserve)
            if controller and controller.room.memory.controller_remote_reserve_set == old_name:
                controller.room.memory.controller_remote_reserve_set = self.creep.name
        # TODO: instead of doing this, just somehow get hivemind to re-gen the replacement-time to include this creep

        self.home.mem.meta.clear_next = 0  # clear next tick


profiling.profile_whitelist(ReplacingExpendedCreep, ["run"])


class Recycling(RoleBase):
    def run(self):
        if _.sum(self.creep.carry, 'amount') > 0:
            storage = self.home.room.storage
            if storage:
                if self.creep.pos.isNearTo(storage.pos):
                    for rtype in Object.keys(self.creep.carry):
                        if self.creep.carry[rtype] > 0:
                            result = self.creep.transfer(storage, rtype)
                            if result == OK:
                                break
                            else:
                                self.log("Unknown result from creep.transfer({}, {}): {}".format(storage, rtype, result))
                else:
                    self.move_to(storage)
                return False

        self.report(speech.recycling)
        self.recycle_me()

import math

import context
from constants import role_dedi_miner, target_big_source, role_remote_miner, target_remote_mine_miner, \
    role_remote_mining_reserve, target_remote_reserve, role_builder, role_upgrader
from role_base import RoleBase
from utilities import movement
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

        if not old_creep or not Memory.creeps[old_name]:
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

        self.log("Commanding {} to suicide, and stealing their {} identity!".format(
            old_name, self.memory.replacing_role,
        ))
        old_time_to_live = old_creep.ticksToLive
        old_creep.suicide()
        Memory.creeps[self.name] = {}
        _.assign(Memory.creeps[self.name], Memory.creeps[old_name])
        # TODO: this works because memory isn't a property, but set during construction. However, memory should probably
        # be turned into a property in the future.
        self.memory = Memory.creeps[self.name]
        del Memory.creeps[old_name]
        # any role here, doesn't really matter. it's already committed suicide
        Memory.creeps[old_name] = {"role": "replaced", "home": self.memory.home}
        del self.memory.calculated_replacement_time
        del self.memory.replacement
        del self.memory.stationary
        del self.memory.path
        del self.memory.reset_path
        del self.memory.last_pos
        self.memory.replaced = True

        self.target_mind.assume_identity(old_name, self.creep.name)
        # TODO: Merge this code stolen from consistency back into it somehow?
        role = self.memory.role
        if role:
            print("[{}][{}] {} died (identity stolen by {}) (time to live: {})".format(
                self.home.room_name, old_name, role, self.name, old_time_to_live))

        if role == role_dedi_miner:
            source = self.target_mind.get_existing_target(self.creep, target_big_source)
            if source:
                Memory.dedicated_miners_stationed[source.id] = self.creep.name
        elif role == role_remote_miner:
            flag = self.target_mind.get_existing_target(self.creep, target_remote_mine_miner)
            if flag and flag.memory and flag.memory.remote_miner_targeting == old_name:
                flag.memory.remote_miner_targeting = self.creep.name
                flag.memory.remote_miner_death_tick = Game.time + self.creep.ticksToLive
        elif role == role_remote_mining_reserve:
            controller = self.target_mind.get_existing_target(self, target_remote_reserve)
            if controller and controller.room.memory.controller_remote_reserve_set == old_name:
                controller.room.memory.controller_remote_reserve_set = self.creep.name
        # TODO: instead of doing this, just somehow get hivemind to re-gen the replacement-time to include this creep
        Memory.meta.clear_now = True


class Colonist(RoleBase):
    def run(self):
        if not self.memory.colonizing:
            closest_distance = math.pow(2, 30)
            closest_room_name = None
            for room in context.hive().my_rooms:
                if not len(room.spawns) and _.sum(room.role_counts) < 3:
                    distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room.room_name)))
                    if distance < closest_distance:
                        closest_room_name = room.room_name

            # Colonize!
            self.memory.colonizing = closest_room_name

        colony = self.memory.colonizing

        if self.creep.room.name == colony:
            del self.memory.colonizing
            self.memory.home = colony
            room = context.hive().get_room(colony)
            if room.role_count(role_builder) < 2:
                self.memory.role = role_builder
            elif room.role_count(role_upgrader) < 1:
                self.memory.role = role_upgrader
            else:
                self.memory.role = role_builder
        else:
            self.move_to(__new__(RoomPosition(25, 25, colony)))

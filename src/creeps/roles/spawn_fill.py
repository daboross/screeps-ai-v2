from typing import List, Optional, TYPE_CHECKING, Union, cast

from cache import volatile_cache
from constants import SPAWN_FILL_WAIT, recycle_time, role_builder, role_recycling, role_spawn_fill, \
    role_spawn_fill_backup, role_tower_fill, role_upgrader, target_spawn_deposit
from creeps.base import RoleBase
from creeps.behaviors.refill import Refill
from creeps.roles import building, upgrading
from jstools.screeps import *
from position_management import flags
from utilities import movement

if TYPE_CHECKING:
    from empire.targets import TargetMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class SpawnFill(building.Builder, Refill):
    def run(self):
        if self.creep.ticksToLive < recycle_time and not self.home.under_siege():
            self.memory.role = role_recycling
            self.memory.last_role = role_spawn_fill
            return False
        if self.memory.filling and self.creep.carry[RESOURCE_ENERGY] >= self.creep.carryCapacity:
            self.memory.filling = False
            if self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill:
                self.targets.untarget_all(self)
            else:
                return True
        elif not self.memory.filling and (self.creep.carry[RESOURCE_ENERGY] <= 0 or
                                              (self.creep.carry[RESOURCE_ENERGY] <= 20
                                               and self.home.room.storage and movement.chebyshev_distance_room_pos(
                                                  self.pos, self.home.room.storage.pos) < 5)):
            self.memory.filling = True
            del self.memory.running
            if self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill:
                self.targets.untarget_all(self)
            else:
                return True

        if self.memory.filling:
            return self.harvest_energy()
        else:
            if 'running' in self.memory:
                if self.memory.running == role_upgrader:
                    return upgrading.Upgrader.run(self)
                elif self.memory.running == role_builder:
                    return building.Builder.run(self)
                elif self.memory.running == "refill":
                    return self.refill_creeps()
                elif self.memory.running != role_spawn_fill and self.memory.running != "spawn_wait":
                    self.log("WARNING: Unknown running value: {}", self.memory.running)
                    del self.memory.running
            elif self.home.room.energyCapacityAvailable < 550 and self.home.room.energyAvailable < 300 \
                    and self.home.next_role is None:
                if self.creep.hasActiveBodyparts(WORK):
                    self.memory.running = role_builder
                    return building.Builder.run(self)
                else:
                    self.memory.running = "refill"
                    return self.refill_creeps()
            target = cast(Union[StructureExtension, Flag, None],
                          self.targets.get_new_target(self, target_spawn_deposit))
            if target:
                if cast(Flag, target).color:  # it's a spawn fill wait flag
                    assert isinstance(target, Flag)
                    self.memory.running = "spawn_wait"
                    rwc_cache = volatile_cache.mem("sfrwc")
                    if not rwc_cache.has(self.pos.roomName):
                        rwc_cache.set(self.pos.roomName, not not _.find(
                            self.room.find(FIND_MY_STRUCTURES),
                            lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN)
                                      and s.energy < s.energyCapacity))
                    if rwc_cache.get(self.pos.roomName):
                        self.targets.untarget(self, target_spawn_deposit)
                        return True
                    if self.creep.carry[RESOURCE_ENERGY] < self.creep.carryCapacity:
                        self.memory.filling = True
                        return True
                    if not self.home.full_storage_use:
                        self.memory.running = "refill"
                        return self.refill_creeps()
                    if not self.pos.isEqualTo(target):
                        self.move_to(target)
                    return False
                else:
                    assert isinstance(target, StructureExtension)
                    if self.memory.running == "spawn_wait":
                        del self.memory.running
                    if target.energy >= target.energyCapacity:
                        self.targets.untarget(self, target_spawn_deposit)
                        return True
                    else:
                        if not self.pos.isNearTo(target):
                            self.move_to(target)
                            return False
                        del self.memory.nbm

                        result = self.creep.transfer(target, RESOURCE_ENERGY)

                        if result == OK:
                            if self.creep.carry[RESOURCE_ENERGY] > target.energyCapacity - target.energy:
                                volatile_cache.mem("extensions_filled").set(target.id, True)
                                if self.creep.carry[RESOURCE_ENERGY] + target.energy - target.energyCapacity > 0:
                                    self.targets.untarget(self, target_spawn_deposit)
                                    new_target = self.targets.get_new_target(self, target_spawn_deposit)
                                    if new_target and not self.pos.isNearTo(new_target):
                                        self.move_to(new_target)
                                else:
                                    self.harvest_energy()  # Get a head start on this too!
                        elif result == ERR_FULL:
                            self.targets.untarget(self, target_spawn_deposit)
                            return True
                        else:
                            self.log("Unknown result from spawn_fill-creep.transfer({}): {}", target, result)
                            self.targets.untarget(self, target_spawn_deposit)
                            return True
                        return False

            if self.home.full_storage_use and self.memory.role == role_spawn_fill_backup \
                    and self.home.carry_mass_of(role_tower_fill) + self.home.carry_mass_of(role_spawn_fill) \
                            >= self.home.get_target_total_spawn_fill_mass():
                self.memory.role = role_builder
                return building.Builder.run(self)
            elif self.memory.role == role_spawn_fill_backup:
                if _.find(self.room.building.get_construction_targets(), lambda s:
                        s.structureType == STRUCTURE_EXTENSION) or self.home.upgrading_deprioritized():
                    self.memory.running = role_builder
                    return building.Builder.run(self)
                else:
                    self.memory.running = role_upgrader
                    return upgrading.Upgrader.run(self)
            elif not self.home.full_storage_use or self.home.room.storage.storeCapacity <= 0:
                self.memory.running = "refill"
                return self.refill_creeps()
            elif self.creep.carry[RESOURCE_ENERGY] < self.creep.carryCapacity:
                self.memory.filling = True
                return self.harvest_energy()
        return False

    def should_pickup(self, resource_type=None):
        if 'running' in self.memory:
            if self.memory.running == role_upgrader:
                return upgrading.Upgrader.should_pickup(self, resource_type)
            elif self.memory.running == role_builder:
                return building.Builder.should_pickup(self, resource_type)
        return RoleBase.should_pickup(self, resource_type)


def find_new_target_extension(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    closest_distance = Infinity
    best_id = None
    stealing_from = None
    structures = cast(List[Union[StructureExtension, StructureSpawn]],
                      _.filter(creep.home.find(FIND_MY_STRUCTURES),
                               lambda s: ((s.structureType == STRUCTURE_EXTENSION
                                           or s.structureType == STRUCTURE_SPAWN)
                                          and s.energy < s.energyCapacity)))
    if len(structures):
        for structure in structures:
            structure_id = structure.id
            if volatile_cache.mem("extensions_filled").has(structure_id):
                continue
            current_carry = targets.workforce_of(target_spawn_deposit, structure_id)
            distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
            if distance < closest_distance:
                max_to_deposit = structure.energyCapacity / 50.0
                if not current_carry or current_carry < max_to_deposit:
                    closest_distance = distance
                    best_id = structure_id
                    stealing_from = None
                else:
                    targeting = targets.reverse_targets[target_spawn_deposit][structure_id]
                    if len(targeting):
                        for name in targeting:
                            if not Game.creeps[name] or movement.distance_squared_room_pos(
                                    Game.creeps[name].pos, structure.pos) > distance * 2.25:
                                # If we're at least 1.5x closer than them, let's steal their place.
                                # Note that 1.5^2 is 2.25, which is what we should be using since we're comparing
                                # squared distances. d1 > d2 * 1.5 is equivalent to d1^2 > d2^2 * 1.5^2 which is
                                # equivalent to d1^2 > d2^2 * 2.25
                                closest_distance = distance
                                best_id = structure_id
                                stealing_from = name
                                break
                    else:
                        closest_distance = distance
                        best_id = structure_id
                        stealing_from = None
        if stealing_from is not None:
            targets.unregister_name(stealing_from, target_spawn_deposit)
    elif creep.home.full_storage_use:
        flag_list = flags.find_flags(creep.home, SPAWN_FILL_WAIT)
        if len(flag_list):
            best_id = _(flag_list).map(lambda f: "flag-{}".format(f.name)) \
                .min(lambda fid: targets.reverse_targets[target_spawn_deposit][fid] or 0)
            if best_id is Infinity:
                best_id = None
    return best_id

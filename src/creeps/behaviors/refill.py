from typing import Any, Dict, List, TYPE_CHECKING, Union, cast

from cache import volatile_cache
from constants import creep_base_full_upgrader, rmem_key_planned_role_to_spawn, role_builder, role_hauler, \
    role_spawn_fill, role_upgrader, roleobj_key_base, roleobj_key_num_sections, roleobj_key_role, target_big_repair, \
    target_construction, target_refill, target_repair
from creep_management import spawning
from creeps.base import RoleBase
from jstools.screeps import *
from utilities import robjs

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind

__pragma__("noalias", "name")
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def generate_role_obj(room):
    # type: (RoomMind) -> Dict[str, Any]
    if room.role_count(role_upgrader) >= 6 and not room.get_target_builder_work_mass():
        role = role_upgrader
        base = creep_base_full_upgrader
        num_sections = spawning.max_sections_of(room, base)
    else:
        role = role_builder
        base = room.get_variable_base(role)
        num_sections = spawning.max_sections_of(room, base)
    role_obj = {
        roleobj_key_role: role,
        roleobj_key_base: base,
        roleobj_key_num_sections: num_sections,
    }
    spawning.validate_role(role_obj)
    return role_obj


class Refill(RoleBase):
    def refill_creeps(self):
        # type: () -> bool
        if not self.creep.carry[RESOURCE_ENERGY]:
            self.memory.filling = True
            return True
        target = cast(Union[Creep, Structure, None], self.targets.get_new_target(self, target_refill))
        if target:
            full = robjs.capacity(target) and robjs.energy(target) >= robjs.capacity(target)
            if full:
                self.targets.untarget(self, target_refill)
                target = self.targets.get_new_target(self, target_refill)
        if target:
            if not self.pos.isNearTo(target):
                self.move_to(target)
                if Game.cpu.bucket >= 4000:
                    other = _.find(self.home.find_in_range(FIND_MY_STRUCTURES, 1, self.pos),
                                   lambda c: (c.energyCapacity and c.energy < c.energyCapacity)
                                             or (c.storeCapacity and _.sum(c.store) < c.storeCapacity))
                    if not other:
                        other = _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                                       lambda c: c.name != self.name
                                                 and (c.memory.role == role_builder or c.memory.role == role_upgrader)
                                                 and _.sum(c.carry) < c.carryCapacity)
                    if other:
                        result = self.creep.transfer(cast(Structure, other), RESOURCE_ENERGY)
                        if result == ERR_NOT_ENOUGH_RESOURCES:
                            self.memory.filling = True
                            return True
                        elif result != OK:
                            self.log("Unknown result from passingby refill.transfer({}): {}", other, result)
                    return False

            latched = False
            target_creep = cast(Creep, target)
            if self.creep.hasActiveBodyparts(WORK) and target_creep.memory and not target_creep.filling:
                # Let's latch on and work on whatever they're working on
                role = target_creep.memory.role
                result = None
                latched_target = None
                if role == role_builder:
                    sc_last_action = target_creep.memory.la
                    if sc_last_action == "r":
                        latched_target = cast(Structure, self.targets.get_existing_target(target_creep, target_repair))
                        if latched_target:
                            result = self.creep.repair(latched_target)
                    elif sc_last_action == "c":
                        latched_target = cast(ConstructionSite,
                                              self.targets.get_existing_target(target_creep, target_construction))
                        if latched_target:
                            result = self.creep.build(latched_target)
                    elif sc_last_action == "b":
                        latched_target = cast(Structure,
                                              self.targets.get_existing_target(target_creep, target_big_repair))
                        if latched_target:
                            result = self.creep.repair(latched_target)
                elif role == role_upgrader:
                    latched_target = self.home.room.controller
                    result = self.creep.upgradeController(latched_target)
                if result is not None:
                    if result == OK:
                        latched = True
                    elif result == ERR_NOT_IN_RANGE:
                        self.basic_move_to(latched_target)

            if Game.cpu.bucket >= 8000 and target_creep.carry:
                min_cap = 0
                other = target_creep
                for obj in cast(List[Dict[str, Creep]], self.home.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)):
                    creep = obj[LOOK_CREEPS]
                    if (creep.memory.role == role_builder or creep.memory.role == role_upgrader) \
                            and creep.name != self.name:
                        empty_percent = (creep.carryCapacity - _.sum(creep.carry)) / creep.carryCapacity
                        if empty_percent > min_cap:
                            other = creep
                            min_cap = empty_percent
                for obj in cast(List[Dict[str, Structure]],
                                self.home.look_for_in_area_around(LOOK_STRUCTURES, self.pos, 1)):
                    structure = obj[LOOK_STRUCTURES]
                    if structure.structureType == STRUCTURE_EXTENSION or structure.structureType == STRUCTURE_SPAWN:
                        structure = cast(Union[StructureSpawn, StructureExtension], structure)
                        empty_percent = 0.1 * (structure.energyCapacity - structure.energy) / structure.energyCapacity
                        if empty_percent > 0.1 and empty_percent > min_cap:
                            other = structure
                            min_cap = empty_percent
                if other != target:
                    result = self.creep.transfer(other, RESOURCE_ENERGY)
                    if result != OK:
                        self.log("Unknown result from passingby refill.transfer({}): {}", other, result)
                    return False
            result = self.creep.transfer(target, RESOURCE_ENERGY)

            if result == OK:
                target_empty = robjs.capacity(target) - robjs.energy(target)
                if not latched and self.creep.carry[RESOURCE_ENERGY] > target_empty:
                    volatile_cache.mem("extensions_filled").set(target.id, True)
                    if self.creep.carry[RESOURCE_ENERGY] - target_empty > 0:
                        self.targets.untarget(self, target_refill)
                        new_target = self.targets.get_new_target(self, target_refill)
                        if new_target and not self.pos.isNearTo(new_target):
                            self.move_to(new_target)
            elif result == ERR_FULL:
                if not latched:
                    self.targets.untarget(self, target_refill)
                    return True
            else:
                self.log("Unknown result from refill.transfer({}): {}", target, result)
                self.targets.untarget(self, target_refill)
            return False
        else:
            self.go_to_depot()
            if not self.home.spawn:
                return False
            # haha, total hack...
            if not self.home.spawn.spawning and self.home.get_next_role() is None:
                self.home.mem[rmem_key_planned_role_to_spawn] = generate_role_obj(self.home)
            else:
                v = volatile_cache.volatile()
                if v.has("refills_idle"):
                    idle = v.get("refills_idle") + 1
                else:
                    idle = 1
                if idle >= 3:
                    role = self.home.get_next_role()
                    if not role or ((role[roleobj_key_role] == role_hauler or role[roleobj_key_role] == role_spawn_fill)
                                    and (self.home.get_target_builder_work_mass()
                                         or self.home.get_target_upgrader_work_mass())) or idle >= 7:
                        self.home.mem[rmem_key_planned_role_to_spawn] = generate_role_obj(self.home)
                        v.set("refills_idle", -Infinity)
                else:
                    v.set("refills_idle", idle)

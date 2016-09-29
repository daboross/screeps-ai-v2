import spawning
from constants import target_refill, role_builder, role_upgrader
from role_base import RoleBase
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__("noalias", "name")
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class Refill(RoleBase):
    def refill_creeps(self):
        target = self.targets.get_new_target(self, target_refill)
        if target:
            full = (target.energyCapacity and target.energy >= target.energyCapacity) \
                   or (target.storeCapacity and _.sum(target.store) >= target.storeCapacity) \
                   or (target.carryCapacity and _.sum(target.carry) >= target.carryCapacity)
            if full:
                self.targets.untarget(self, target_refill)
                target = self.targets.get_new_target(self, target_refill)
        if target:
            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                other = _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                               lambda c: c.name != self.name
                                         and (c.memory.role == role_builder or c.memory.role == role_upgrader)
                                         and _.sum(c.carry) < c.carryCapacity)
                if other:
                    result = self.creep.transfer(other, RESOURCE_ENERGY)
                    if result == ERR_NOT_ENOUGH_RESOURCES:
                        self.memory.filling = True
                        return True
                    elif result != OK:
                        self.log("Unknown result from passingby refill.transfer({}): {}", other, result)
                return False

            result = self.creep.transfer(target, RESOURCE_ENERGY)

            if result == OK:
                target_empty = (target.energyCapacity or target.storeCapacity or target.carryCapacity) \
                               - (target.energy or (target.store and target.store.energy)
                                  or (target.carry and target.carry.energy) or 0)
                if self.creep.carry.energy > target_empty:
                    volatile_cache.mem("extensions_filled").set(target.id, True)
                    if self.creep.carry.energy - target_empty > 0:
                        self.targets.untarget(self, target_refill)
                        new_target = self.targets.get_new_target(self, target_refill)
                        if new_target and not self.creep.pos.isNearTo(new_target.pos):
                            self.move_to(new_target)
            elif result == ERR_FULL:
                self.targets.untarget(self, target_refill)
                return True
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.filling = True
                return True
            else:
                self.log("Unknown result from refill.transfer({}): {}", target, result)
                self.targets.untarget(self, target_refill)
            return False
        else:
            self.go_to_depot()
            # haha, total hack...
            if not self.home.spawn.spawning and self.home.get_next_role() is None:
                role = role_builder
                base = self.home.get_variable_base(role)
                num_sections = spawning.max_sections_of(self.home, base)
                role_obj = {
                    'role': role,
                    'base': base,
                    'num_sections': num_sections,
                }
                spawning.validate_role(role_obj)
                self.home.mem.next_role = role_obj

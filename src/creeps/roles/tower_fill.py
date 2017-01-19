from constants import recycle_time, role_builder, role_recycling, role_spawn_fill, role_tower_fill, target_tower_fill
from creeps.base import RoleBase
from creeps.roles import spawn_fill
from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


class TowerFill(spawn_fill.SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_tower_fill
            return False
        if self.memory.filling:
            if self.creep.carry.energy >= self.creep.carryCapacity:
                self.memory.filling = False
                self.targets.untarget_all(self)
        else:
            if self.creep.carry.energy <= 0:
                self.memory.filling = True
                del self.memory.running
                self.targets.untarget_all(self)

        if self.memory.filling:
            return self.harvest_energy()
        else:
            if Game.time % 5 == 4:
                target = self.targets.get_new_target(self, target_tower_fill)
            else:
                target = self.targets.get_existing_target(self, target_tower_fill)
            if target:
                if not self.home.role_count(role_spawn_fill) and target.energy >= target.energyCapacity / 2:
                    return spawn_fill.SpawnFill.run(self)
                if not self.pos.isNearTo(target):
                    self.move_to(target)
                    return False
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_FULL:
                    self.targets.untarget(self, target_tower_fill)
                    return True
                elif result != OK:
                    self.log("Unknown result from tower_fill-creep.transfer({}): {}", target, result)
                    self.targets.untarget(self, target_tower_fill)

            return spawn_fill.SpawnFill.run(self)


class TowerFillOnce(RoleBase):
    def run(self):
        if self.memory.filling:
            if self.creep.carry.energy >= self.creep.carryCapacity:
                self.memory.filling = False
                self.targets.untarget_all(self)
        else:
            if self.creep.carry.energy <= 0:
                self.memory.filling = True
                del self.memory.running
                self.targets.untarget_all(self)

        if self.memory.filling:
            return self.harvest_energy()
        else:
            target = self.targets.get_new_target(self, target_tower_fill)
            if target:
                if not self.pos.isNearTo(target):
                    self.move_to(target)
                    return False
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_FULL:
                    self.targets.untarget(self, target_tower_fill)
                    return True
                elif result != OK:
                    self.log("Unknown result from tower_fill-creep.transfer({}): {}", target, result)
                    self.targets.untarget(self, target_tower_fill)
            else:
                self.memory.role = self.memory.old_role or role_builder
                del self.memory.old_role

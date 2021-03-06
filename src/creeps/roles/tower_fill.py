from typing import Optional, TYPE_CHECKING

from constants import recycle_time, role_builder, role_recycling, role_spawn_fill, role_tower_fill, target_tower_fill
from creeps.base import RoleBase
from creeps.roles import spawn_fill
from jstools.screeps import *

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


class TowerFill(spawn_fill.SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_tower_fill
            return False
        if self.memory.filling:
            if self.creep.carry[RESOURCE_ENERGY] >= self.creep.carryCapacity:
                self.memory.filling = False
                self.targets.untarget_all(self)
        else:
            if self.creep.carry[RESOURCE_ENERGY] <= 0:
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
            assert isinstance(target, StructureTower)
            if target:
                if not self.home.role_count(role_spawn_fill) and target.energy >= target.energyCapacity / 2:
                    return spawn_fill.SpawnFill.run(self)
                if not self.pos.isNearTo(target):
                    self.memory.running = "tf2"
                    self.move_to(target)
                    return False
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result == ERR_FULL:
                    self.targets.untarget(self, target_tower_fill)
                    del self.memory.running
                    return True
                elif result != OK:
                    self.log("Unknown result from tower_fill-creep.transfer({}): {}", target, result)
                    self.targets.untarget(self, target_tower_fill)
                    del self.memory.running
                return False

            return spawn_fill.SpawnFill.run(self)


class TowerFillOnce(RoleBase):
    def run(self):
        if self.memory.filling:
            if self.creep.carry[RESOURCE_ENERGY] >= self.creep.carryCapacity:
                self.memory.filling = False
                self.targets.untarget_all(self)
        else:
            if self.creep.carry[RESOURCE_ENERGY] <= 0:
                self.memory.filling = True
                del self.memory.running
                self.targets.untarget_all(self)

        if self.memory.filling:
            return self.harvest_energy()
        else:
            target = self.targets.get_new_target(self, target_tower_fill)
            assert isinstance(target, StructureTower)
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


def find_new_target_tower(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    most_lacking = 0
    best_id = None
    for tower in creep.room.defense.towers():
        if tower.energy >= tower.energyCapacity * 0.9:
            continue
        # 50 per carry part, but we don't know if it's full. this is a safe compromise
        carry_targeting = targets.workforce_of(target_tower_fill, tower.id) * 25
        tower_lacking = tower.energyCapacity - tower.energy - carry_targeting
        if tower_lacking > most_lacking:
            most_lacking = tower_lacking
            best_id = tower.id

    return best_id

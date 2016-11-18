import math

import random

import speech
from constants import target_repair, target_construction, target_big_repair, role_recycling, recycle_time, \
    role_builder, target_destruction_site, role_upgrader
from control import pathdef
from role_base import RoleBase
from roles import upgrading
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class Builder(upgrading.Upgrader):
    def any_building_targets(self):
        return not not (len(self.home.building.next_priority_big_repair_targets())
                        or len(self.home.building.next_priority_construction_targets()))

    def any_destruct_targets(self):
        if self.targets.get_existing_target(self, target_destruction_site):
            return True
        if self.targets.get_new_target(self, target_destruction_site):
            self.targets.untarget(self, target_destruction_site)
            return True
        return False

    def should_pickup(self, resource_type=None):
        return RoleBase.should_pickup(self, resource_type) and self.any_building_targets()

    def run(self):
        if self.creep.ticksToLive < recycle_time and self.home.spawn:
            self.memory.role = role_recycling
            self.memory.last_role = role_builder
            return False
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
            self.targets.untarget_all(self)
            if self.home.room.controller.ticksToDowngrade < 500 \
                    and not self.home.role_count(role_upgrader) \
                    and self.memory.role == role_builder:
                self.memory.role = role_upgrader
                self.home.register_to_role(self)  # TODO: "unregister_from_role" func
                return False
        elif not self.memory.filling and self.creep.carry.energy <= 0:
            # don't do this if we don't have targets
            self.targets.untarget_all(self)
            self.memory.filling = True

        if 'la' not in self.memory and not self.any_building_targets():
            destruct = self.targets.get_new_target(self, target_destruction_site)
            if destruct:
                if self.memory.filling:
                    return self.execute_destruction_target(destruct)
                else:
                    return self.empty_to_storage()
            elif self.home.get_target_upgrader_work_mass():
                self.log("No targets found, repurposing as upgrader.")
                self.memory.role = role_upgrader
                return False
            else:
                self.log("No targets found, recycling.")
                self.memory.role = role_recycling
                self.memory.last_role = role_upgrader
                return False

        if self.memory.filling:
            if self.creep.getActiveBodyparts(WORK) >= 4:
                destruct = self.targets.get_new_target(self, target_destruction_site)
            else:
                destruct = None
            if destruct:
                self.execute_destruction_target(destruct)
            elif self.home.building_paused():
                if self.creep.carry.energy > 0:
                    self.memory.filling = False
                    return True
                self.go_to_depot()
            else:
                # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
                # source faster!
                self.build_swamp_roads()
                return self.harvest_energy()
        else:
            sc_last_action = self.memory.la
            if sc_last_action == "r":
                target = self.targets.get_existing_target(self, target_repair)
                if target:
                    return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)
                else:
                    del self.memory.la
                    if Game.cpu.bucket >= 8000:
                        # We've ran out of enery an untargeted a wall! Let's refresh the repair targets to re-sort them.
                        self.home.building.refresh_repair_targets(True)
            elif sc_last_action == "m":
                target = self.targets.get_existing_target(self, target_repair)
                if target:
                    return self.execute_repair_target(target, 5000, target_repair)
                else:
                    del self.memory.la
            elif sc_last_action == "b":
                target = self.targets.get_existing_target(self, target_big_repair)
                if target:
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)
                else:
                    del self.memory.la
            elif sc_last_action == "c":
                target = self.targets.get_existing_target(self, target_construction)
                if target:
                    return self.execute_construction_target(target)
                else:
                    del self.memory.la
            else:
                target = self.targets.get_existing_target(self, target_repair)
                if target:
                    self.memory.la = "r"
                    return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)
                target = self.targets.get_existing_target(self, target_construction)
                if target:
                    self.memory.la = "c"
                    return self.execute_construction_target(target)
                target = self.targets.get_existing_target(self, target_big_repair)
                if target:
                    self.memory.la = "b"
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)

            if self.memory.building_walls_at:
                walls = self.room.look_at(LOOK_STRUCTURES, self.memory.building_walls_at & 0x3F,
                                          (self.memory.building_walls_at >> 6) & 0x3F)
                wall = _.find(walls, lambda s: s.structureType == STRUCTURE_WALL
                                               or s.structureType == STRUCTURE_RAMPART)
                del self.memory.building_walls_at
                if wall:
                    if Game.cpu.bucket >= 8000:
                        self.home.building.refresh_repair_targets()
                    self.targets._register_new_targeter(target_repair, self.name, wall.id)
                    self.memory.la = 'm'
                    return self.execute_repair_target(wall, 5000, target_repair)

            if not self.home.spawn and (not self.home.being_bootstrapped() or self.home.mem.prio_spawn):
                target = _.find(self.home.find(FIND_MY_CONSTRUCTION_SITES), {'structureType': STRUCTURE_SPAWN})
                if target:
                    self.targets._register_new_targeter(target_construction, self.name, target.id)
                    self.memory.la = 'c'
                    return self.execute_construction_target(target)

            target = self.get_new_construction_target(True)  # walls_only = True
            if target:
                self.memory.la = 'c'
                return self.execute_construction_target(target)

            target = self.get_new_repair_target(5000, target_repair)
            if target:
                self.memory.la = 'm'
                return self.execute_repair_target(target, 5000, target_repair)

            target = self.get_new_construction_target()
            if target:
                self.memory.la = 'c'
                return self.execute_construction_target(target)

            target = self.get_new_repair_target(self.home.min_sane_wall_hits, target_repair)
            if target:
                self.memory.la = 'r'
                return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)

            target = self.get_new_repair_target(self.home.max_sane_wall_hits, target_big_repair)
            if target:
                self.memory.la = 'b'
                return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)

            # Old code which was being possible inefficient when there were only high-hits targets left
            # Note that since this code was last active, TargetMind._find_new_big_repair_site has been updated
            # to return the structure with the least hits (previously it just returned the first structure found with
            # hits < max_hits). This update to TargetMind is what allowed the more simplified code above to work
            # effectively.
            # for max_hits in range(min(400000, self.home.min_sane_wall_hits), self.home.max_sane_wall_hits, 50000):
            #     target = self.get_new_repair_target(max_hits, target_big_repair)
            #     if target:
            #         self.memory.last_big_repair_max_hits = max_hits
            #         return self.execute_repair_target(target, max_hits, target_big_repair)
            # target = self.get_new_repair_target(self.home.max_sane_wall_hits, target_big_repair)
            # if target:
            #     self.memory.last_big_repair_max_hits = self.home.max_sane_wall_hits
            #     return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)
            if self.home.get_target_upgrader_work_mass():
                self.log("No targets found, repurposing as upgrader.")
                self.memory.role = role_upgrader
                return False
            else:
                self.log("No targets found, recycling.")
                self.memory.role = role_recycling
                self.memory.last_role = role_upgrader
                return False

    def get_new_repair_target(self, max_hits, ttype):
        target = self.targets.get_new_target(self, ttype, max_hits)
        if target and ((target.hits >= max_hits and (target.structureType == STRUCTURE_WALL
                                                     or target.structureType == STRUCTURE_RAMPART))
                       or target.hits >= target.maxHits):
            self.log("WARNING: TargetMind.get_new_target({}, {}, {}) returned {} ({} hits)"
                     .format(self, ttype, max_hits, target, target.hits))
            self.targets.untarget(self, ttype)
            return None
        return target

    def get_new_construction_target(self, walls_only=False):
        return self.targets.get_new_target(self, target_construction, walls_only)

    def execute_repair_target(self, target, max_hits, ttype):
        self.report(speech.building_repair_target, target.structureType)
        if target.hits >= target.hitsMax or (target.hits >= max_hits * 2 and
                                                 (target.structureType == STRUCTURE_WALL
                                                  or target.structureType == STRUCTURE_RAMPART)):
            self.log("Untargeting {}: hits: {}, hitsMax: {}, max_hits: {} type: {}", target, target.hits,
                     target.hitsMax, max_hits, ttype)
            if Game.cpu.bucket >= 8000:
                self.home.building.refresh_repair_targets()
            self.targets.untarget(self, ttype)
            if self.home.role_count(role_builder) > 10:
                nearby = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)
                self.refill_nearby(nearby)
            return False
        if not self.creep.pos.inRangeTo(target.pos, 3):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            return False

        result = self.creep.repair(target)
        if result == OK:
            self.move_around_when_ok(target)
        elif result == ERR_INVALID_TARGET:
            self.targets.untarget(self, ttype)
            self.home.building.refresh_repair_targets()
            return False
        else:
            self.log("Unknown result from creep.repair({}): {}", target, result)

        return False

    def execute_construction_target(self, target):
        if not target.structureType and target.color:
            # it's a flag! ConstructionMind should have made a new construction site when adding this to the list of
            # available targets.
            site = _.find(target.pos.lookFor(LOOK_CONSTRUCTION_SITES), 'my')
            if site:
                self.targets._register_new_targeter(target_construction, self.name, site.id)
                target = site
            else:
                self.log("WARNING: Couldn't find site for flag at {}! Refreshing building targets..."
                         .format(target.pos))
                self.home.building.refresh_building_targets()
                self.targets.untarget(self, target_construction)
                self.move_to(target)
                return False
        self.report(speech.building_build_target, target.structureType)
        if not self.creep.pos.inRangeTo(target.pos, 3):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            if self.home.role_count(role_builder) > 10:
                nearby = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)
                self.refill_nearby(nearby)
            return False

        result = self.creep.build(target)
        if result == OK:
            self.move_around_when_ok(target)
            if target.structureType == STRUCTURE_WALL or target.structureType == STRUCTURE_RAMPART:
                self.memory.building_walls_at = target.pos.x | (target.pos.y << 6)
        elif result == ERR_INVALID_TARGET:
            self.targets.untarget(self, target_construction)
        else:
            self.log("Unknown result from creep.build({}): {}", target, result)
            return False

        return False

    def execute_destruction_target(self, target):
        if not self.pos.isNearTo(target.pos):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            return False

        result = self.creep.dismantle(target)
        if result == OK:
            self.move_around(target)
            if target.hits < self.creep.getActiveBodyparts(WORK) * 50:  # we've fully destroyed it
                # check to see if we've opened up any new spots for construction sites with our destroyed structure.
                self.home.building.refresh_building_targets()
        else:
            self.log("Unknown result from creep.dismantle({}): {}", target, result)

    def refill_nearby(self, nearby):
        refill_target_obj = _(nearby).filter(lambda c: c.creep.name != self.name and
                                                       (c.creep.memory.role == role_builder
                                                        or c.creep.memory.running == role_builder)
                                                       and not c.creep.memory.filling) \
            .max(lambda c: c.creep.carryCapacity - c.creep.carry.energy)
        if refill_target_obj is not -Infinity:
            refill_target = refill_target_obj.creep
            target_empty = refill_target.carryCapacity - refill_target.carry.energy
            self_empty = self.creep.carryCapacity - self.creep.carry.energy
            if target_empty > self_empty:
                amount = math.floor(min((target_empty - self_empty), self.creep.carry.energy * 3 / 4) * 2 / 3)
                if amount > 0:
                    result = self.creep.transfer(refill_target, RESOURCE_ENERGY, amount)
                    if result == OK:
                        refill_target.memory.filling = False
                    else:
                        self.log("Unknown result from btb-transfer({}, {}, {}): {}", refill_target, RESOURCE_ENERGY,
                                 amount, result)

    def move_around_when_ok(self, target):
        nearby = None
        if self.home.role_count(role_builder) > 10:
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)
            self.refill_nearby(nearby)

        if self.creep._forced_move:
            return

        if nearby is None:
            nearby = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)

        other = _.find(nearby, lambda c: c.creep.name != self.name)
        if other:
            best = None
            available = None
            for x in range(max(1, self.pos.x - 1), min(49, self.pos.x + 2)):
                for y in range(max(1, self.pos.y - 1), min(49, self.pos.y + 2)):
                    if movement.is_block_clear(self.room, x, y):
                        if max(abs(x - target.pos.x), abs(y - target.pos.y)) <= 3:
                            if best is None or random.randint(0, 10) > 3:
                                best = (x, y)
                        elif available is None or random.randint(0, 10) > 3:
                            available = (x, y)
            if best is not None:
                self.creep.move(pathdef.get_direction(best[0] - self.pos.x, best[1] - self.pos.y))
            elif available is not None:
                self.creep.move(pathdef.get_direction(available[0] - self.pos.x, available[1] - self.pos.y))
            else:
                self.log("Couldn't find somewhere to move to!")


profiling.profile_whitelist(Builder, [
    "run",
    "build_swamp_roads",
    "any_destruct_targets",
    "any_building_targets",
    "get_new_repair_target",
    "get_new_construction_target",
    "execute_repair_target",
    "execute_construction_target",
    "move_around_when_ok",
    "refill_nearby",
])

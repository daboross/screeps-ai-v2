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
            del self.memory.la
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
            else:
                self.memory.role = role_upgrader
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
            elif sc_last_action == "c":
                target = self.targets.get_existing_target(self, target_construction)
                if target:
                    return self.execute_construction_target(target)
                else:
                    del self.memory.la
            elif sc_last_action == "b":
                target = self.targets.get_existing_target(self, target_big_repair)
                if target:
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)
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
                walls = self.room.find_at(FIND_STRUCTURES, self.memory.building_walls_at & 0x3F,
                                          (self.memory.building_walls_at >> 6) & 0x3F)
                wall = _.find(walls, lambda s: s.structureType == STRUCTURE_WALL
                                               or s.structureType == STRUCTURE_RAMPART)
                del self.memory.building_walls_at
                if wall:
                    self.targets._register_new_targeter(target_repair, self.name, wall.id)
                    return self.execute_repair_target(wall, self.home.min_sane_wall_hits, target_repair)

            target = self.get_new_repair_target(self.home.min_sane_wall_hits, target_repair)
            if target:
                return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)

            target = self.get_new_construction_target()
            if target:
                return self.execute_construction_target(target)

            target = self.get_new_repair_target(self.home.max_sane_wall_hits, target_big_repair)
            if target:
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
            self.log("No targets found, repurposing as upgrader.")
            self.memory.role = role_upgrader
            return False

    def get_new_repair_target(self, max_hits, ttype):
        target = self.targets.get_new_target(self, ttype, max_hits)
        if target and (target.hits >= max_hits or target.hits > target.maxHits):
            self.log("WARNING: TargetMind.get_new_target({}, {}, {}) returned {} ({} hits)"
                     .format(self, ttype, max_hits, target, target.hits))
            self.targets.untarget(self, ttype)
            return None
        return target

    def get_new_construction_target(self):
        return self.targets.get_new_target(self, target_construction)

    def execute_repair_target(self, target, max_hits, ttype):
        self.report(speech.building_repair_target, target.structureType)
        if target.hits >= target.hitsMax or target.hits >= max_hits * 2:
            self.log("Untargeting {}: hits: {}, hitsMax: {}, max_hits: {} type: {}", target, target.hits,
                     target.hitsMax,
                     max_hits, ttype)
            self.home.building.refresh_repair_targets()
            self.targets.untarget(self, ttype)
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
            # available targets. Let's ask for a new target, so as to allow it to update the targets list.
            # this seems like an OK way to do this!
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
            self.move_around_when_ok(target)
            if target.hits < self.creep.getActiveBodyparts(WORK) * 50:  # we've fully destroyed it
                # check to see if we've opened up any new spots for construction sites with our destroyed structure.
                self.home.building.refresh_building_targets()
        else:
            self.log("Unknown result from creep.dismantle({}): {}", target, result)

    def move_around_when_ok(self, target):
        if self.creep._forced_move:
            return
        nearby = self.room.find_in_range(FIND_MY_CREEPS, 1, self.pos)
        other = _.find(nearby, lambda c: c.name != self.name)
        if other:
            if not self.basic_move_to(target):
                found = False
                for x in range(min(1, self.pos.x - 1), max(49, self.pos.x + 2)):
                    for y in range(min(1, self.pos.y - 1), max(49, self.pos.y + 2)):
                        if movement.is_block_clear(self.room, x, y):
                            self.creep.move(pathdef.get_direction(x - self.pos.x, y - self.pos.y))
                            found = True
                            break
                    if found:
                        break
                if not found:
                    self.creep.move(pathdef.get_direction(other.pos.x - self.pos.x, other.pos.y - self.pos.y))
                    print("Couldn't find somewhere to move to! D:")


profiling.profile_whitelist(Builder, [
    "run",
    "build_swamp_roads",
    "any_destruct_targets",
    "any_building_targets",
    "get_new_repair_target",
    "get_new_construction_target",
    "execute_repair_target",
    "execute_construction_target",
])

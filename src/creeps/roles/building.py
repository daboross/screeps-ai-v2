import math
from typing import Dict, List, Optional, TYPE_CHECKING, Union, cast

from constants import recycle_time, rmem_key_building_priority_spawn, rmem_key_there_might_be_energy_lying_around, \
    role_builder, role_recycling, role_upgrader, target_big_big_repair, target_big_repair, target_construction, \
    target_destruction_site, target_repair
from creeps.base import RoleBase
from creeps.roles import upgrading
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

_max_builders_per_target = 4

_default_maximum_repair_workforce = 10


class Builder(upgrading.Upgrader):
    def any_building_targets(self):
        # type: () -> bool
        return not not (len(self.home.building.get_big_repair_targets())
                        or len(self.home.building.get_construction_targets()))

    def any_destruct_targets(self):
        # type: () -> bool
        if self.targets.get_existing_target(self, target_destruction_site):
            return True
        if self.targets.get_new_target(self, target_destruction_site):
            self.targets.untarget(self, target_destruction_site)
            return True
        return False

    def should_pickup(self, resource_type=None):
        # type: (Optional[str]) -> bool
        return RoleBase.should_pickup(self, resource_type) and self.any_building_targets()

    def run(self):
        if self.creep.ticksToLive < recycle_time and self.home.spawn:
            self.memory.role = role_recycling
            self.memory.last_role = role_builder
            return False
        if self.memory.filling and self.creep.carry[RESOURCE_ENERGY] >= self.creep.carryCapacity:
            self.memory.filling = False
            self.targets.untarget_all(self)
            if self.home.room.controller.ticksToDowngrade < 500 \
                    and not self.home.role_count(role_upgrader) \
                    and self.memory.role == role_builder:
                self.memory.role = role_upgrader
                self.home.register_to_role(self)  # TODO: "unregister_from_role" func
                return False
        elif not self.memory.filling and self.creep.carry[RESOURCE_ENERGY] <= 0:
            # don't do this if we don't have targets
            self.targets.untarget_all(self)
            self.memory.filling = True

        if Game.time % 5 == 0 and not (self.creep.hasActiveBodyparts(WORK) & self.creep.hasActiveBodyparts(CARRY)) and \
                not self.home.defense.healing_capable():
            if self.home.spawn:
                self.memory.last_role = self.memory.role
                self.memory.role = role_recycling
            else:
                self.creep.suicide()
                return

        if 'la' not in self.memory and not self.any_building_targets():
            destruct = cast(Optional[Structure], self.targets.get_new_target(self, target_destruction_site))
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
                destruct = cast(Optional[Structure], self.targets.get_new_target(self, target_destruction_site))
            else:
                destruct = None
            if destruct:
                self.execute_destruction_target(destruct)
            elif self.home.building_paused():
                if self.creep.carry[RESOURCE_ENERGY] > 0:
                    self.memory.filling = False
                    return True
                self.go_to_depot()
            else:
                # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
                # source faster!
                if self.home.mem[rmem_key_there_might_be_energy_lying_around]:
                    closest = self.pos.findClosestByRange(FIND_DROPPED_RESOURCES, {
                        'filter': lambda x: x.amount >= self.creep.carryCapacity
                    })
                    if closest:
                        if not self.pos.isNearTo(closest):
                            self.move_to(closest)
                            return
                    else:
                        del self.home.mem[rmem_key_there_might_be_energy_lying_around]
                self.build_swamp_roads()
                return self.harvest_energy()
        else:
            sc_last_action = self.memory.la
            if sc_last_action == "r":
                target = cast(Structure, self.targets.get_existing_target(self, target_repair))
                if target:
                    return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)
                else:
                    del self.memory.la
                    if Game.cpu.bucket >= 8000:
                        # We've ran out of energy an untargeted a wall!
                        # Let's refresh the repair targets to re-sort them.
                        self.home.building.refresh_repair_targets(True)
            elif sc_last_action == "m":
                target = cast(Structure, self.targets.get_existing_target(self, target_repair))
                if target:
                    return self.execute_repair_target(target, 5000, target_repair)
                else:
                    del self.memory.la
            elif sc_last_action == "b":
                target = cast(Structure, self.targets.get_existing_target(self, target_big_repair))
                if target:
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)
                else:
                    del self.memory.la
            elif sc_last_action == "e":
                target = cast(Structure, self.targets.get_existing_target(self, target_big_big_repair))
                if target:
                    return self.execute_repair_target(target, Infinity, target_big_big_repair)
                else:
                    del self.memory.la
            elif sc_last_action == "c":
                target = cast(Union[ConstructionSite, Flag],
                              self.targets.get_existing_target(self, target_construction))
                if target:
                    return self.execute_construction_target(target)
                else:
                    del self.memory.la
            elif sc_last_action == 'f':
                target = self.home.room.storage
                if target:
                    if self.pos.isNearTo(target):
                        resource = _.findKey(self.creep.carry)
                        self.creep.transfer(target, resource)
                    else:
                        self.move_to(target)
                else:
                    del self.memory.la
            else:
                target = self.targets.get_existing_target(self, target_repair)
                if target:
                    assert isinstance(target, Structure)
                    self.memory.la = "r"
                    return self.execute_repair_target(target, self.home.min_sane_wall_hits, target_repair)
                target = self.targets.get_existing_target(self, target_construction)
                if target:
                    assert isinstance(target, ConstructionSite) or isinstance(target, Flag)
                    self.memory.la = "c"
                    return self.execute_construction_target(target)
                target = self.targets.get_existing_target(self, target_big_repair)
                if target:
                    assert isinstance(target, Structure)
                    self.memory.la = "b"
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)
                target = self.targets.get_existing_target(self, target_big_big_repair)
                if target:
                    assert isinstance(target, Structure)
                    self.memory.la = "e"
                    return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_big_repair)

            if self.memory.building_walls_at:
                walls = self.room.look_at(LOOK_STRUCTURES, self.memory.building_walls_at & 0x3F,
                                          (self.memory.building_walls_at >> 6) & 0x3F)
                wall = _.find(walls, lambda s: s.structureType == STRUCTURE_WALL
                                               or s.structureType == STRUCTURE_RAMPART)
                assert isinstance(wall, (StructureWall, StructureRampart))
                del self.memory.building_walls_at
                if wall:
                    if Game.cpu.bucket >= 8000:
                        self.home.building.refresh_repair_targets()
                    self.targets.manually_register(self, target_repair, wall.id)
                    self.memory.la = 'm'
                    return self.execute_repair_target(wall, 5000, target_repair)

            if not self.home.spawn and (not self.home.being_bootstrapped()
                                        or self.home.mem[rmem_key_building_priority_spawn]):
                target = None
                if self.home.rcl >= 4:
                    if self.home.room.storage and self.home.mem[rmem_key_there_might_be_energy_lying_around]:
                        self.memory.la = 'f'
                    elif self.home.mem[rmem_key_there_might_be_energy_lying_around]:
                        target = _.find(self.home.find(FIND_MY_CONSTRUCTION_SITES),
                                        {'structureType': STRUCTURE_STORAGE})
                        if not target:
                            storage = flags.find_ms_flags(self.home, flags.MAIN_BUILD, flags.SUB_STORAGE)[0]
                            if storage and len(self.home.look_at(LOOK_RESOURCES, storage.pos)):
                                site = self.home.look_at(LOOK_CONSTRUCTION_SITES, storage.pos)[0]
                                if not site:
                                    storage.pos.createConstructionSite(STRUCTURE_STORAGE)
                                    return
                                else:
                                    target = site
                if not target:
                    target = _.find(self.home.find(FIND_MY_CONSTRUCTION_SITES), {'structureType': STRUCTURE_SPAWN})
                if target:
                    assert isinstance(target, ConstructionSite)
                    self.targets.manually_register(self, target_construction, target.id)
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

            target = self.get_new_repair_target(Infinity, target_big_big_repair)
            if target:
                self.memory.la = 'e'
                return self.execute_repair_target(target, Infinity, target_big_big_repair)
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
        # type: (int, int) -> Optional[Structure]
        target = self.targets.get_new_target(self, ttype, max_hits)

        assert isinstance(target, Structure)
        if target and ((target.hits >= max_hits and (target.structureType == STRUCTURE_WALL
                                                     or target.structureType == STRUCTURE_RAMPART))
                       or target.hits >= target.hitsMax):
            self.log("WARNING: TargetMind.get_new_target({}, {}, {}) returned {} ({} hits)"
                     .format(self, ttype, max_hits, target, target.hits))
            self.targets.untarget(self, ttype)
            return None
        return target

    def get_new_construction_target(self, walls_only=False):
        # type: (bool) -> Optional[ConstructionSite]
        return self.targets.get_new_target(self, target_construction, walls_only)

    def execute_repair_target(self, target, max_hits, ttype):
        # type: (Structure, int, int) -> bool
        if target.hits >= target.hitsMax or (target.hits >= max_hits * 2 and
                                                 (target.structureType == STRUCTURE_WALL
                                                  or target.structureType == STRUCTURE_RAMPART)):
            # self.log("Untargeting {}: hits: {}, hitsMax: {}, max_hits: {} type: {}", target, target.hits,
            #          target.hitsMax, max_hits, ttype)
            if Game.cpu.bucket >= 8000:
                self.home.building.refresh_repair_targets()
            self.targets.untarget(self, ttype)
            if self.home.role_count(role_builder) > 10:
                nearby = cast(List[Dict[str, Creep]], self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1))
                self.refill_nearby(nearby)
            return False
        if not self.pos.inRangeTo(target, 2):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            if not self.pos.inRangeTo(target, 3):
                return False

        result = self.creep.repair(target)
        if result == OK:
            pass
        elif result == ERR_INVALID_TARGET:
            self.targets.untarget(self, ttype)
            self.home.building.refresh_repair_targets()
            return False
        else:
            self.log("Unknown result from creep.repair({}): {}", target, result)

        return False

    def execute_construction_target(self, target):
        # type: (Union[Structure, Flag]) -> bool
        if not cast(Structure, target).structureType and cast(Flag, target).color:
            # it's a flag! ConstructionMind should have made a new construction site when adding this to the list of
            # available targets.
            site = cast(ConstructionSite, _.find(target.pos.lookFor(LOOK_CONSTRUCTION_SITES)))
            if site:
                if site.my:
                    self.targets.manually_register(self, target_construction, site.id)
                    target = site
                else:
                    site.remove()
                    self.move_to(site)
            else:
                creeps = cast(List[Creep], target.pos.lookFor(LOOK_CREEPS))
                if len(creeps):
                    if not _.find(creeps, lambda c: not c.my):
                        mine = _.find(creeps, 'my')
                        if not mine.__moved:
                            mine = self.hive.wrap_creep(mine)
                            if mine is not None:
                                mine.go_to_depot()
                else:
                    self.log("WARNING: Couldn't find site for flag at {}! Refreshing building targets..."
                             .format(target.pos))
                    self.home.building.refresh_building_targets()
                    self.targets.untarget(self, target_construction)
                    if not self.pos.inRangeTo(target, 2):
                        self.move_to(target)
                return False
        target = cast(ConstructionSite, target)
        if not self.pos.inRangeTo(target, 2):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            if not self.pos.inRangeTo(target, 3):
                if self.home.role_count(role_builder) > 10:
                    nearby = self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1)
                    self.refill_nearby(nearby)
                return False

        result = self.creep.build(target)
        if result == OK:
            if target.structureType == STRUCTURE_WALL or target.structureType == STRUCTURE_RAMPART:
                pos = target.pos or target
                self.memory.building_walls_at = pos.x | (pos.y << 6)
        elif result == ERR_INVALID_TARGET:
            self.targets.untarget(self, target_construction)
        else:
            self.log("Unknown result from creep.build({}): {}", target, result)
            return False

        return False

    def execute_destruction_target(self, target):
        # type: (Structure) -> bool
        if not self.pos.isNearTo(target):
            # If we're bootstrapping, build any roads set to be built in swamp, so that we can get to/from the
            # source faster!
            self.build_swamp_roads()
            self.move_to(target)
            return False

        result = self.creep.dismantle(target)
        if result == OK:
            self.move_around(target)
            if target.hits < self.creep.getActiveBodyparts(WORK) * DISMANTLE_POWER:  # we've fully destroyed it
                # check to see if we've opened up any new spots for construction sites with our destroyed structure.
                self.home.building.refresh_building_targets()
        else:
            self.log("Unknown result from creep.dismantle({}): {}", target, result)
        return False

    def refill_nearby(self, nearby):
        # type: (List[Dict[str, Creep]]) -> None
        refill_target_obj = _(nearby).filter(lambda c: c[LOOK_CREEPS].name != self.name and
                                                       (c[LOOK_CREEPS].memory.role == role_builder
                                                        or c[LOOK_CREEPS].memory.running == role_builder)
                                                       and not c[LOOK_CREEPS].memory.filling) \
            .max(lambda c: c[LOOK_CREEPS].carryCapacity - c[LOOK_CREEPS].carry[RESOURCE_ENERGY])
        if refill_target_obj is not -Infinity:
            refill_target = refill_target_obj.creep
            target_empty = refill_target.carryCapacity - refill_target.carry[RESOURCE_ENERGY]
            self_empty = self.creep.carryCapacity - self.creep.carry[RESOURCE_ENERGY]
            if target_empty > self_empty:
                amount = math.floor(
                    min((target_empty - self_empty), int(self.creep.carry[RESOURCE_ENERGY] * 3 / 4)) * 2 / 3)
                if amount > 0:
                    result = self.creep.transfer(refill_target, RESOURCE_ENERGY, int(amount))
                    if result == OK:
                        refill_target.memory.filling = False
                    else:
                        self.log("Unknown result from btb-transfer({}, {}, {}): {}", refill_target, RESOURCE_ENERGY,
                                 amount, result)


def find_new_target_construction_site(targets, creep, walls_only=False):
    # type: (TargetMind, RoleBase, Optional[bool]) -> Optional[str]
    smallest_work_force = Infinity
    best_id = None
    if walls_only:
        sites = creep.home.building.get_high_value_construction_targets()
    else:
        sites = creep.home.building.get_construction_targets()
    for site_id in sites:
        if site_id.startswith("flag-"):
            max_work = _max_builders_per_target
        else:
            site = cast(ConstructionSite, Game.getObjectById(site_id))
            if not site:
                continue
            max_work = min(_max_builders_per_target, math.ceil((site.progressTotal - site.progress) / 50))
        current_work = targets.workforce_of(target_construction, site_id)

        if not current_work or current_work < max_work:
            best_id = site_id
            break
        elif current_work < smallest_work_force:
            best_id = site_id
            smallest_work_force = current_work
    if not best_id and len(sites):
        creep.home.building.refresh_building_targets(True)
        # TODO: Infinite loop warning!!!
        return find_new_target_construction_site(targets, creep, walls_only)
    return best_id


def find_new_target_destruction_site(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    construct_count = {}
    for struct_id in creep.home.building.get_destruction_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct:
            current_num = targets.targets[target_destruction_site][struct_id]
            if not current_num or current_num < _max_builders_per_target:
                # List is already in priority.
                if struct.structureType not in construct_count:
                    construct_count[struct.structureType] = _.sum(creep.home.find(FIND_MY_CONSTRUCTION_SITES),
                                                                  lambda s: s.structureType == struct.structureType)
                if construct_count[struct.structureType] < 2:
                    return struct_id


def find_new_target_small_repair_site(targets, creep, max_hits, max_work=_default_maximum_repair_workforce):
    # type: (TargetMind, RoleBase, int, int) -> Optional[str]
    repair_targets = creep.home.building.get_repair_targets()
    if not len(repair_targets):
        return None
    # closest_distance = Infinity
    # smallest_num_builders = Infinity
    # best_id = None
    if len(repair_targets) <= 1 and not len(creep.home.building.get_construction_targets()):
        max_work = Infinity
    best_id = None
    second_best_id = None
    for struct_id in repair_targets:
        structure = cast(Structure, Game.getObjectById(struct_id))
        if not structure:
            continue
        # TODO: merge this logic with ConstructionMind _efficiently!_
        this_hits_max = min(structure.hitsMax, max_hits)
        if structure and structure.hits < this_hits_max * 0.9:
            distance = movement.chebyshev_distance_room_pos(structure.pos, creep.pos)
            ticks_to_repair = (structure.hitsMax - structure.hits) \
                              / (creep.creep.getActiveBodyparts(WORK) * REPAIR_POWER)
            if ticks_to_repair < 10 and distance < 3:
                return structure.id
            elif distance + ticks_to_repair < 15:
                best_id = structure.id
            if second_best_id:
                continue
            if max_work is Infinity:
                current_max = Infinity
            else:
                current_max = min(max_work, math.ceil((this_hits_max - structure.hits) / 50))
            current_workforce = targets.workforce_of(target_repair, struct_id)
            if not current_workforce or current_workforce < current_max:
                #     or current_workforce < smallest_num_builders + 1:
                # Already priority sorted
                second_best_id = structure.id
                # distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                # if distance < closest_distance:
                #     smallest_num_builders = current_workforce
                #     closest_distance = distance
                #     best_id = struct_id
    if best_id:
        return best_id
    else:
        return second_best_id


def find_new_target_big_repair_site(targets, creep, max_hits):
    # type: (TargetMind, RoleBase, int) -> Optional[str]
    # print("[targets][{}] Finding new big repair site in room {} with max_hits {} "
    #       .format(creep.name, creep.home.name, max_hits))
    best_id = None
    smallest_num = Infinity
    smallest_hits = Infinity
    for struct_id in creep.home.building.get_big_repair_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct and struct.hits < struct.hitsMax and struct.hits < max_hits:
            struct_num = targets.workforce_of(target_big_repair, struct_id)
            if struct_num < smallest_num or (struct_num == smallest_num and struct.hits < smallest_hits):
                smallest_num = struct_num
                smallest_hits = struct.hits
                best_id = struct_id
    return best_id


def find_new_target_extra_big_repair_site(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    # print("[targets][{}] Finding new big repair site in room {} with max_hits {} "
    #       .format(creep.name, creep.home.name, max_hits))
    best_id = None
    smallest_num = Infinity
    smallest_hits = Infinity
    for struct_id in creep.home.building.get_big_repair_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct and struct.hits < struct.hitsMax \
                and (struct.structureType == STRUCTURE_WALL or struct.structureType == STRUCTURE_RAMPART):
            struct_num = targets.workforce_of(target_big_big_repair, struct_id)
            if struct_num < smallest_num or (struct_num == smallest_num and struct.hits < smallest_hits):
                smallest_num = struct_num
                smallest_hits = struct.hits
                best_id = struct_id
    return best_id

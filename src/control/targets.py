import math

import flags
import spawning
from constants import *
from control import defense
from tools import profiling
from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_MAX_BUILDERS = 4
_MAX_REPAIR_WORKFORCE = 10


def _mass_count(name):
    # set in spawning and role base.
    if name in Memory.creeps and (Memory.creeps[name].carry or Memory.creeps[name].work):
        carry = Memory.creeps[name].carry or 0
        work = Memory.creeps[name].work or 0
    elif name in Game.creeps:
        creep = Game.creeps[name]
        carry = spawning.carry_count(creep)
        work = spawning.work_count(creep)
    else:
        return 1
    # TODO: do we, instead of doing this, want to count two different mass targeting variables in memory?
    return max(work, carry)


__pragma__('fcall')


class TargetMind:
    def __init__(self):
        if not Memory.targets:
            Memory.targets = {
                "targets_used": {},
                "targeters_using": {},
                "last_clear": Game.time,
            }
        self.mem = Memory.targets
        if not self.mem.targets_used:
            self.mem.targets_used = {}
        if not self.mem.targets_workforce:
            self.mem.targets_workforce = {}
        if not self.mem.targeters_using:
            self.mem.targeters_using = {}
        if not self.mem.targets_stealable:
            self.mem.targets_stealable = {}
        if (self.mem.last_clear or 0) + 1000 < Game.time:
            self._reregister_all()
            self.mem.last_clear = Game.time
        self.find_functions = {
            target_source: self._find_new_source,
            target_construction: self._find_new_construction_site,
            target_repair: self._find_new_repair_site,
            target_big_repair: self._find_new_big_repair_site,
            target_destruction_site: self._find_new_destruction_site,
            target_spawn_deposit: self._find_new_spawn_fill_site,
            target_tower_fill: self._find_new_tower,
            target_energy_miner_mine: self._find_new_energy_miner_mine,
            target_energy_hauler_mine: self._find_new_energy_hauler_mine,
            target_reserve_now: self._find_top_priority_reservable_room,
            target_closest_energy_site: self._find_closest_deposit_site,
            target_single_flag: self._find_closest_flag,
            target_single_flag2: self._find_closest_flag2,
            target_home_flag: self._find_closest_home_flag,
            target_refill: self._find_refill_target,
            target_rampart_defense: self._find_new_defendable_wall,
        }

    def __get_targets(self):
        return self.mem.targets_used

    def __set_targets(self, value):
        self.mem.targets_used = value

    def __get_targeters(self):
        return self.mem.targeters_using

    def __set_targeters(self, value):
        self.mem.targeters_using = value

    def __get_targets_workforce(self):
        return self.mem.targets_workforce

    def __set_targets_workforce(self, value):
        self.mem.targets_workforce = value

    def __get_reverse_targets(self):
        return self.mem.targets_stealable

    def __set_reverse_targets(self, value):
        self.mem.targets_stealable = value

    targets = property(__get_targets, __set_targets)
    targeters = property(__get_targeters, __set_targeters)
    targets_workforce = property(__get_targets_workforce, __set_targets_workforce)
    reverse_targets = property(__get_reverse_targets, __set_reverse_targets)

    def workforce_of(self, ttype, target):
        return (self.targets[ttype] and self.targets[ttype][target]
                and self.targets_workforce[ttype] and self.targets_workforce[ttype][target]) or 0

    def creeps_now_targeting(self, ttype, target_id):
        return (ttype in self.reverse_targets and self.reverse_targets[ttype][target_id]) or []

    def _register_new_targeter(self, ttype, targeter_id, target_id):
        if targeter_id not in self.targeters:
            self.targeters[targeter_id] = {
                ttype: target_id
            }
        elif ttype not in self.targeters[targeter_id]:
            self.targeters[targeter_id][ttype] = target_id
        else:
            old_target_id = self.targeters[targeter_id][ttype]
            self.targeters[targeter_id][ttype] = target_id
            if old_target_id == target_id:
                return  # everything beyond here would be redundant
            self.targets[ttype][old_target_id] -= 1
            if len(self.targets[ttype][old_target_id]) <= 0:
                del self.targets[ttype][old_target_id]

        if ttype not in self.targets:
            self.targets[ttype] = {
                target_id: 1,
            }
        elif not self.targets[ttype][target_id]:
            self.targets[ttype][target_id] = 1
        else:
            self.targets[ttype][target_id] += 1
        if ttype not in self.targets_workforce:
            self.targets_workforce[ttype] = {
                target_id: _mass_count(targeter_id)
            }
        elif target_id not in self.targets_workforce[ttype]:
            self.targets_workforce[ttype][target_id] = _mass_count(targeter_id)
        else:
            self.targets_workforce[ttype][target_id] += _mass_count(targeter_id)
        if ttype not in self.reverse_targets:
            self.reverse_targets[ttype] = {target_id: [targeter_id]}
        elif target_id not in self.reverse_targets[ttype]:
            self.reverse_targets[ttype][target_id] = [targeter_id]
        else:
            self.reverse_targets[ttype][target_id].push(targeter_id)

    def _reregister_all(self):
        new_targets = {}
        new_workforce = {}
        new_reverse = {}
        for targeter_id in Object.keys(self.targeters):
            mass = _mass_count(targeter_id)
            for ttype in Object.keys(self.targeters[targeter_id]):
                target_id = self.targeters[targeter_id][ttype]
                if ttype in new_targets:
                    if target_id in new_targets[ttype]:
                        new_targets[ttype][target_id] += 1
                    else:
                        new_targets[ttype][target_id] = 1
                else:
                    new_targets[ttype] = {target_id: 1}
                if ttype in new_workforce:
                    if target_id in new_workforce[ttype]:
                        new_workforce[ttype][target_id] += mass
                    else:
                        new_workforce[ttype][target_id] = mass
                else:
                    new_workforce[ttype] = {target_id: mass}
                # this target can be stolen, mark the targeter:
                if ttype in new_reverse:
                    if target_id in new_reverse[ttype]:
                        new_reverse[ttype][target_id].push(targeter_id)
                    else:
                        new_reverse[ttype][target_id] = [targeter_id]
                else:
                    new_reverse[ttype] = {target_id: [targeter_id]}

        self.targets = new_targets
        self.targets_workforce = new_workforce
        self.reverse_targets = new_reverse

    def _unregister_targeter(self, ttype, targeter_id):
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            if ttype in self.targets and existing_target in self.targets[ttype]:
                self.targets[ttype][existing_target] -= 1
            if ttype in self.targets_workforce and existing_target in self.targets_workforce[ttype]:
                self.targets_workforce[ttype][existing_target] -= _mass_count(targeter_id)
            if ttype in self.reverse_targets and existing_target in self.reverse_targets[ttype]:
                index = self.reverse_targets[ttype][existing_target].indexOf(targeter_id)
                if index > -1:
                    self.reverse_targets[ttype][existing_target].splice(index, 1)
            del self.targeters[targeter_id][ttype]

    def _unregister_all(self, targeter_id):
        if self.targeters[targeter_id]:
            mass = _mass_count(targeter_id)
            for ttype in Object.keys(self.targeters[targeter_id]):
                target = self.targeters[targeter_id][ttype]
                if ttype in self.targets and target in self.targets[ttype]:
                    self.targets[ttype][target] -= 1
                if ttype in self.targets_workforce and target in self.targets_workforce[ttype]:
                    self.targets_workforce[ttype][target] -= mass
                if ttype in self.reverse_targets and target in self.reverse_targets[ttype]:
                    index = self.reverse_targets[ttype][target].indexOf(targeter_id)
                    if index > -1:
                        self.reverse_targets[ttype][target].splice(index, 1)
        del self.targeters[targeter_id]

    def _move_targets(self, old_targeter_id, new_targeter_id):
        if self.targeters[old_targeter_id]:
            self.targeters[new_targeter_id] = self.targeters[old_targeter_id]
            old_mass = _mass_count(old_targeter_id)
            new_mass = _mass_count(new_targeter_id)
            for ttype in Object.keys(self.targeters[new_targeter_id]):
                target = self.targeters[new_targeter_id][ttype]
                if ttype in self.targets_workforce:
                    if target in self.targets_workforce:
                        self.targets_workforce[ttype][target] += new_mass - old_mass
                    else:
                        self.targets_workforce[ttype][target] = new_mass
                else:
                    self.targets_workforce[ttype] = {target: new_mass}
                if ttype in self.reverse_targets and target in self.reverse_targets[ttype]:
                    index = self.reverse_targets[ttype][target].indexOf(old_targeter_id)
                    if index > -1:
                        self.reverse_targets[ttype][target].splice(index, 1, new_targeter_id)
            del self.targeters[old_targeter_id]

    def _find_new_target(self, ttype, creep, extra_var):
        """
        :type ttype: str
        :type creep: role_base.RoleBase
        :type extra_var: ?
        """
        if ttype not in self.targets:
            self.targets[ttype] = {}
        if ttype not in self.targets_workforce:
            self.targets_workforce[ttype] = {}
        if ttype not in self.reverse_targets:
            self.reverse_targets[ttype] = {}
        func = self.find_functions[ttype]
        if func:
            return func(creep, extra_var)
        else:
            raise Error("Couldn't find find_function for '{}'!".format(ttype))

    def _get_existing_target_id(self, ttype, targeter_id):
        if targeter_id in self.targeters and ttype in self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        return None

    def _get_new_target_id(self, ttype, targeter_id, creep, extra_var):
        if targeter_id in self.targeters and ttype in self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        new_target = self._find_new_target(ttype, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(ttype, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, ttype, extra_var=None, second_time=False):
        target_id = self._get_new_target_id(ttype, creep.name, creep, extra_var)
        if not target_id:
            return None
        if target_id.startswith and target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, creep.name)
            if not second_time:
                return self.get_new_target(creep, ttype, extra_var, True)
        return target

    def get_existing_target(self, creep, ttype):
        target_id = self._get_existing_target_id(ttype, creep.name)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, creep.name)
        return target

    def untarget(self, creep, ttype):
        self._unregister_targeter(ttype, creep.name)

    def untarget_all(self, creep):
        self._unregister_all(creep.name)

    def assume_identity(self, old_name, new_name):
        self._move_targets(old_name, new_name)

    def _find_new_source(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        has_work = not not creep.creep.getActiveBodyparts(WORK)
        any_miners = not not creep.home.role_count(role_miner)
        highest_priority = -Infinity
        best_source = None
        for source in creep.home.find(FIND_SOURCES):
            if not has_work and not _.find(creep.home.find_in_range(FIND_MY_CREEPS, 1, source.pos),
                                           lambda c: c.memory.role == role_miner):
                continue
            distance = movement.distance_room_pos(source.pos, creep.pos)
            current_work_force = self.workforce_of(target_source, source.id)
            if any_miners:
                energy = _.sum(creep.home.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount')
                priority = energy - current_work_force * 100 - distance * 2
            else:
                oss = creep.home.get_open_source_spaces_around(source)
                priority = oss * 10 - 100 * current_work_force / oss - distance
            if source.energy <= 0:
                priority -= 200
            if priority > highest_priority:
                best_source = source.id
                highest_priority = priority

        return best_source

    def _find_new_spawn_fill_site(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        closest_distance = Infinity
        best_id = None
        stealing_from = None
        structures = _.filter(creep.home.find(FIND_MY_STRUCTURES),
                              lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN)
                                        and s.energy < s.energyCapacity)
        if len(structures):
            for structure in structures:
                structure_id = structure.id
                if volatile_cache.mem("extensions_filled").has(structure_id):
                    continue
                current_carry = self.workforce_of(target_spawn_deposit, structure_id)
                distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                if distance < closest_distance:
                    max = structure.energyCapacity / 50.0
                    if not current_carry or current_carry < max:
                        closest_distance = distance
                        best_id = structure_id
                        stealing_from = None
                    else:
                        targeting = self.reverse_targets[target_spawn_deposit][structure_id]
                        if len(targeting):
                            for name in targeting:
                                if not Game.creeps[name] or movement.distance_squared_room_pos(
                                        Game.creeps[name].pos, structure.pos) > distance * 2.25:
                                    # If we're at least 1.5x closer than them, let's steal their place.
                                    # Note that 1.5^2 is 2.25, which is what we should be using since we're comparing squared distances.
                                    # d1 > d2 * 1.5 is equivalent to d1^2 > d2^2 * 1.5^2 which is equivalent to d1^2 > d2^2 * 2.25
                                    closest_distance = distance
                                    best_id = structure_id
                                    stealing_from = name
                                    break
                        else:
                            closest_distance = distance
                            best_id = structure_id
                            stealing_from = None
            if stealing_from is not None:
                self._unregister_targeter(target_spawn_deposit, stealing_from)
        elif creep.home.full_storage_use:
            flag_list = flags.find_flags(creep.home, flags.SPAWN_FILL_WAIT)
            if len(flag_list):
                best_id = _(flag_list).map(lambda f: "flag-{}".format(f.name)) \
                    .min(lambda fid: self.reverse_targets[target_spawn_deposit][fid] or 0)
                if best_id is Infinity:
                    best_id = None
        return best_id

    def _find_new_construction_site(self, creep, walls_only=False):
        """
        :type creep: role_base.RoleBase
        """
        smallest_work_force = Infinity
        best_id = None
        if walls_only:
            sites = creep.home.building.next_priority_high_value_construction_targets()
        else:
            sites = creep.home.building.next_priority_construction_targets()
        for site_id in sites:
            if site_id.startsWith("flag-"):
                max_work = _MAX_BUILDERS
            else:
                site = Game.getObjectById(site_id)
                if not site:
                    continue
                max_work = min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 50))
            current_work = self.workforce_of(target_construction, site_id)

            if not current_work or current_work < max_work:
                best_id = site_id
                break
            elif current_work < smallest_work_force:
                best_id = site_id
                smallest_work_force = current_work
        if not best_id and len(sites):
            creep.home.building.refresh_building_targets(True)
            # TODO: Infinite loop warning!!!
            return self._find_new_construction_site(creep, walls_only)
        return best_id

    def _find_new_repair_site(self, creep, max_hits, max_work=_MAX_REPAIR_WORKFORCE):
        """
        :type creep: role_base.RoleBase
        """
        repair_targets = creep.home.building.next_priority_repair_targets()
        if not len(repair_targets):
            return None
        # closest_distance = Infinity
        # smallest_num_builders = Infinity
        # best_id = None
        if len(repair_targets) <= 1 and not len(creep.home.building.next_priority_construction_targets()):
            max_work = Infinity
        for struct_id in repair_targets:
            structure = Game.getObjectById(struct_id)
            if not structure:
                continue
            # TODO: merge this logic with ConstructionMind _efficiently!_
            this_hits_max = min(structure.hitsMax, max_hits)
            if structure and structure.hits < this_hits_max * 0.9:
                if max_work is Infinity:
                    current_max = Infinity
                else:
                    current_max = min(max_work, math.ceil((this_hits_max * 0.9 - structure.hits) / 50))
                current_workforce = self.workforce_of(target_repair, struct_id)
                if not current_workforce or current_workforce < current_max:
                    #     or current_workforce < smallest_num_builders + 1:
                    # Already priority sorted
                    return struct_id
                    # distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                    # if distance < closest_distance:
                    #     smallest_num_builders = current_workforce
                    #     closest_distance = distance
                    #     best_id = struct_id
        if max_work is _MAX_REPAIR_WORKFORCE and len(repair_targets):
            # TODO: do this through multiple best_id variables in the above loop, not like this.
            return self._find_new_repair_site(creep, max_hits, Infinity)
        return None

    def _find_new_big_repair_site(self, creep, max_hits):
        """
        :type creep: role_base.RoleBase
        """
        # print("[targets][{}] Finding new big repair site in room {} with max_hits {} "
        #       .format(creep.name, creep.home.room_name, max_hits))
        best_id = None
        smallest_num = Infinity
        smallest_hits = Infinity
        for struct_id in creep.home.building.next_priority_big_repair_targets():
            struct = Game.getObjectById(struct_id)
            if struct and struct.hits < struct.hitsMax and struct.hits < max_hits:
                struct_num = self.workforce_of(target_big_repair, struct_id)
                if struct_num < smallest_num or (struct_num == smallest_num and struct.hits < smallest_hits):
                    smallest_num = struct_num
                    smallest_hits = struct.hits
                    best_id = struct_id
        return best_id

    def _find_new_destruction_site(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        construct_count = {}
        for struct_id in creep.home.building.next_priority_destruct_targets():
            struct = Game.getObjectById(struct_id)
            if struct:
                current_num = self.targets[target_destruction_site][struct_id]
                if not current_num or current_num < _MAX_BUILDERS:
                    # List is already in priority.
                    if struct.structureType not in construct_count:
                        construct_count[struct.structureType] = _.sum(creep.home.find(FIND_MY_CONSTRUCTION_SITES),
                                                                      lambda s: s.structureType == struct.structureType)
                    if construct_count[struct.structureType] < 2:
                        return struct_id

    def _find_new_tower(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        most_lacking = 0
        best_id = None
        for tower in creep.room.defense.towers():
            if tower.energy >= tower.energyCapacity * 0.9:
                continue
            # 50 per carry part, but we don't know if it's full. this is a safe compromise
            carry_targeting = self.workforce_of(target_tower_fill, tower.id) * 25
            tower_lacking = tower.energyCapacity - tower.energy - carry_targeting
            if tower_lacking > most_lacking:
                most_lacking = tower_lacking
                best_id = tower.id

        return best_id

    def _find_new_energy_miner_mine(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        closest_flag = Infinity
        for flag in creep.home.mining.available_mines:
            flag_id = "flag-{}".format(flag.name)
            miners = self.targets[target_energy_miner_mine][flag_id]
            if not miners or miners < 1:
                distance = movement.distance_squared_room_pos(flag.pos, creep.creep.pos)
                if distance < closest_flag:
                    closest_flag = distance
                    best_id = flag_id

        return best_id

    def _find_new_energy_hauler_mine(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        # don't go to any rooms with 100% haulers in use.
        smallest_percentage = 1
        for flag in creep.home.mining.active_mines:
            flag_id = "flag-{}".format(flag.name)
            if not creep.home.mining.haulers_can_target_mine(flag):
                continue
            hauler_mass = self.workforce_of(target_energy_hauler_mine, flag_id)
            hauler_percentage = float(hauler_mass) / creep.home.mining.calculate_current_target_mass_for_mine(flag)
            too_long = creep.creep.ticksToLive < 2.2 * creep.home.mining.distance_to_mine(flag)
            if too_long:
                if hauler_percentage < 0.5:
                    hauler_percentage *= 2
                else:
                    hauler_percentage = 0.99
            if not hauler_mass or hauler_percentage < smallest_percentage:
                smallest_percentage = hauler_percentage
                best_id = flag_id

        return best_id

    def _find_closest_deposit_site(self, creep, pos):
        """
        :type creep: role_base.RoleBase
        """

        if not pos:
            pos = creep.pos
        if creep.home.full_storage_use:
            best = creep.home.room.storage
            # Still usually prefer storage over any links, unless a lot longer distance (>13 more away)
            best_priority = movement.chebyshev_distance_room_pos(pos, best.pos) - 13
            if creep.home.links.enabled:
                for struct in creep.home.links.links:
                    priority = movement.chebyshev_distance_room_pos(pos, struct.pos)
                    if priority < best_priority:
                        best = struct
                        best_priority = priority
            return best.id
        else:
            return None

    def _find_top_priority_reservable_room(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        closest_flag = None
        closest_distance = Infinity
        for flag in flags.find_flags_global(flags.RESERVE_NOW):
            room_name = flag.pos.roomName
            room = Game.rooms[room_name]
            if not room or (room.controller and not room.controller.my and not room.controller.owner):
                # claimable!
                flag_id = "flag-{}".format(flag.name)
                current_targets = self.targets[target_reserve_now][flag_id]
                if not current_targets or current_targets < 1:
                    distance = movement.distance_squared_room_pos(creep.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room_name)))

                    if distance < closest_distance:
                        closest_distance = distance
                        closest_flag = flag_id
        return closest_flag

    def _find_new_defendable_wall(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        hostiles = defense.stored_hostiles_near(creep.home.room_name)

        def priority(wall):
            current_priority = 0
            if len(hostiles):
                closest_distance = 5000
                for h in hostiles:
                    distance = movement.chebyshev_distance_room_pos(
                        movement.serialized_pos_to_pos_obj(h.room, h.pos), creep.pos)
                    if distance < closest_distance:
                        closest_distance = distance
            else:
                closest_distance = 5000
            current_priority -= closest_distance * 50  # Closer = better
            current_priority += max(abs(25 - wall.pos.x), abs(25 - wall.pos.y))  # Closer to edges = better
            current_priority -= movement.chebyshev_distance_room_pos(creep, wall) / 50  # Closer = better
            if closest_distance <= 1:
                current_priority += 15000
            elif closest_distance <= 3:
                current_priority += 12500
            elif _.find(wall.pos.lookFor(LOOK_FLAGS), {'color': COLOR_GREEN, "secondaryColor": COLOR_GREEN}):
                if closest_distance <= 5:
                    current_priority += 10000
                current_priority += 10000  # Green flag = better
            elif _.find(wall.pos.lookFor(LOOK_FLAGS), {'color': COLOR_GREEN, "secondaryColor": COLOR_RED}):
                if closest_distance <= 5:
                    current_priority += 10000
                current_priority += 5000  # Red flag = better

            return current_priority

        value = _(creep.home.find(FIND_MY_STRUCTURES).concat(creep.home.find(FIND_MY_CONSTRUCTION_SITES))) \
            .filter(lambda wall: wall.structureType == STRUCTURE_RAMPART
                                 and movement.is_block_empty(creep.home, wall.pos.x, wall.pos.y)
                                 and not self.targets[target_rampart_defense][wall.id]) \
            .max(priority)
        if value != -Infinity:
            return value.id
        return None

    def _find_closest_flag(self, creep, flag_type, pos):
        if not pos:
            pos = creep.pos
        elif pos.pos:
            pos = pos.pos
        closest_flag = None
        closest_distance = Infinity
        for flag in flags.find_flags_global(flag_type):
            flag_id = "flag-{}".format(flag.name)
            current = self.targets[target_single_flag][flag_id]
            if not current or current < 1:
                distance = movement.distance_squared_room_pos(pos, flag.pos)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_flag = flag_id
        return closest_flag

    def _find_closest_flag2(self, creep, flag_type, pos):
        if not pos:
            pos = creep.pos
        elif pos.pos:
            pos = pos.pos
        closest_flag = None
        closest_distance = Infinity
        for flag in flags.find_flags_global(flag_type):
            flag_id = "flag-{}".format(flag.name)
            current = self.targets[target_single_flag2][flag_id]
            if not current or current < 1:
                distance = movement.distance_squared_room_pos(pos, flag.pos)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_flag = flag_id
        return closest_flag

    def _find_closest_home_flag(self, creep, flag_type, pos):
        if not pos:
            pos = creep.pos
        elif pos.pos:
            pos = pos.pos
        closest_flag = None
        closest_distance = Infinity
        for flag in flags.find_flags(creep.home, flag_type):
            flag_id = "flag-{}".format(flag.name)
            current = self.targets[target_home_flag][flag_id]
            if not current or current < 1:
                distance = movement.distance_squared_room_pos(pos, flag.pos)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_flag = flag_id
        return closest_flag

    def _find_refill_target(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_priority = Infinity
        best_id = None
        stealing_from = None
        structures = _.filter(creep.home.find(FIND_MY_STRUCTURES),
                              lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN
                                         or s.structureType == STRUCTURE_CONTAINER
                                         or s.structureType == STRUCTURE_TOWER)
                                        and s.energy < s.energyCapacity)
        creeps = _.filter(creep.home.creeps,
                          lambda c: (c.memory.role == role_upgrader or c.memory.role == role_builder)
                                    and c.carry.energy < c.carryCapacity)
        extra = creep.home.get_extra_fill_targets()
        for structure in structures.concat(extra).concat(creeps):
            structure_id = structure.id
            if volatile_cache.mem("extensions_filled").has(structure_id):
                continue
            current_carry = self.workforce_of(target_spawn_deposit, structure_id) \
                            + self.workforce_of(target_refill, structure_id)
            empty = ((structure.energyCapacity or structure.carryCapacity or structure.storeCapacity)
                     - ((structure.store and _.sum(structure.store.energy))
                        or (structure.carry and _.sum(structure.carry.energy))
                        or structure.energy or 0))
            empty_percent = empty / (structure.energyCapacity or structure.carryCapacity or structure.storeCapacity) \
                            * 30
            if empty <= 0 or (empty <= 2 and not structure.structureType):
                continue
            distance = movement.chebyshev_distance_room_pos(structure.pos, creep.creep.pos)
            priority = distance - empty_percent
            if structure.memory and not structure.memory.filling:
                priority -= 15
            elif structure.structureType == STRUCTURE_CONTAINER:
                priority -= 40
            elif structure.structureType:
                priority -= 25
            if priority < best_priority:
                max_work_mass = empty / 50
                if not current_carry or current_carry < max_work_mass:
                    best_priority = priority
                    best_id = structure_id
                    stealing_from = None
                else:
                    targeting = self.reverse_targets[target_refill][structure_id]
                    if len(targeting):
                        for name in targeting:
                            if not Game.creeps[name] or movement.chebyshev_distance_room_pos(
                                    Game.creeps[name].pos, structure.pos) > distance * 1.5:
                                # If we're at least 1.5x closer than them, let's steal their place.
                                best_priority = priority
                                best_id = structure_id
                                stealing_from = name
                                break
        if stealing_from is not None:
            self._unregister_targeter(target_refill, stealing_from)

        return best_id


__pragma__('nofcall')

profiling.profile_whitelist(TargetMind, [
    "_find_new_target",
    "_find_new_source",
    "_find_new_big_h_source",
    "_find_new_harvester_deposit_site",
    "_find_new_repair_site",
    "_find_new_big_repair_site",
    "_find_new_spawn_fill_site",
    "_find_new_tower",
    "_find_new_remote_miner_mine",
    "_find_new_remote_hauler_mine",
    "_find_closest_deposit_site",
    "_find_new_reservable_controller",
])

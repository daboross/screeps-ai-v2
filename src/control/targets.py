import math

import context
import spawning
from constants import *
from control.hivemind import SLIGHTLY_SMALLER_THAN_MAX_INT
from control.hivemind import get_carry_mass_for_remote_mine
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MAX_BUILDERS = 3


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
        if (self.mem.last_clear or 0) + 1000 < Game.time:
            self._reregister_all()
            self.mem.last_clear = Game.time
        self.find_functions = {
            target_source: self._find_new_source,
            target_big_source: self._find_new_dedicated_miner_source,
            target_construction: self._find_new_construction_site,
            target_repair: self._find_new_repair_site,
            target_big_repair: self._find_new_big_repair_site,
            target_harvester_deposit: self._find_new_harvester_deposit_site,
            target_tower_fill: self._find_new_tower,
            target_remote_mine_miner: self._find_new_remote_miner_mine,
            target_remote_mine_hauler: self._find_new_remote_hauler_mine,
            target_remote_reserve: self._find_new_reservable_controller,
            target_closest_deposit_site: self._find_closest_deposit_site,
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

    targets = property(__get_targets, __set_targets)
    targeters = property(__get_targeters, __set_targeters)
    targets_workforce = property(__get_targets_workforce, __set_targets_workforce)

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

    def _reregister_all(self):
        new_targets = {}
        new_workforce = {}
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

        self.targets = new_targets
        self.targets_workforce = new_workforce

    def _unregister_targeter(self, ttype, targeter_id):
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            if ttype in self.targets and existing_target in self.targets[ttype]:
                self.targets[ttype][existing_target] -= 1
            if ttype in self.targets_workforce and existing_target in self.targets_workforce[ttype]:
                self.targets_workforce[ttype][existing_target] -= _mass_count(targeter_id)
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
            del self.targeters[old_targeter_id]

    def _find_new_target(self, ttype, creep, extra_var):
        """
        :type ttype: str
        :type creep: role_base.RoleBase
        :type extra_var: ?
        """
        if not self.targets[ttype]:
            self.targets[ttype] = {}
        if not self.targets_workforce[ttype]:
            self.targets_workforce[ttype] = {}
        func = self.find_functions[ttype]
        if func:
            return func(creep, extra_var)
        else:
            raise Error("Couldn't find find_function for '{}'!".format(ttype))

    def _get_existing_target_id(self, ttype, targeter_id):
        if self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        return None

    def _get_new_target_id(self, ttype, targeter_id, creep, extra_var):
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            return existing_target
        new_target = self._find_new_target(ttype, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(ttype, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, ttype, extra_var=None, second_time=False):
        target_id = self._get_new_target_id(ttype, creep.name, creep, extra_var)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, creep.name)
            if not second_time:
                return self.get_new_target(creep, ttype, extra_var, True)
        return target

    def _get_existing_target_from_name(self, name, ttype):
        """Exists to give an interface for when creeps die. TODO: make a full method."""
        target_id = self._get_existing_target_id(ttype, name)
        if not target_id:
            return None
        if target_id.startswith("flag-"):
            target = Game.flags[target_id[5:]]
        else:
            target = Game.getObjectById(target_id)
        if not target:
            self._unregister_targeter(ttype, name)
        return target

    def get_existing_target(self, creep, ttype):
        return self._get_existing_target_from_name(creep.name, ttype)

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
        biggest_energy_store = 0
        smallest_work_force = SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id_1 = None
        best_id_2 = None
        sources = creep.room.find(FIND_SOURCES)
        for source in sources:
            energy = _.sum(creep.room.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount') or 0
            # print("[{}] Energy at {}: {}".format(creep.room.name, source.id[-4:], energy))
            if source.id in self.targets_workforce[target_source]:
                current_work_force = self.targets_workforce[target_source][source.id]
            else:
                current_work_force = 0
            if current_work_force < smallest_work_force:
                smallest_work_force = current_work_force
            if energy > biggest_energy_store:
                biggest_energy_store = energy
        # print("[{}] Biggest energy store: {}".format(creep.room.name, biggest_energy_store))
        for source in sources:
            dedicated_miner_placed = not not (Memory.dedicated_miners_stationed and
                                              Memory.dedicated_miners_stationed[source.id])
            energy = _.sum(creep.room.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount') or 0
            if source.id in self.targets[target_source]:
                current_work_force = self.targets[target_source][source.id]
            else:
                current_work_force = 0
            if dedicated_miner_placed or has_work:
                if (current_work_force <= smallest_work_force) and energy + 100 > biggest_energy_store:
                    # print("[{}] Setting best_id_1: {}. {} + 100 > {}".format(
                    #     creep.room.name, source.id[-4:], energy, biggest_energy_store))
                    best_id_1 = source.id
                elif energy >= biggest_energy_store:
                    best_id_2 = source.id

        if best_id_1:
            return best_id_1
        if best_id_2:
            return best_id_2
        return None

    def _find_new_dedicated_miner_source(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        for source in creep.room.find(FIND_SOURCES):
            source_id = source.id
            current_harvesters = self.targets[target_big_source][source_id]
            if not current_harvesters or current_harvesters < 1:
                return source_id

        return None

    def _find_new_harvester_deposit_site(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        closest_distance = SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if (structure.structureType == STRUCTURE_EXTENSION or structure.structureType == STRUCTURE_SPAWN) \
                    and structure.energy < structure.energyCapacity and structure.my:
                source_id = structure.id
                current_carry = self.targets_workforce[target_harvester_deposit][source_id]
                # TODO: "1" should be a lot bigger if we have smaller creeps and no extensions.
                if not current_carry or current_carry < structure.energyCapacity / 50.0:
                    distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        best_id = source_id

        return best_id

    def _find_new_construction_site(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        needs_refresh = False
        for site_id in creep.home.building.next_priority_construction_targets():
            if site_id.startsWith("flag-"):
                max_work = _MAX_BUILDERS
            else:
                site = Game.getObjectById(site_id)
                if not site:
                    # we've built it
                    needs_refresh = True
                    continue
                max_work = min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 50))
            current_work = self.targets_workforce[target_construction][site_id]
            # TODO: this 200 should be a decided factor based off of spawn extensions
            if not current_work or current_work < max_work:
                best_id = site_id
                break
        if needs_refresh:
            context.room().building.refresh_targets()
        return best_id

    def _find_new_repair_site(self, creep, max_hits):
        """
        :type creep: role_base.RoleBase
        """
        # TODO: adjust to use workforce rather than counting creeps
        closest_distance = SLIGHTLY_SMALLER_THAN_MAX_INT
        smallest_num_builders = SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if (not structure.owner or structure.my) and structure.hits < structure.hitsMax * 0.9 \
                    and (structure.hits < max_hits or not max_hits):
                struct_id = structure.id
                current_num = self.targets[target_repair][struct_id]
                # TODO: this 200 should be a decided factor based off of spawn extensions
                if not current_num or current_num < \
                        min(_MAX_BUILDERS, math.ceil((min(max_hits, structure.hitsMax * 0.9) - structure.hits) / 200)) \
                        or current_num <= smallest_num_builders + 1:
                    distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                    if distance < closest_distance:
                        smallest_num_builders = current_num
                        closest_distance = distance
                        best_id = struct_id

        return best_id

    def _find_new_big_repair_site(self, creep, max_hits):
        """
        :type creep: role_base.RoleBase
        :type max_hits: int
        """
        closest_distance = SLIGHTLY_SMALLER_THAN_MAX_INT
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if (not structure.owner or structure.my) and structure.hits < structure.hitsMax * 0.9 \
                    and (structure.hits < max_hits or not max_hits):
                struct_id = structure.id
                current_num = self.targets[target_big_repair][struct_id]
                if not current_num or current_num < 1:
                    distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        best_id = struct_id

        return best_id

    def _find_new_tower(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        most_lacking = 0
        best_id = None
        for tower_id in Memory.tower.towers:
            tower = Game.getObjectById(tower_id)
            if tower.room != creep.creep.room:
                continue
            # 50 per carry part, but we don't know if it's full. this is a safe compromise
            carry_targeting = self.targets_workforce[target_tower_fill][tower_id] * 25
            if tower.energyCapacity - tower.energy - carry_targeting > most_lacking:
                most_lacking = tower.energyCapacity - tower.energy
                best_id = tower_id

        return best_id

    def _find_new_remote_miner_mine(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        closest_flag = SLIGHTLY_SMALLER_THAN_MAX_INT
        for flag in creep.home.remote_mining_operations:
            flag_id = "flag-{}".format(flag.name)
            miners = self.targets[target_remote_mine_miner][flag_id]
            if not miners or miners < 1:
                distance = movement.distance_squared_room_pos(flag.pos, creep.creep.pos)
                if distance < closest_flag:
                    closest_flag = distance
                    best_id = flag_id
                else:
                    print("[{}][{}] Flag is further than {} away... (range: {})".format(
                        creep.memory.home, creep.name, closest_flag, distance))
            else:
                print("[{}][{}] flag has {} miners already...".format(
                    creep.memory.home, creep.name, miners))

        return best_id

    def _find_new_remote_hauler_mine(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        # don't go to any rooms with 100% haulers in use.
        smallest_percentage = 1
        for flag in creep.home.remote_mining_operations:
            if not flag.memory.remote_miner_targeting and not (flag.memory.sitting > 500):
                continue  # only target mines with active miners
            flag_id = "flag-{}".format(flag.name)
            hauler_mass = self.targets_workforce[target_remote_mine_hauler][flag_id] or 0
            hauler_percentage = float(hauler_mass) / get_carry_mass_for_remote_mine(creep.home, flag)
            too_long = creep.creep.ticksToLive < 2.2 * creep.home.distance_storage_to_mine(flag)
            if too_long:
                if hauler_percentage < 0.5:
                    hauler_percentage *= 2
                else:
                    hauler_percentage = 0.99
            if not hauler_mass or hauler_percentage < smallest_percentage:
                smallest_percentage = hauler_percentage
                best_id = flag_id

        return best_id

    def _find_closest_deposit_site(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        # --Called once per creep in the entire lifetime-- < NOT TRUE, we are now resetting all targets multiple times
        # in a creep's lifetime.
        # target = creep.creep.pos.findClosestByPath(FIND_STRUCTURES, {
        # TODO: cache the closest deposit site to each mine site.
        target = creep.room.find_closest_by_range(FIND_STRUCTURES, creep.creep.pos,
                                                  lambda s: s.structureType == STRUCTURE_LINK
                                                            or s.structureType == STRUCTURE_STORAGE)
        if target:
            return target.id
        else:
            return None

    def _find_new_reservable_controller(self, creep):
        """
        :type creep: role_base.RoleBase
        """
        best_id = None
        closest_room = SLIGHTLY_SMALLER_THAN_MAX_INT
        # TODO: this really needs to be some kind of thing merged into RoomMind!
        max_reservable = 2 if Game.rooms[creep.memory.home].energyCapacityAvailable < 1300 else 1
        for flag in creep.home.remote_mining_operations:
            # TODO: should we only target already-mined rooms?
            if Game.rooms[flag.pos.roomName]:
                # must have a remote miner targeting, and be a room we have a view into.
                controller = Game.rooms[flag.pos.roomName].controller
                current_reservers = self.targets[target_remote_reserve][controller.id]
                if current_reservers >= max_reservable:  # TODO: should this be a constant, or is 2 a good small number?
                    continue  # max is 2
                if controller.my or (controller.reservation
                                     and controller.reservation.username != creep.creep.owner.username):
                    continue
                # Dispatch logic is to send 2 reservers to controllers with ticksToEnd < 4000, and 1 reserver to all
                # others.
                if not controller.reservation or controller.reservation.ticksToEnd < 4000 or current_reservers < 1:
                    # Ok, it's a controller we can reserve
                    controller_id = controller.id
                    distance = movement.distance_squared_room_pos(controller.pos, creep.creep.pos)
                    if not flag.memory.remote_miner_targeting:
                        distance += 10000  # Choose an already targeted mine if possible!
                    if distance < closest_room:
                        closest_room = distance
                        best_id = controller_id

        return best_id


profiling.profile_whitelist(TargetMind, [
    "_find_new_target",
    "_find_new_source",
    "_find_new_big_h_source",
    "_find_new_harvester_deposit_site",
    "_find_new_repair_site",
    "_find_new_big_repair_site",
    "_find_new_tower",
    "_find_new_remote_miner_mine",
    "_find_new_remote_hauler_mine",
    "_find_closest_deposit_site",
    "_find_new_reservable_controller",
])

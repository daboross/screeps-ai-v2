import math

import flags
from constants import target_source, recycle_time, role_recycling, target_closest_energy_site, role_miner, role_spawn_fill, role_tower_fill
from control import pathdef
from tools import profiling
from utilities import movement
from utilities import walkby_move
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_REUSE_PATH = 100
_WITH_ROAD_PF_OPTIONS = {
    "maxRooms": 10,
    "maxOps": 4000,
    "reusePath": _REUSE_PATH,
    "plainCost": 2,
    "swampCost": 10,
}
_NO_ROAD_PF_OPTIONS = {
    "maxRooms": 10,
    "maxOps": 4000,
    "reusePath": _REUSE_PATH,
    "plainCost": 1,
    "swampCost": 5,
}


class RoleBase:
    """
    :type targets: control.targets.TargetMind
    :type creep: Creep
    :type name: str
    :type hive: control.hivemind.HiveMind
    :type home: control.hivemind.RoomMind
    """

    def __init__(self, hive, targets, home, creep):
        self.hive = hive
        self.targets = targets
        self.home = home
        self.creep = creep
        if creep.memory:
            self.memory = creep.memory
        elif Memory.creeps[creep.name]:
            self.memory = Memory.creeps[creep.name]
        else:
            memory = {
                "targets": {},
                "path": {},
            }
            Memory.creeps[creep.name] = memory
            self.memory = memory
        self._room = None

    __pragma__('fcall')

    def get_name(self):
        return self.creep.name

    name = property(get_name)

    def get_pos(self):
        return self.creep.pos

    pos = property(get_pos)

    def get_room(self):
        """
        :rtype: control.hivemind.RoomMind
        """
        if not self._room:
            self._room = self.hive.get_room(self.creep.room.name)
            if not self._room:
                self.log("ERROR: can't find room we're in from hive! Room: {}".format(self.creep.room.name))
        return self._room

    room = property(get_room)

    def get_replacement_time(self):
        if "calculated_replacement_time" in self.memory:
            return self.memory.calculated_replacement_time
        else:
            store = True
            ticks_to_live = self.creep.ticksToLive
            if not ticks_to_live:
                if self.creep.spawning:
                    ticks_to_live = 1500
                    store = False
                else:
                    self.log("ticksToLive is not defined, while spawning is false!")
            ttr = self._calculate_time_to_replace()
            if ttr == -1:
                ttr = RoleBase._calculate_time_to_replace(self)
                store = False
            replacement_time = Game.time + ticks_to_live - ttr
            if store:
                self.memory.calculated_replacement_time = math.floor(replacement_time)
            return self.memory.calculated_replacement_time

    def _calculate_time_to_replace(self):
        return recycle_time + _.size(self.creep.body) * 3

    def run(self):
        """
        Runs this role's actions.
        :return: False if completed successfully, true if this method should be called a second time.
        :rtype Boolean:
        """
        pass

    def _move_options(self, target_room):
        roads = self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2
        if roads:
            options = _WITH_ROAD_PF_OPTIONS
        else:
            options = _NO_ROAD_PF_OPTIONS
        # Since this is overridden every _move_options call, we should be fine with modifying the constants.
        options['roomCallback'] = walkby_move.create_cost_callback(self, roads, target_room)
        return options

    __pragma__('nofcall')

    def _try_move_to(self, pos):
        here = self.creep.pos

        if here == pos:
            return OK
        elif here.isNearTo(pos):
            self.basic_move_to(pos)
            return OK
        move_opts = self._move_options(pos.roomName)
        result = self.creep.moveTo(pos, move_opts)
        if result == -2:
            self.basic_move_to(pos)
        return result

    def move_to(self, target):
        if self.creep.fatigue <= 0:
            if target.pos:
                target = target.pos
            result = self._try_move_to(target)

            if result == ERR_NO_BODYPART:
                # TODO: check for towers here, or use RoomMind to do that.
                self.log("Couldn't move, all move parts dead!")
                tower_here = False
                for struct in self.room.find(FIND_STRUCTURES):
                    if struct.structureType == STRUCTURE_TOWER:
                        tower_here = True
                        break
                if not tower_here:
                    self.creep.suicide()
                    self.home.mem.meta.clear_next = 0  # clear next tick
            elif result != OK:
                if result != ERR_NOT_FOUND and (result != ERR_NO_PATH or (self.pos.x != 49 and self.pos.y != 49
                                                                          and self.pos.x != 0 and self.pos.y != 0)):
                    self.log("WARNING: Unknown result from ({} at {}:{},{}).moveTo({}:{},{}): {}",
                             self.memory.role, self.pos.roomName, self.pos.x, self.pos.y,
                             target.roomName, target.x, target.y, result)

    def harvest_energy(self):
        if self.home.full_storage_use or (self.home.room.storage and not self.home.any_local_miners() and (self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill)):
            # Full storage use enabled! Just do that.
            storage = self.home.room.storage
            if self.carry_sum() == self.creep.carry.energy:  # don't do this if we have minerals
                target = self.targets.get_new_target(self, target_closest_energy_site)
                if not target:
                    target = storage
                elif target.energy <= 0 and not self.home.links.enabled:
                    target = storage
                # TODO: this is a special case mostly for W47N26
                elif target.pos.inRangeTo(self.home.room.controller, 4):
                    target = storage
                elif self.pos.getRangeTo(target) > self.pos.getRangeTo(storage):
                    target = storage
                if target.structureType == STRUCTURE_LINK:
                    self.home.links.register_target_withdraw(target, self,
                                                             self.creep.carryCapacity - self.creep.carry.energy,
                                                             self.creep.pos.getRangeTo(target))
            else:
                target = storage

            if not self.creep.pos.isNearTo(target.pos):
                # TODO: 5 should ideally be instead 1/4 of the distance to this creep's next target.
                if self.creep.carry.energy > 0.4 * self.creep.carryCapacity and \
                                self.creep.pos.getRangeTo(target.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    # TODO: some unified dual-interface for harvesting and jobs
                    self.memory.filling = False
                self.move_to(target)
                return False

            if self.carry_sum() > self.creep.carry.energy:
                resource = _.findKey(self.creep.carry)
                result = self.creep.transfer(target, resource)
            else:
                result = self.creep.withdraw(target, RESOURCE_ENERGY)

            if result == OK:
                pass
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                if target == storage:
                    self.log("Storage empty in {}!".format(target.pos.roomName))
                else:
                    # in case there are remote miners waiting to deposit here
                    self.move_around(target)
            else:
                self.log("Unknown result from creep.withdraw({}): {}", target, result)
            return False

        source = self.targets.get_new_target(self, target_source)
        if not source:
            if self.creep.hasActiveBodyparts(WORK):
                self.log("Wasn't able to find a source!")
                self.finished_energy_harvest()
            if self.creep.carry.energy > 10 and self.memory.filling:
                self.memory.filling = False
                return True
            self.go_to_depot()
            return False

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            return False

        piles = self.room.find_in_range(FIND_DROPPED_ENERGY, 3, source.pos)
        if len(piles) > 0:
            pile = _.max(piles, 'amount')
            if not self.creep.pos.isNearTo(pile):
                if self.creep.carry.energy > 0.4 * self.creep.carryCapacity \
                        and self.creep.pos.getRangeTo(pile.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                self.move_to(pile)
                return False
            result = self.creep.pickup(pile)
            if result == OK:
                self.creep.picked_up = True
                pile.picked_up = True
            else:
                self.log("Unknown result from creep.pickup({}): {}", pile, result)
            return False

        containers = _.filter(self.room.find_in_range(FIND_STRUCTURES, 3, source.pos),
                              {"structureType": STRUCTURE_CONTAINER})
        if len(containers) > 0:
            container = containers[0]
            if not self.creep.pos.isNearTo(container):
                if self.creep.carry.energy > 0.4 * self.creep.carryCapacity \
                        and self.creep.pos.getRangeTo(container.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                self.move_to(container)

            result = self.creep.withdraw(container, RESOURCE_ENERGY)
            if result != OK:
                self.log("Unknown result from creep.withdraw({}): {}", container, result)

            return False

        # TODO: this assumes that different sources are at least 3 away.
        miner = _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, source), lambda c: c.memory.role == role_miner)
        if miner:
            if not self.creep.pos.isNearTo(miner):
                if self.creep.carry.energy > 0.4 * self.creep.carryCapacity and \
                                self.creep.pos.getRangeTo(miner.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                if _.sum(self.room.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount') > 1500:
                    # Just get all you can - if this much has built up, it means something's blocking the queue...
                    self.move_to(miner)
                self.move_to(miner)
            return False  # waiting for the miner to gather energy.

        if _.find(self.room.find_in_range(FIND_MY_CREEPS, 2, self.creep.pos), lambda c: c.memory.role == role_miner):
            self.go_to_depot()
            return False
        if not self.creep.hasActiveBodyparts(WORK):
            self.go_to_depot()
            self.finished_energy_harvest()
            return False

        if source.energy <= 2 and Game.time % 10 == 5 and source.ticksToRegeneration >= 50:
            if _.find(self.home.sources, lambda s: s.energy > 0):
                self.targets.untarget(self, target_source)
            elif self.creep.carry.energy >= 100:
                self.memory.filling = False
        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source)
            return False

        result = self.creep.harvest(source)

        if result != OK and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from creep.harvest({}): {}", source, result)
        return False

    def finished_energy_harvest(self):
        self.targets.untarget(self, target_source)
        self.targets.untarget(self, target_closest_energy_site)

    def repair_nearby_roads(self):
        if not self.creep.hasActiveBodyparts(WORK):
            return False
        if self.creep.carry.energy <= 0:
            return False
        road = _.find(self.room.look_at(LOOK_STRUCTURES, self.creep.pos),
                      lambda s: s.structureType == STRUCTURE_ROAD)
        if road:
            if road.hits < road.hitsMax and road.hitsMax - road.hits \
                    >= REPAIR_POWER * self.creep.getActiveBodyparts(WORK):
                result = self.creep.repair(road)
                if result == OK:
                    return True
                else:
                    self.log("Unknown result from passingby-road-repair on {}: {}".format(road, result))
        else:
            build = self.room.look_at(LOOK_CONSTRUCTION_SITES, self.creep.pos)
            if len(build):
                build = _.find(build, lambda s: s.structureType == STRUCTURE_ROAD)
                if build:
                    result = self.creep.build(build)
                    if result == OK:
                        return True
                    else:
                        self.log("Unknown result from passingby-road-build on {}: {}".format(build, result))
        return False

    def find_depot(self):
        depots = flags.find_flags(self.home, flags.DEPOT)
        if len(depots):
            depot = depots[0].pos
        else:
            self.log("WARNING: No depots found in {}!".format(self.home.name))
            self.home.building.place_depot_flag()
            depots = flags.find_flags_global(flags.DEPOT)
            if len(depots):
                depot = depots[0].pos
            elif self.home.spawn:
                depot = self.home.spawn.pos
            else:
                depot = movement.find_an_open_space(self.home.name)
        return depot

    def go_to_depot(self):
        depot = self.find_depot()
        if not (self.pos.isEqualTo(depot) or (self.pos.isNearTo(depot)
                                              and not movement.is_block_clear(self.home, depot.x, depot.y))):
            self.move_to(depot)

    def _log_recycling(self):
        if self.creep.ticksToLive > 50:
            if self.memory.role == role_recycling:
                self.log("{} recycled (ttl: {}).", self.memory.last_role, self.creep.ticksToLive)
            else:
                self.log("{} committed suicide (ttl: {}).", self.memory.role, self.creep.ticksToLive)

    def recycle_me(self):
        spawn = self.home.spawns[0]
        if not spawn:
            if self.creep.ticksToLive > 50:
                self.go_to_depot()
            else:
                self._log_recycling()
                self.creep.suicide()
            return
        if not self.creep.pos.isNearTo(spawn.pos):
            if self.pos.getRangeTo(spawn) + 20 > self.creep.ticksToLive:
                self._log_recycling()
                self.creep.suicide()
            else:
                self.move_to(self.home.spawns[0])
        else:
            result = spawn.recycleCreep(self.creep)
            if result == OK:
                self._log_recycling()
                self.home.mem.meta.clear_next = 0  # clear next tick
            else:
                self.log("Unknown result from {}.recycleCreep({})! {}", spawn, self.creep, result)
                self.go_to_depot()

    def empty_to_storage(self):
        total = self.carry_sum()
        if total > 0:
            storage = self.home.room.storage
            if storage:
                if self.creep.pos.isNearTo(storage.pos):
                    for rtype in Object.keys(self.creep.carry):
                        if self.creep.carry[rtype] > 0:
                            result = self.creep.transfer(storage, rtype)
                            if result == OK:
                                return True
                            else:
                                self.log("Unknown result from creep.transfer({}, {}): {}"
                                         .format(storage, rtype, result))
                    else:
                        self.log("[empty_to_storage] Couldn't find resource to empty!")
                else:
                    self.move_to(storage)
                    return True
            else:
                self.log("Can't empty to storage: no storage!")
        return False

    # def _calculate_renew_cost_per_tick(self):
    #     creep_cost = _.sum()
    #
    # def renew_me(self):
    #     spawn = self.home.spawns[0]
    #     if self.home.room.energyAvailable < min(self.home.room.energyCapacityAvailable / 2.0, )

    def move_around(self, target):
        if Game.time % 7 < 4:
            self.move_around_clockwise(target)
        else:
            self.move_around_counter_clockwise(target)

    def move_around_clockwise(self, target):
        if self.creep.fatigue > 0:
            return
        direction = target.pos.getDirectionTo(self.creep.pos)
        if direction == TOP_LEFT or direction == TOP:
            self.creep.move(RIGHT)
        elif direction == TOP_RIGHT or direction == RIGHT:
            self.creep.move(BOTTOM)
        elif direction == BOTTOM_RIGHT or direction == BOTTOM:
            self.creep.move(LEFT)
        elif direction == BOTTOM_LEFT or direction == LEFT:
            self.creep.move(TOP)

    def move_around_counter_clockwise(self, target):
        if self.creep.fatigue > 0:
            return
        direction = target.pos.getDirectionTo(self.creep.pos)
        if direction == TOP_RIGHT or direction == TOP:
            self.creep.move(LEFT)
        elif direction == BOTTOM_RIGHT or direction == RIGHT:
            self.creep.move(TOP)
        elif direction == BOTTOM_LEFT or direction == BOTTOM:
            self.creep.move(RIGHT)
        elif direction == TOP_LEFT or direction == LEFT:
            self.creep.move(BOTTOM)

    def basic_move_to(self, target):
        if self.creep.fatigue > 0:
            return True
        if target.pos:
            target = target.pos
        if self.pos.isEqualTo(target):
            return False
        adx = target.x - self.pos.x
        ady = target.y - self.pos.y
        if target.roomName != self.pos.roomName:
            room1x, room1y = movement.parse_room_to_xy(self.pos.roomName)
            room2x, room2y = movement.parse_room_to_xy(target.roomName)
            adx += (room2x - room1x) * 50
            ady += (room2y - room1y) * 50
        dx = Math.sign(adx)
        dy = Math.sign(ady)
        if dx and dy:
            if movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y + dy):
                self.creep.move(pathdef.get_direction(dx, dy))
                return True
            elif adx == 1 and ady == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y):
                self.creep.move(pathdef.get_direction(dx, 0))
                return True
            elif movement.is_block_clear(self.room, self.pos.y + dy, self.pos.x):
                self.creep.move(pathdef.get_direction(0, dy))
                return True
        elif dx:
            if movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y):
                self.creep.move(pathdef.get_direction(dx, 0))
                return True
            elif adx == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y + 1):
                self.creep.move(pathdef.get_direction(dx, 1))
                return True
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y - 1):
                self.creep.move(pathdef.get_direction(dx, -1))
                return True
        elif dy:
            if movement.is_block_clear(self.room, self.pos.x, self.pos.y + dy):
                self.creep.move(pathdef.get_direction(0, dy))
                return True
            elif ady == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + 1, self.pos.y + dy):
                self.creep.move(pathdef.get_direction(1, dy))
                return True
            elif movement.is_block_clear(self.room, self.pos.x - 1, self.pos.y + dy):
                self.creep.move(pathdef.get_direction(-1, dy))
                return True
        return False

    __pragma__('fcall')

    def _try_force_move_to(self, x, y, creep_cond=lambda x: True):
        """
        Checks if a block is not a wall, has no non-walkable structures, and has no creeps.
        (copied from movement.py)
        """
        if x > 49 or y > 49 or x < 0 or y < 0:
            return False
        if Game.map.getTerrainAt(x, y, self.room.room.name) == 'wall':
            return False
        for struct in self.room.look_at(LOOK_STRUCTURES, x, y):
            if (struct.structureType != STRUCTURE_RAMPART or not struct.my) \
                    and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
                return False
        for struct in self.room.look_at(LOOK_CONSTRUCTION_SITES, x, y):
            if struct.my and struct.structureType != STRUCTURE_RAMPART \
                    and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
                return False
        creeps = self.room.look_at(LOOK_CREEPS, x, y)
        if len(creeps):
            other = creeps[0]
            if not other or not other.my:
                print("{} has length, but {}[0] == {}!".format(creeps, creeps, other))
                return False
            if not creep_cond(other):
                return False
            other.move(pathdef.get_direction(self.pos.x - x, self.pos.y - y))
            other._forced_move = True
        self.creep.move(pathdef.get_direction(x - self.pos.x, y - self.pos.y))
        return True

    __pragma__('nofcall')

    def force_basic_move_to(self, target, creep_cond=lambda x: True):
        """
        Tries to do a basic move in the direction, forcing place switching with an creep for which creep_cond(creep) returns True.
        :param target: The location (pos or object with pos property) to move to
        :param creep_cond: The condition with which this creep will take the place of another creep (default is "lambda x: True")
        :return: True if moved, False otherwise.
        """
        if self.creep.fatigue > 0:
            return True
        if target.pos:
            target = target.pos
        if self.pos.isNearTo(target):
            return True
        adx = target.x - self.pos.x
        ady = target.y - self.pos.y
        dx = Math.sign(adx)
        dy = Math.sign(ady)
        if dx and dy:
            if self._try_force_move_to(self.pos.x + dx, self.pos.y + dy, creep_cond):
                return True
            elif adx == 1 and ady == 1:
                return False
            elif self._try_force_move_to(self.pos.x + dx, self.pos.y, creep_cond):
                return True
            elif self._try_force_move_to(self.pos.x, self.pos.y + dy, creep_cond):
                return True
        elif dx:
            if self._try_force_move_to(self.pos.x + dx, self.pos.y, creep_cond):
                return True
            elif adx == 1:
                return False
            elif self._try_force_move_to(self.pos.x + dx, self.pos.y + 1, creep_cond):
                return True
            elif self._try_force_move_to(self.pos.x + dx, self.pos.y - 1, creep_cond):
                return True
        elif dy:
            if self._try_force_move_to(self.pos.x, self.pos.y + dy, creep_cond):
                return True
            elif ady == 1:
                return False
            elif self._try_force_move_to(self.pos.x + 1, self.pos.y + dy, creep_cond):
                return True
            elif self._try_force_move_to(self.pos.x - 1, self.pos.y + dy, creep_cond):
                return True
        return False

    def report(self, task_array, *args):
        if Game.cpu.bucket >= 6000 and (not Memory.meta.quiet or task_array[1]):
            time = Game.time
            if len(args):
                stuff = task_array[0][time % len(task_array[0])].format(*args)
            else:
                stuff = task_array[0][time % len(task_array[0])]
            if stuff:
                self.creep.say(stuff, True)

    def log(self, format_string, *args):
        """
        Logs a given string
        :type format_string: str
        :type args: list[object]
        """
        if len(args):
            print("[{}][{}] {}".format(self.home.name, self.name, format_string.format(*args)))
        else:
            print("[{}][{}] {}".format(self.home.name, self.name, format_string))

    __pragma__('fcall')

    def should_pickup(self, resource_type=None):
        return resource_type is None or resource_type == RESOURCE_ENERGY

    def carry_sum(self):
        if '_carry_sum' not in self.creep:
            self.creep._carry_sum = _.sum(self.creep.carry)
        return self.creep._carry_sum

    def toString(self):
        return "Creep[{}, role: {}, home: {}]".format(self.name, self.memory.role, self.home.name)

    __pragma__('nofcall')


profiling.profile_whitelist(RoleBase, [
    "_calculate_time_to_replace",
    "_follow_path_to",
    "move_to_with_queue",
    "_try_move_to",
    "move_to",
    "harvest_energy",
    "is_next_block_clear",
    "repair_nearby_roads",
])

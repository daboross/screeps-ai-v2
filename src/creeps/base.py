import math
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Union, cast

from constants import DEPOT, basic_reuse_path, recycle_time, role_miner, role_recycling, role_spawn_fill, \
    role_tower_fill, target_closest_energy_site, target_source
from creep_management import walkby_move
from jstools.screeps import *
from position_management import flags
from utilities import movement, robjs

if TYPE_CHECKING:
    from empire.hive import HiveMind
    from empire.targets import TargetMind
    from rooms.room_mind import RoomMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_WITH_ROAD_PF_OPTIONS = {
    "maxRooms": 10,
    "maxOps": 4000,
    "reusePath": basic_reuse_path,
    "plainCost": 2,
    "swampCost": 10,
}
_NO_ROAD_PF_OPTIONS = {
    "maxRooms": 10,
    "maxOps": 4000,
    "reusePath": basic_reuse_path,
    "plainCost": 1,
    "swampCost": 5,
}


class RoleBase:
    """
    :type targets: empire.targets.TargetMind
    :type creep: Creep
    :type name: str
    :type hive: empire.hive.HiveMind
    :type home: rooms.room_mind.RoomMind
    """

    def __init__(self, hive, targets, home, creep):
        # type: (HiveMind, TargetMind, RoomMind, Creep) -> None
        self.hive = hive
        self.targets = targets
        self.home = home
        self.creep = creep
        if creep.memory:
            self.memory = creep.memory  # type: _Memory
        elif Memory.creeps[creep.name]:
            self.memory = Memory.creeps[creep.name]  # type: _Memory
        else:
            memory = cast(_Memory, {
                "targets": {},
                "path": {},
            })
            Memory.creeps[creep.name] = memory
            self.memory = memory
        self._room = None

    __pragma__('fcall')

    def get_name(self):
        # type: () -> str
        return self.creep.name

    name = property(get_name)

    def get_pos(self):
        # type: () -> RoomPosition
        return self.creep.pos

    pos = property(get_pos)

    def get_room(self):
        # type: () -> RoomMind
        if not self._room:
            self._room = self.hive.get_room(self.creep.room.name)
            if not self._room:
                self.log("error! broken assumption. we're in room {}, but that room isn't found in hive.",
                         self.creep.room.name)
        return self._room

    room = property(get_room)

    def get_replacement_time(self):
        # type: () -> int
        if "calculated_replacement_time" in self.memory:
            return cast(int, self.memory.calculated_replacement_time)
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
                self.memory.calculated_replacement_time = int(math.floor(replacement_time))
            return self.memory.calculated_replacement_time

    def _calculate_time_to_replace(self):
        # type: () -> int
        return recycle_time + _.size(self.creep.body) * CREEP_SPAWN_TIME

    def run(self):
        # type: () -> Optional[bool]
        """
        Runs this role's actions.
        :return: False if completed successfully, true if this method should be called a second time.
        :rtype Boolean:
        """
        pass

    def _move_options(self, target_room, opts):
        # type: (str, Dict[str, Any]) -> Dict[str, Any]
        roads = self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2
        if roads:
            options = _WITH_ROAD_PF_OPTIONS
        else:
            options = _NO_ROAD_PF_OPTIONS
        callback = walkby_move.create_cost_callback(self, roads, target_room)
        if opts:
            if opts['costCallback']:
                room_callback = callback
                cost_callback = opts['costCallback']

                def callback(room_name):
                    matrix = room_callback(room_name)
                    if matrix:
                        result = cost_callback(room_name, matrix)
                        if result:
                            matrix = result
                    return matrix
            if opts['reusePath']:
                options = Object.create(options)
                options['reusePath'] = opts['reusePath']
        # Since this is overridden every _move_options call, we should be fine with modifying the constants.
        options['roomCallback'] = callback
        return options

    __pragma__('nofcall')

    def _try_move_to(self, pos, opts):
        # type: (RoomPosition, Dict[str, Any]) -> int
        here = self.creep.pos

        if here == pos:
            return OK
        elif here.isNearTo(pos):
            if not here.isEqualTo(pos):
                self.creep.move(movement.diff_as_direction(here, pos))
            return OK
        move_opts = self._move_options(pos.roomName, opts)
        result = self.creep.moveTo(pos, move_opts)
        if result == -2:
            self.basic_move_to(pos)
        return result

    def move_to(self, _target, opts = None):
        # type: (Union[RoomPosition, RoomObject, RoleBase], Dict[str, Any]) -> None
        if self.creep.fatigue <= 0:
            target = robjs.pos(_target)
            result = self._try_move_to(target, opts)

            if result == ERR_NO_BODYPART:
                self.log("Couldn't move, all move parts dead!")
                if not (self.room.my and self.room.defense.healing_capable()) and \
                        not _.some(self.room.find(FIND_MY_CREEPS), lambda c: c.hasActiveBodyparts(HEAL)):
                    self.creep.suicide()
                    self.home.check_all_creeps_next_tick()
            elif result != OK:
                if result != ERR_NOT_FOUND and (result != ERR_NO_PATH or (self.pos.x != 49 and self.pos.y != 49
                                                                          and self.pos.x != 0 and self.pos.y != 0)):
                    self.log("WARNING: Unknown result from ({} at {}:{},{}).moveTo({}:{},{} ({})): {}",
                             self.memory.role, self.pos.roomName, self.pos.x, self.pos.y,
                             target.roomName, target.x, target.y, target, result)

    def harvest_energy(self):
        # type: () -> bool
        if self.home.full_storage_use or (self.home.room.storage and not self.home.any_local_miners() and (
                        self.memory.role == role_spawn_fill or self.memory.role == role_tower_fill)):
            # Full storage use enabled! Just do that.
            storage = self.home.room.storage
            if self.carry_sum() == self.creep.carry[RESOURCE_ENERGY]:  # don't do this if we have minerals
                target = cast(Union[StructureStorage, StructureLink],
                              self.targets.get_new_target(self, target_closest_energy_site))
                if not target:
                    target = storage
                elif isinstance(target, StructureLink) and target.energy <= 0 and not self.home.links.enabled:
                    target = storage
                # TODO: this is a special case mostly for W47N26
                elif target.pos.inRangeTo(self.home.room.controller, 4):
                    target = storage
                elif self.pos.getRangeTo(target) > self.pos.getRangeTo(storage):
                    target = storage
                if target.structureType == STRUCTURE_LINK:
                    self.home.links.register_target_withdraw(target, self,
                                                             self.creep.carryCapacity
                                                             - self.creep.carry[RESOURCE_ENERGY],
                                                             self.pos.getRangeTo(target))
            else:
                target = storage

            if not self.pos.isNearTo(target):
                # TODO: 5 should ideally be instead 1/4 of the distance to this creep's next target.
                if self.creep.carry[RESOURCE_ENERGY] > 0.4 * self.creep.carryCapacity and \
                                self.pos.getRangeTo(target) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    # TODO: some unified dual-interface for harvesting and jobs
                    self.memory.filling = False
                self.move_to(target)
                return False

            if self.carry_sum() > self.creep.carry[RESOURCE_ENERGY]:
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

        source = cast(Source, self.targets.get_new_target(self, target_source))
        if not source:
            if self.creep.hasActiveBodyparts(WORK):
                self.log("Wasn't able to find a source!")
                self.finished_energy_harvest()
            if self.creep.carry[RESOURCE_ENERGY] > 10 and self.memory.filling:
                self.memory.filling = False
                return True
            self.go_to_depot()
            return False

        if self.pos.roomName != source.pos.roomName:
            self.move_to(source)
            return False

        piles = cast(List[Resource], self.room.find_in_range(FIND_DROPPED_RESOURCES, 3, source.pos))
        if len(piles) > 0:
            pile = _.max(piles, 'amount')
            if not self.creep.pos.isNearTo(pile):
                if self.creep.carry[RESOURCE_ENERGY] > 0.4 * self.creep.carryCapacity \
                        and self.pos.getRangeTo(pile) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                self.move_to(pile)
                return False
            result = self.creep.pickup(pile)
            if result == OK:
                self.creep.picked_up = pile
                pile.picked_up = self.creep
            else:
                self.log("Unknown result from creep.pickup({}): {}", pile, result)
            return False

        containers = cast(List[StructureContainer], _.filter(self.room.find_in_range(FIND_STRUCTURES, 3, source.pos),
                                                             {"structureType": STRUCTURE_CONTAINER}))
        if len(containers) > 0:
            container = containers[0]
            if not self.pos.isNearTo(container):
                if self.creep.carry[RESOURCE_ENERGY] > 0.4 * self.creep.carryCapacity \
                        and self.pos.getRangeTo(container) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                self.move_to(container)

            result = self.creep.withdraw(container, RESOURCE_ENERGY)
            if result != OK:
                self.log("Unknown result from creep.withdraw({}): {}", container, result)

            return False

        # TODO: this assumes that different sources are at least 3 away.
        miner = _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, source.pos), lambda c: c.memory.role == role_miner)
        if miner:
            if not self.pos.isNearTo(miner):
                if self.creep.carry[RESOURCE_ENERGY] > 0.4 * self.creep.carryCapacity and \
                                self.pos.getRangeTo(miner) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.filling = False
                if _.sum(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, source.pos), 'amount') > 1500:
                    # Just get all you can - if this much has built up, it means something's blocking the queue...
                    self.move_to(miner)
                self.move_to(miner)
            return False  # waiting for the miner to gather energy.

        if _.find(self.room.find_in_range(FIND_MY_CREEPS, 2, self.pos), lambda c: c.memory.role == role_miner):
            self.go_to_depot()
            return False
        if not self.creep.hasActiveBodyparts(WORK):
            self.go_to_depot()
            self.finished_energy_harvest()
            return False

        if source.energy <= 2 and Game.time % 10 == 5 and source.ticksToRegeneration >= 50:
            if _.find(self.home.sources, lambda s: s.energy > 0):
                self.targets.untarget(self, target_source)
            elif self.creep.carry[RESOURCE_ENERGY] >= 100:
                self.memory.filling = False
        if not self.pos.isNearTo(source):
            self.move_to(source)
            return False

        result = self.creep.harvest(source)

        if result != OK and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from creep.harvest({}): {}", source, result)
        return False

    def finished_energy_harvest(self):
        # type: () -> None
        self.targets.untarget(self, target_source)
        self.targets.untarget(self, target_closest_energy_site)

    def repair_nearby_roads(self):
        # type: () -> bool
        if not self.creep.hasActiveBodyparts(WORK):
            return False
        if self.creep.carry[RESOURCE_ENERGY] <= 0:
            return False
        road = cast(Optional[StructureRoad], _.find(self.room.look_at(LOOK_STRUCTURES, self.pos),
                                                    lambda s: s.structureType == STRUCTURE_ROAD))
        if road:
            if road.hits < road.hitsMax and road.hitsMax - road.hits \
                    >= REPAIR_POWER * self.creep.getActiveBodyparts(WORK):
                result = self.creep.repair(road)
                if result == OK:
                    return True
                else:
                    self.log("Unknown result from passingby-road-repair on {}: {}".format(road, result))
        else:
            build_list = cast(List[ConstructionSite], self.room.look_at(LOOK_CONSTRUCTION_SITES, self.pos))
            if len(build_list):
                build = _.find(build_list, lambda s: s.structureType == STRUCTURE_ROAD)
                if build:
                    result = self.creep.build(build)
                    if result == OK:
                        return True
                    else:
                        self.log("Unknown result from passingby-road-build on {}: {}".format(build, result))
        return False

    def find_depot(self):
        # type: () -> RoomPosition
        depots = flags.find_flags(self.home, DEPOT)
        if len(depots):
            depot = depots[0].pos
        else:
            self.log("WARNING: No depots found in {}!".format(self.home.name))
            self.home.building.place_depot_flag()
            depots = flags.find_flags_global(DEPOT)
            if len(depots):
                depot = _.min(depots, lambda d: movement.chebyshev_distance_room_pos(self.pos, d.pos)).pos
            elif self.home.spawn:
                depot = self.home.spawn.pos
            else:
                depot = movement.find_an_open_space(self.home.name)
        return depot

    def go_to_depot(self):
        # type: () -> None
        depot = self.find_depot()
        if not (self.pos.isEqualTo(depot) or (self.pos.isNearTo(depot)
                                              and not movement.is_block_clear(self.home, depot.x, depot.y))):
            self.move_to(depot)

    def _log_recycling(self):
        # type: () -> None
        if self.creep.ticksToLive > 50:
            if self.memory.role == role_recycling:
                self.log("{} recycled (ttl: {}).", self.memory.last_role, self.creep.ticksToLive)
            else:
                self.log("{} committed suicide (ttl: {}).", self.memory.role, self.creep.ticksToLive)

    def recycle_me(self):
        # type: () -> None
        spawn = self.home.spawns[0]
        if not spawn:
            if self.creep.ticksToLive > 50:
                self.go_to_depot()
            else:
                self._log_recycling()
                self.creep.suicide()
            return
        if not self.pos.isNearTo(spawn):
            if self.pos.getRangeTo(spawn) + 20 > self.creep.ticksToLive:
                self._log_recycling()
                self.creep.suicide()
            else:
                self.move_to(self.home.spawns[0])
        else:
            result = spawn.recycleCreep(self.creep)
            if result == OK:
                self._log_recycling()
                self.home.check_all_creeps_next_tick()
            else:
                self.log("Unknown result from {}.recycleCreep({})! {}", spawn, self.creep, result)
                self.go_to_depot()

    def empty_to_storage(self):
        # type: () -> bool
        total = self.carry_sum()
        if total > 0:
            storage = self.home.room.storage
            if storage:
                if self.pos.isNearTo(storage):
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
        # type: (RoomObject) -> None
        if Game.time % 7 < 4:
            self.move_around_clockwise(target)
        else:
            self.move_around_counter_clockwise(target)

    def move_around_clockwise(self, target):
        # type: (RoomObject) -> None
        if self.creep.fatigue > 0:
            return
        direction = target.pos.getDirectionTo(self.pos)
        if direction == TOP_LEFT or direction == TOP:
            self.creep.move(RIGHT)
        elif direction == TOP_RIGHT or direction == RIGHT:
            self.creep.move(BOTTOM)
        elif direction == BOTTOM_RIGHT or direction == BOTTOM:
            self.creep.move(LEFT)
        elif direction == BOTTOM_LEFT or direction == LEFT:
            self.creep.move(TOP)

    def move_around_counter_clockwise(self, target):
        # type: (RoomObject) -> None
        if self.creep.fatigue > 0:
            return
        direction = target.pos.getDirectionTo(self.pos)
        if direction == TOP_RIGHT or direction == TOP:
            self.creep.move(LEFT)
        elif direction == BOTTOM_RIGHT or direction == RIGHT:
            self.creep.move(TOP)
        elif direction == BOTTOM_LEFT or direction == BOTTOM:
            self.creep.move(RIGHT)
        elif direction == TOP_LEFT or direction == LEFT:
            self.creep.move(BOTTOM)

    def basic_move_to(self, target):
        # type: (Union[RoomPosition, RoomObject]) -> bool
        if self.creep.fatigue > 0:
            return True
        pos = robjs.pos(target)
        if self.pos.isEqualTo(target):
            return False
        adx = pos.x - self.pos.x
        ady = pos.y - self.pos.y
        if pos.roomName != self.pos.roomName:
            room1x, room1y = movement.parse_room_to_xy(self.pos.roomName)
            room2x, room2y = movement.parse_room_to_xy(pos.roomName)
            adx += (room2x - room1x) * 50
            ady += (room2y - room1y) * 50
        dx = Math.sign(adx)
        dy = Math.sign(ady)
        if dx and dy:
            if movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y + dy):
                self.creep.move(movement.dxdy_to_direction(dx, dy))
                return True
            elif adx == 1 and ady == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y):
                self.creep.move(movement.dxdy_to_direction(dx, 0))
                return True
            elif movement.is_block_clear(self.room, self.pos.y + dy, self.pos.x):
                self.creep.move(movement.dxdy_to_direction(0, dy))
                return True
        elif dx:
            if movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y):
                self.creep.move(movement.dxdy_to_direction(dx, 0))
                return True
            elif adx == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y + 1):
                self.creep.move(movement.dxdy_to_direction(dx, 1))
                return True
            elif movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y - 1):
                self.creep.move(movement.dxdy_to_direction(dx, -1))
                return True
        elif dy:
            if movement.is_block_clear(self.room, self.pos.x, self.pos.y + dy):
                self.creep.move(movement.dxdy_to_direction(0, dy))
                return True
            elif ady == 1:
                return False
            elif movement.is_block_clear(self.room, self.pos.x + 1, self.pos.y + dy):
                self.creep.move(movement.dxdy_to_direction(1, dy))
                return True
            elif movement.is_block_clear(self.room, self.pos.x - 1, self.pos.y + dy):
                self.creep.move(movement.dxdy_to_direction(-1, dy))
                return True
        if dx or dy:
            self.creep.move(movement.dxdy_to_direction(dx, dy))
        return False

    __pragma__('fcall')

    def _try_force_move_to(self, x, y, creep_cond = lambda x: True):
        # type: (int, int, Callable[[Creep], bool]) -> bool
        """
        Checks if a block is not a wall, has no non-walkable structures, and has no creeps.
        (copied from movement.py)
        """
        if x > 49 or y > 49 or x < 0 or y < 0:
            return False
        if Game.map.getTerrainAt(x, y, self.room.room.name) == 'wall':
            return False
        for struct in cast(List[Structure], self.room.look_at(LOOK_STRUCTURES, x, y)):
            if (struct.structureType != STRUCTURE_RAMPART or not cast(StructureRampart, struct).my) \
                    and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
                return False
        for struct in cast(List[ConstructionSite], self.room.look_at(LOOK_CONSTRUCTION_SITES, x, y)):
            if struct.my and struct.structureType != STRUCTURE_RAMPART \
                    and struct.structureType != STRUCTURE_CONTAINER and struct.structureType != STRUCTURE_ROAD:
                return False
        creeps = cast(List[Creep], self.room.look_at(LOOK_CREEPS, x, y))
        if len(creeps):
            other = creeps[0]
            if not other or not other.my:
                self.log("error! broken assumption. _try_force_move_to called towards {}, which is not owned."
                         .format(other))
                return False
            if not creep_cond(other):
                return False
            other.move(movement.dxdy_to_direction(self.pos.x - x, self.pos.y - y))
            # other._forced_move = True  - never used
        self.creep.move(movement.dxdy_to_direction(x - self.pos.x, y - self.pos.y))
        return True

    __pragma__('nofcall')

    def force_basic_move_to(self, target, creep_cond = lambda x: True):
        # type: (Union[RoomObject, RoomPosition], Callable[[Creep], bool]) -> bool
        """
        Tries to do a basic move in the direction, forcing place switching with an creep for which creep_cond(creep) returns True.
        :param target: The location (pos or object with pos property) to move to
        :param creep_cond: The condition with which this creep will take the place of another creep (default is "lambda x: True")
        :return: True if moved, False otherwise.
        """
        if self.creep.fatigue > 0:
            return True
        target = robjs.pos(target)
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

    def log(self, format_string, *args):
        # type: (str, *Any) -> None
        """
        Logs a given string, formatted using str.format.
        """
        if len(args):
            print("[{}][{}] {}".format(self.home.name, self.name, format_string.format(*args)))
        else:
            print("[{}][{}] {}".format(self.home.name, self.name, format_string))

    __pragma__('fcall')

    def should_pickup(self, resource_type = None):
        # type: (Optional[str]) -> bool
        return resource_type is None or resource_type == RESOURCE_ENERGY

    def carry_sum(self):
        # type: () -> int
        if '_carry_sum' not in self.creep:
            self.creep._carry_sum = _.sum(self.creep.carry)
        return self.creep._carry_sum

    def new_target(self, ttype):
        # type: (int) -> RoomObject
        return self.hive.targets.get_new_target(self, ttype)

    def target(self, ttype):
        # type: (int) -> RoomObject
        return self.hive.targets.get_existing_target(self, ttype)

    # noinspection PyPep8Naming
    def toString(self):
        # type: () -> str
        return "Creep[{}, role: {}, home: {}]".format(self.name, self.memory.role, self.home.name)

    # noinspection PyPep8Naming
    def findSpecialty(self):
        # type: () -> str
        return self.creep.findSpecialty()

    __pragma__('nofcall')


def find_new_target_source(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    has_work = not not creep.creep.hasActiveBodyparts(WORK)
    any_miners = not not creep.home.role_count(role_miner)
    highest_priority = -Infinity
    best_source = None
    for source in creep.home.sources:
        if not has_work and not _.some(creep.home.find_in_range(FIND_MY_CREEPS, 1, source.pos),
                                       lambda c: c.memory.role == role_miner):
            continue
        distance = movement.chebyshev_distance_room_pos(source.pos, creep.pos)
        current_work_force = targets.workforce_of(target_source, source.id)
        if any_miners:
            energy = _.sum(creep.home.find_in_range(FIND_DROPPED_RESOURCES, 1, source.pos), 'amount')
            priority = energy - current_work_force * 100 - distance * 2
        else:
            oss = creep.home.get_open_source_spaces_around(source)
            priority = oss * 10 - 100 * current_work_force / oss - distance
        if source.energy <= 0:
            priority -= 200
        if not priority:
            print("[targets] Strange priority result for source {}: {}".format(source, priority))
        if priority > highest_priority:
            best_source = source.id
            highest_priority = priority

    return best_source


def find_new_target_energy_site(targets, creep, pos):
    # type: (TargetMind, RoleBase, Optional[RoomPosition]) -> Optional[str]
    if not pos:
        pos = creep.pos
    if creep.home.full_storage_use:
        best = creep.home.room.storage
        # Still usually prefer storage over any links, unless a lot longer distance (>13 more away)
        best_priority = movement.chebyshev_distance_room_pos(pos, best.pos) - 13
        if creep.home.links.enabled:
            for struct in creep.home.links.links:
                current_targets = targets.targets[target_closest_energy_site][struct.id]
                priority = movement.chebyshev_distance_room_pos(pos, struct.pos)
                if priority < best_priority and (not current_targets or current_targets < 2):
                    best = struct
                    best_priority = priority
        return best.id
    else:
        return None

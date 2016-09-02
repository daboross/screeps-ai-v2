import math

import context
import flags
from constants import target_source, role_dedi_miner, recycle_time, role_recycling, PYFIND_REPAIRABLE_ROADS, \
    PYFIND_BUILDABLE_ROADS, target_closest_energy_site
from control import pathdef
from tools import profiling
from utilities import movement, global_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_DEFAULT_PATH_OPTIONS = {"maxRooms": 1}


class RoleBase:
    """
    :type target_mind: control.targets.TargetMind
    :type creep: Creep
    :type name: str
    :type home: RoomMind
    """

    def __init__(self, target_mind, creep):
        self.target_mind = target_mind
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
        self._home = None
        self._room = None

    def get_harvesting(self):
        return self.memory.harvesting

    def set_harvesting(self, value):
        self.memory.harvesting = value

    harvesting = property(get_harvesting, set_harvesting)

    def get_name(self):
        return self.creep.name

    name = property(get_name)

    def get_pos(self):
        return self.creep.pos

    pos = property(get_pos)

    def get_home(self):
        """
        :rtype: control.hivemind.RoomMind
        """
        if not self._home:
            if not self.memory.home:
                self._home = context.hive().get_closest_owned_room(self.creep.pos.roomName)
                self.memory.home = self._home.room_name
            else:
                self._home = context.hive().get_room(self.memory.home)

        return self._home

    home = property(get_home)

    def get_room(self):
        """
        :rtype: control.hivemind.RoomMind
        """
        if not self._room:
            self._room = context.hive().get_room(self.creep.room.name)
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

    def _get_last_checkpoint(self):
        if self.memory.last_checkpoint:
            if not self._last_checkpoint_as_pos:
                checkpoint = self.memory.last_checkpoint
                if checkpoint.pos:
                    checkpoint = checkpoint.pos
                if checkpoint.x is undefined or checkpoint.y is undefined or checkpoint.roomName is undefined:
                    self.last_checkpoint = None
                    return None
                self._last_checkpoint_as_pos = __new__(RoomPosition(checkpoint.x, checkpoint.y, checkpoint.roomName))
            return self._last_checkpoint_as_pos
        else:
            return None

    def _set_last_checkpoint(self, value):
        if value is None:
            del self.memory.last_checkpoint
            del self.memory.last_target
        else:
            if value.pos:
                # we allow setting last checkpoint to a RoomObject and not just a RoomPosition.
                value = value.pos
            self.memory.last_checkpoint = value
        self._last_checkpoint_as_pos = value

    last_checkpoint = property(_get_last_checkpoint, _set_last_checkpoint)

    def _get_last_target(self):
        if self.memory.last_target:
            if not self._last_target_as_pos:
                target = self.memory.last_target
                if target.pos:
                    target = target.pos
                if target.x is undefined or target.y is undefined or target.roomName is undefined:
                    self.last_target = None
                    return None
                self._last_target_as_pos = __new__(RoomPosition(target.x, target.y, target.roomName))
            return self._last_target_as_pos
        else:
            return None

    def _set_last_target(self, value):
        if value is None:
            del self.memory.last_target
            del self.memory.last_checkpoint
        else:
            if value.pos:
                # we allow setting last target to a RoomObject and not just a RoomPosition.
                value = value.pos
            self.memory.last_target = value
        self._last_target_as_pos = value

    last_target = property(_get_last_target, _set_last_target)

    def _follow_path_to(self, target, set_rhp=False):
        if target.pos:
            target = target.pos
        if self.last_target:
            if not self.last_target.isEqualTo(target):
                # self.log("Last target was {}. Setting that as the new target!".format(self.last_target))
                self.last_checkpoint = self.last_target
                self.last_target = target
        else:
            self.last_target = target
        if self.creep.pos.isNearTo(target):
            self.creep.move(self.creep.pos.getDirectionTo(target))
            return OK
        checkpoint = self.last_checkpoint
        if not checkpoint:
            if self.creep.pos.isEqualTo(target) or (self.creep.pos.inRangeTo(target, 2) and
                                                        movement.is_block_clear(self.creep.room, target.x, target.y)):
                self.last_checkpoint = target
            return self.creep.moveTo(target, _DEFAULT_PATH_OPTIONS)
        elif target.isEqualTo(checkpoint):
            self.log("Creep target not updated! Last checkpoint is still {}, at {} distance away.".format(
                target, self.creep.pos.getRangeTo(target)
            ))
            self.last_checkpoint = None
            return self.creep.moveTo(target, _DEFAULT_PATH_OPTIONS)
        if checkpoint.roomName != self.creep.pos.roomName:
            entrance = movement.get_entrance_for_exit_pos(checkpoint)
            if entrance == -1:
                self.log("Last checkpoint appeared to be an exit, but it was not! Checkpoint: {}, here: {}".format(
                    checkpoint, self.creep.pos))
                self.last_checkpoint = None
                return self.creep.moveTo(target, _DEFAULT_PATH_OPTIONS)
            # TODO: Remove debug logging
            self.last_checkpoint = checkpoint = entrance
            if entrance.roomName != self.creep.pos.roomName:
                self.log("Last checkpoint appeared to be an exit, but it was not! Checkpoint: {}, here: {}."
                         "Removing checkpoint.".format(checkpoint, self.creep.pos))
                self.last_checkpoint = None
                return self.creep.moveTo(target, _DEFAULT_PATH_OPTIONS)

        # TODO: RoleBase should have a reference to the hive!
        path = self.room.honey.find_path(checkpoint, target)
        if set_rhp:
            # TODO: this is a semi-hacky thing to make road building work only for building remote miner roads
            global_cache.set("rhp_{}_{}_{}_{}_{}".format(
                self.pos.roomName, checkpoint.x, checkpoint.y, target.x, target.y),
                [checkpoint.x, checkpoint.y, target.x, target.y], 300)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        # TODO: this code should be able to space out creeps eventually
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            pos = self.creep.pos
            if pos.x != 0 and pos.x != 49 and pos.y != 0 and pos.y != 49:
                # This seems to only ever happen when the path accidentally includes an exit tile, in which case we'll
                # probably find the path again shortly.
                pass
                # self.log("Uh-oh! We've lost the path from {} to {}.".format(self.last_checkpoint, target))

            return self.creep.moveTo(target, _DEFAULT_PATH_OPTIONS)
        if result == OK:
            # TODO: Maybe an option in the move_to call to switch between isNearTo and inRangeTo(2)?
            # If the creep is trying to go *directly on top of* the target, isNearTo is what we want,
            # but if they're just trying to get close to it, inRangeTo is what we want.
            if self.creep.pos.inRangeTo(target, 2) and movement.is_block_clear(self.creep.room, target.x, target.y):
                self.last_checkpoint = target
        elif result == ERR_INVALID_ARGS:
            self.log("Invalid path found: {}".format(JSON.stringify(path)))
        return result

    def move_to_with_queue(self, target, queue_flag_type, full_defined_path=False):
        if target.pos:
            target = target.pos
        if self.creep.pos.roomName != target.roomName:
            return self.move_to(target, False, full_defined_path)

        queue_flag = flags.find_closest_in_room(target, queue_flag_type)

        if not queue_flag or queue_flag.pos.getRangeTo(target) > 10:
            self.log("WARNING! Couldn't find queue flag of type {} close to {}.".format(queue_flag_type, target))
            return self.move_to(target, False, full_defined_path)
        if self.creep.pos.isEqualTo(queue_flag.pos):
            self.last_checkpoint = queue_flag.pos
        if queue_flag.pos.isEqualTo(self.last_checkpoint) and target.roomName == self.last_checkpoint.roomName:
            return self._follow_path_to(target)  # this will precalculate a single path ignoring creeps, and move on it.

        if full_defined_path:
            result = self._follow_path_to(queue_flag)
        else:
            self.last_checkpoint = None
            result = self.creep.moveTo(queue_flag, _DEFAULT_PATH_OPTIONS)
        if result == OK:
            if self.creep.pos.isNearTo(queue_flag.pos) and \
                    movement.is_block_clear(self.creep.room, queue_flag.pos.x, queue_flag.pos.y):
                self.last_checkpoint = queue_flag.pos
        return result

    def _try_move_to(self, pos, follow_defined_path=False):
        here = self.creep.pos

        if here == pos:
            return OK

        if here.roomName != pos.roomName:
            exit_flag = movement.get_exit_flag_to(here.roomName, pos.roomName)
            if exit_flag:
                # pathfind to the flag instead
                pos = exit_flag
            else:
                # TODO: use Map to pathfind a list of room names to get from each room to each room, and use that
                # instead of the direct route using these flags.
                no_exit_flag = movement.get_no_exit_flag_to(here.roomName, pos.roomName)
                if not no_exit_flag:
                    self.log("ERROR: Couldn't find exit flag from {} to {}.".format(here.roomName, pos.roomName))
                self.last_checkpoint = None
                return self.creep.moveTo(pos)  # no _DEFAULT_PATH_OPTIONS since we're doing multi-room here.
        if follow_defined_path:
            # TODO: this is a semi-hacky thing to make road building work only for building remote miner roads
            return self._follow_path_to(pos, True)
        else:
            self.last_checkpoint = None
            return self.creep.moveTo(pos, _DEFAULT_PATH_OPTIONS)

    def move_to(self, target, same_position_ok=False, follow_defined_path=False, already_tried=0):
        if not same_position_ok:
            # do this automatically, and the roles will set it to true once they've reached their destination.
            self.memory.stationary = False
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            result = self._try_move_to(pos, follow_defined_path)

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
            elif result == ERR_NO_PATH:
                # TODO: ERR_NO_PATH should probably get our attention - we should cache this status.
                # for now it's fine though, as we aren't going over our CPU limit.
                return
            elif result != OK:
                if result != ERR_NOT_FOUND:
                    self.log("WARNING: Unknown result from creep.moveByPath: {}", result)

                if not already_tried:
                    self.move_to(target, same_position_ok, follow_defined_path, True)
                else:
                    self.log("WARNING: Failed to move from {} to {} twice.", self.creep.pos, pos)
                    self.last_checkpoint = None
                    self.creep.moveTo(pos, {"reusePath": 0})

    def harvest_energy(self, follow_defined_path=False):
        if self.home.full_storage_use:
            # Full storage use enabled! Just do that.
            storage = self.home.room.storage
            if _.sum(self.creep.carry) == self.creep.carry.energy:  # don't do this if we have minerals
                target = self.target_mind.get_new_target(self, target_closest_energy_site)
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
                    self.memory.harvesting = False
                self.move_to(target, False, follow_defined_path)
                return False

            for stype in Object.keys(self.creep.carry):
                if stype != RESOURCE_ENERGY and self.creep.carry[stype] > 0:
                    result = self.creep.transfer(target, stype)
                    break
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

        if not self.memory.last_source_change or self.memory.last_source_change + 50 < Game.time:
            self.target_mind.untarget(self, target_source)
            self.memory.last_source_change = Game.time
        source = self.target_mind.get_new_target(self, target_source)
        if not source:
            if self.creep.getActiveBodyparts(WORK):
                self.log("Wasn't able to find a source!")
                self.finished_energy_harvest()
            self.go_to_depot(follow_defined_path)
            return False

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source, False, follow_defined_path)
            return False

        piles = self.room.find_in_range(FIND_DROPPED_ENERGY, 3, source.pos)
        if len(piles) > 0:
            pile = piles[0]
            if not self.creep.pos.isNearTo(pile) or not self.last_checkpoint:
                if not self.creep.pos.isNearTo(pile) and self.creep.carry.energy > 0.4 * self.creep.carryCapacity \
                        and self.creep.pos.getRangeTo(pile.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.harvesting = False
                self.move_to_with_queue(pile, flags.SOURCE_QUEUE_START, follow_defined_path)
                return False
            result = self.creep.pickup(pile)
            if result != OK:
                self.log("Unknown result from creep.pickup({}): {}", pile, result)
            return False

        containers = _.filter(self.room.find_in_range(FIND_STRUCTURES, 3, source.pos),
                              {"structureType": STRUCTURE_CONTAINER})
        if len(containers) > 0:
            container = containers[0]
            if not self.creep.pos.isNearTo(container) or not container.pos.isEqualTo(self.last_checkpoint):
                if not self.creep.pos.isNearTo(container) and self.creep.carry.energy > 0.4 * self.creep.carryCapacity \
                        and self.creep.pos.getRangeTo(container.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    self.memory.harvesting = False
                self.move_to_with_queue(container, flags.SOURCE_QUEUE_START, follow_defined_path)

            result = self.creep.withdraw(container, RESOURCE_ENERGY)
            if result != OK:
                self.log("Unknown result from creep.withdraw({}): {}", container, result)

            return False

        if Memory.dedicated_miners_stationed and Memory.dedicated_miners_stationed[source.id]:
            miner = Game.creeps[Memory.dedicated_miners_stationed[source.id]]
            if miner:
                if not miner.pos.isNearTo(source.pos):
                    self.go_to_depot()
                elif not self.creep.pos.isNearTo(miner) or not miner.pos.isEqualTo(self.last_checkpoint):
                    if not self.creep.pos.isNearTo(miner) and self.creep.carry.energy > 0.4 * self.creep.carryCapacity \
                            and self.creep.pos.getRangeTo(miner.pos) > 5:
                        # a spawn fill has given use some extra energy, let's go use it.
                        self.memory.harvesting = False
                    if _.sum(self.room.find_in_range(FIND_DROPPED_ENERGY, 1, source.pos), 'amount') > 1500:
                        # Just get all you can - if this much has built up, it means something's blocking the queue...
                        self.move_to(miner)
                    self.move_to_with_queue(miner, flags.SOURCE_QUEUE_START, follow_defined_path)
                return False  # waiting for the miner to gather energy.
            else:
                self.home.mem.meta.clear_next = 0  # clear next tick
                del Memory.dedicated_miners_stationed[source.id]
        if _.find(self.room.find_in_range(FIND_MY_CREEPS, 2, self.creep.pos), {"memory": {"role": role_dedi_miner}}):
            self.go_to_depot(follow_defined_path)
            return False
        if not self.creep.getActiveBodyparts(WORK):
            self.go_to_depot(follow_defined_path)
            self.finished_energy_harvest()
            return False
        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source, False, follow_defined_path)
            return False

        if not self.memory.action_start_time:
            self.memory.action_start_time = Game.time
        result = self.creep.harvest(source)

        if result != OK and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from creep.harvest({}): {}", source, result)
        return False

    def finished_energy_harvest(self):
        del self.memory.action_start_time
        self.target_mind.untarget(self, target_source)
        self.target_mind.untarget(self, target_closest_energy_site)

    def repair_nearby_roads(self):
        if self.creep.getActiveBodyparts(WORK) <= 0:
            return
        if self.creep.carry.energy <= 0:
            return
        repair = self.room.find_in_range(PYFIND_REPAIRABLE_ROADS, 2, self.creep.pos)
        if len(repair):
            result = self.creep.repair(repair[0])
            if result != OK:
                self.log("Unknown result from passingby-road-repair on {}: {}".format(repair[0], result))
        else:
            build = self.room.find_in_range(PYFIND_BUILDABLE_ROADS, 2, self.creep.pos)
            if len(build):
                result = self.creep.build(build[0])
                if result != OK:
                    self.log("Unknown result from passingby-road-build on {}: {}".format(build[0], result))

    def go_to_depot(self, follow_defined_path=False):
        depots = flags.find_flags(self.home, flags.DEPOT)
        if len(depots):
            self.move_to(depots[0], True, follow_defined_path)
        else:
            depots = flags.find_flags_global(flags.DEPOT)
            if len(depots):
                self.move_to(depots[0], True, follow_defined_path)
            else:
                self.move_to(self.home.spawn, True, follow_defined_path)

    def recycle_me(self):
        spawn = self.home.spawns[0]
        if not spawn:
            self.go_to_depot()
            return
        if not self.creep.pos.isNearTo(spawn.pos):
            self.move_to(self.home.spawns[0])
        else:
            result = spawn.recycleCreep(self.creep)
            if result == OK:
                if self.memory.role == role_recycling:
                    self.log("{} recycled (ttl: {}).", self.memory.last_role, self.creep.ticksToLive)
                else:
                    self.log("{} committed suicide (ttl: {}).", self.memory.role, self.creep.ticksToLive)
                self.home.mem.meta.clear_next = 0  # clear next tick
            else:
                self.log("Unknown result from {}.recycleCreep({})! {}", spawn, self.creep, result)
                self.go_to_depot()

    def empty_to_storage(self):
        total = _.sum(self.creep.carry)
        if total > 0:
            self.creep.say("Emptying", True)
            storage = self.home.room.storage
            if storage:
                if self.creep.pos.isNearTo(storage.pos):
                    for rtype in Object.keys(self.creep.carry):
                        if self.creep.carry[rtype] > 0:
                            result = self.creep.transfer(storage, rtype)
                            if result == OK:
                                return True
                            else:
                                self.log("Unknown result from emptying-creep.transfer({}, {}): {}"
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
        if Game.time % 5 < 3:
            self.move_around_clockwise(target)
        else:
            self.move_around_counter_clockwise(target)

    def move_around_clockwise(self, target):
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
        if target.pos: target = target.pos
        if self.pos.isEqualTo(target):
            return True
        dx = target.x - self.pos.x
        dy = target.y - self.pos.y
        # Don't divide by zero
        if dx:
            dx /= abs(dx)
        if dy:
            dy /= abs(dy)
        if dx and movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y):
            self.creep.move(pathdef.get_direction(dx, 0))
            return True
        elif dy and movement.is_block_clear(self.room, self.pos.y + dy, self.pos.x):
            self.creep.move(pathdef.get_direction(0, dy))
            return True
        elif dx and dy and movement.is_block_clear(self.room, self.pos.x + dx, self.pos.y + dy):
            self.creep.move(pathdef.get_direction(dx, dy))
            return True
        else:
            return False

    def report(self, task_array, *args):
        if not Memory.meta.quiet or task_array[1]:
            if self.memory.action_start_time:
                time = Game.time - self.memory.action_start_time
            else:
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
        print("[{}][{}] {}".format(self.home.room_name, self.name, format_string.format(*args)))

    def toString(self):
        return "Creep[role: {}, home: {}]".format(self.memory.role, self.home.room_name)


profiling.profile_whitelist(RoleBase, [
    "_calculate_time_to_replace",
    "_follow_path_to",
    "move_to_with_queue",
    "_try_move_to",
    "move_to",
    "harvest_energy",
    "is_next_block_clear",
])

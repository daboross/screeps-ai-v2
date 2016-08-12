import math

import context
import flags
import speech
from constants import target_source, role_dedi_miner
from tools import profiling
from utilities import movement
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

    def get_harvesting(self):
        return self.memory.harvesting

    def set_harvesting(self, value):
        self.memory.harvesting = value

    harvesting = property(get_harvesting, set_harvesting)

    def get_name(self):
        return self.creep.name

    name = property(get_name)

    def get_home(self):
        """
        :rtype: control.hivemind.RoomMind
        """
        if self.memory.home:
            return context.hive().get_room(self.memory.home)

        room = context.hive().get_closest_owned_room(self.creep.pos.roomName)
        self.memory.home = room.name
        return room

    home = property(get_home)

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
            # self.log("Calculated replacement time: {\n\tcurrent_time: {}\n\tttr: {}"
            #          "\n\tdeath_time: {}\n\treplacement_time: {}\n}",
            #          Game.time, ttr, Game.time + ticks_to_live, replacement_time)
            return self.memory.calculated_replacement_time

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3

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

    def _follow_path_to(self, target):
        if target.pos:
            target = target.pos
        if self.last_target:
            if not self.last_target.isEqualTo(target):
                # self.log("Last target was {}. Setting that as the new target!".format(self.last_target))
                self.last_checkpoint = self.last_target
                self.last_target = target
        else:
            self.last_target = target
        if not self.last_checkpoint:
            if self.creep.pos.isEqualTo(target) or (self.creep.pos.inRangeTo(target, 2) and
                                                        movement.is_block_clear(self.creep.room, target.x, target.y)):
                self.last_checkpoint = target
            return self.creep.moveTo(target)
        elif target.isEqualTo(self.last_checkpoint):
            self.log("Creep target not updated! Last checkpoint is still {}, at {} distance away.".format(
                target, self.creep.pos.getRangeTo(target)
            ))
            self.last_checkpoint = None
            return self.creep.moveTo(target)
        if self.last_checkpoint.roomName != self.creep.pos.roomName:
            entrance = movement.get_entrance_for_exit_pos(self.last_checkpoint)
            if entrance == -1:
                self.log("Last checkpoint appeared to be an exit, but it was not! Checkpoint: {}, here: {}".format(
                    self.last_checkpoint, self.creep.pos))
                self.last_checkpoint = None
                return self.creep.moveTo(target)
            # TODO: Remove debug logging
            self.last_checkpoint = entrance
            if entrance.roomName != self.creep.pos.roomName:
                self.log("Last checkpoint appeared to be an exit, but it was not! Checkpoint: {}, here: {}."
                         "Removing checkpoint.".format(self.last_checkpoint, self.creep.pos))
                self.last_checkpoint = None
                return self.creep.moveTo(target)

        # TODO: RoleBase should have a reference to the hive!
        room = context.hive().get_room(self.creep.pos.roomName)
        path = room.honey.find_path(self.last_checkpoint, target)
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

            return self.creep.moveTo(target)
        if result == OK:
            # TODO: Maybe an option in the move_to call to switch between isNearTo and inRangeTo(2)?
            # If the creep is trying to go *directly on top of* the target, isNearTo is what we want,
            # but if they're just trying to get close to it, inRangeTo is what we want.
            if self.creep.pos.inRangeTo(target, 2) and movement.is_block_clear(self.creep.room, target.x, target.y):
                self.last_checkpoint = target
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
        if queue_flag.pos.isEqualTo(self.last_checkpoint):
            return self._follow_path_to(target)  # this will precalculate a single path ignoring creeps, and move on it.

        if full_defined_path:
            result = self._follow_path_to(queue_flag)
        else:
            self.last_checkpoint = None
            result = self.creep.moveTo(queue_flag)
        if result == OK:
            if self.creep.pos.isNearTo(queue_flag.pos) and \
                    movement.is_block_clear(self.creep.room, queue_flag.pos.x, queue_flag.pos.y):
                self.last_checkpoint = queue_flag.pos
        return result

    def _try_move_to(self, pos, same_position_ok=False, follow_defined_path=False):
        here = self.creep.pos

        if here == pos:
            return OK

        if here.roomName != pos.roomName:
            difference = movement.inter_room_difference(here.roomName, pos.roomName)
            if not difference:
                self.log("Couldn't find direction from {} to {} (target pos: {}, {})!!",
                         here.roomName, pos.roomName, pos, pos.pos)
                return OK
            exit_flag, exit_direction = movement.get_exit_flag_and_direction(here.roomName, pos.roomName, difference)
            if exit_flag:
                # pathfind to the flag instead
                pos = exit_flag
            else:
                return OK
        if follow_defined_path:
            return self._follow_path_to(pos)
        else:
            self.last_checkpoint = None
            return self.creep.moveTo(pos)

    def move_to(self, target, same_position_ok=False, follow_defined_path=False, times_tried=0):
        if not same_position_ok:
            # do this automatically, and the roles will set it to true once they've reached their destination.
            self.memory.stationary = False
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            result = self._try_move_to(pos, same_position_ok, follow_defined_path)

            if result == ERR_NO_BODYPART:
                # TODO: check for towers here, or use RoomMind to do that.
                self.log("Couldn't move, all move parts dead!")
                if not len(self.creep.room.find(FIND_MY_STRUCTURES, {"filter": {"structureType": STRUCTURE_TOWER}})):
                    self.creep.suicide()
                    self.home.mem.meta.clear_now = True
            elif result == ERR_NO_PATH:
                # TODO: ERR_NO_PATH should probably get our attention - we should cache this status.
                # for now it's fine though, as we aren't going over our CPU limit.
                return
            elif result != OK:
                if result != ERR_NOT_FOUND:
                    self.log("Unknown result from creep.moveByPath: {}", result)

                times_tried = times_tried or 0
                if times_tried < 2:
                    self.move_to(target, same_position_ok, follow_defined_path, times_tried + 1)
                else:
                    self.log("Continually failed to move from {} to {}!", self.creep.pos, pos)
                    self.last_checkpoint = None
                    self.creep.moveTo(pos, {"reusePath": 0})

    def harvest_energy(self):
        if context.room().full_storage_use:
            # Full storage use enabled! Just do that.
            storage = context.room().room.storage
            if not self.creep.pos.isNearTo(storage.pos):
                # TODO: 5 should ideally be instead 1/4 of the distance to this creep's next target.
                if self.creep.carry.energy > 0 and self.creep.pos.getRangeTo(storage.pos) > 5:
                    # a spawn fill has given use some extra energy, let's go use it.
                    # TODO: some unified dual-interface for harvesting and jobs
                    self.memory.harvesting = False
                self.pick_up_available_energy()
                self.move_to(storage)
                self.report(speech.default_gather_moving_to_storage)
                return False

            if _.sum(self.creep.carry) > self.creep.carry.energy:
                for type in Object.keys(self.creep.carry):
                    if type != RESOURCE_ENERGY:
                        result = self.creep.trasnfer(storage, type)
                        break
                else:
                    result = self.creep.withdraw(storage, RESOURCE_ENERGY)
            else:
                result = self.creep.withdraw(storage, RESOURCE_ENERGY)

            if result == OK:
                self.report(speech.default_gather_storage_withdraw_ok)
            else:
                self.log("Unknown result from creep.withdraw({}): {}", storage, result)
                self.report(speech.default_gather_unknown_result_withdraw)
            return False

        source = self.target_mind.get_new_target(self, target_source)
        if not source:
            self.log("Wasn't able to find a source!")
            self.finished_energy_harvest()
            self.go_to_depot()
            self.report(speech.default_gather_no_sources)
            return False

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            self.report(speech.default_gather_moving_between_rooms)
            return False

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            pile = piles[0]
            if not self.creep.pos.isNearTo(pile) or not self.last_checkpoint:
                self.move_to_with_queue(pile, flags.SOURCE_QUEUE_START)
                self.report(speech.default_gather_moving_to_energy)
                return False
            result = self.creep.pickup(pile)
            if result == OK:
                self.report(speech.default_gather_energy_pickup_ok)
            else:
                self.log("Unknown result from creep.pickup({}): {}", pile, result)
                self.report(speech.default_gather_unknown_result_pickup)
            return False

        containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
            (struct.structureType == STRUCTURE_CONTAINER
             or struct.structureType == STRUCTURE_STORAGE)
            and struct.store >= 0
        )})
        if len(containers) > 0:
            container = containers[0]
            if not self.creep.pos.isNearTo(container) or not container.pos.isEqualTo(self.last_checkpoint):
                self.report(speech.default_gather_moving_to_container)
                self.move_to_with_queue(container, flags.SOURCE_QUEUE_START)

            result = self.creep.withdraw(container, RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.default_gather_container_withdraw_ok)
            else:
                self.log("Unknown result from creep.withdraw({}): {}", container, result)
                self.report(speech.default_gather_unknown_result_withdraw)
            return False

        miner = None
        if Memory.dedicated_miners_stationed and Memory.dedicated_miners_stationed[source.id]:
            miner = Game.creeps[Memory.dedicated_miners_stationed[source.id]]
            if miner:
                if not self.creep.pos.isNearTo(miner) or not miner.pos.isEqualTo(self.last_checkpoint):
                    self.report(speech.default_gather_moving_to_source)  # TODO: moving to miner speech
                    self.move_to_with_queue(miner, flags.SOURCE_QUEUE_START)
                return False  # waiting for the miner to gather energy.
            else:
                self.home.mem.meta.clear_now = True
                del Memory.dedicated_miners_stationed[source.id]

        if len(self.creep.pos.findInRange(FIND_MY_CREEPS, 2, {"filter": {"memory": {"role": role_dedi_miner}}})):
            self.go_to_depot()
            return False
        if not self.creep.getActiveBodyparts(WORK):
            self.go_to_depot()
            self.finished_energy_harvest()
            return False
        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source)
            self.report(speech.default_gather_moving_to_source)
            return False

        if not self.memory.action_start_time:
            self.memory.action_start_time = Game.time
        result = self.creep.harvest(source)

        if result == OK:
            self.report(speech.default_gather_source_harvest_ok)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
            self.report(speech.default_gather_source_harvest_ner)
        else:
            self.log("Unknown result from creep.harvest({}): {}", source, result)
            self.report(speech.default_gather_unknown_result_harvest)
        return False

    def finished_energy_harvest(self):
        del self.memory.action_start_time
        self.target_mind.untarget(self, target_source)

    def pick_up_available_energy(self):
        if self.creep.getActiveBodyparts(CARRY) <= 0:
            return
        resources = self.creep.pos.lookFor(LOOK_RESOURCES)
        for resource in resources:
            if resource.resourceType == RESOURCE_ENERGY:
                self.creep.pickup(resource)
                break

    def go_to_depot(self):
        depots = flags.find_flags(self.home, flags.DEPOT)
        self.pick_up_available_energy()
        if len(depots):
            self.move_to(depots[0], True)
        else:
            depots = flags.find_flags_global(flags.DEPOT)
            if len(depots):
                self.move_to(depots[0], True)
            else:
                self.move_to(Game.spawns[0], True)

    def recycle_me(self):
        spawn = self.home.spawns[0]
        if not self.creep.pos.isNearTo(spawn.pos):
            self.pick_up_available_energy()
            self.move_to(self.home.spawns[0])
        else:
            result = spawn.recycleCreep(self.creep)
            if result == OK:
                self.log("{} committed suicide (life left: {}).", self.memory.role, self.creep.ticksToLive)
                self.home.mem.meta.clear_now = True
            else:
                self.log("Unknown result from {}.recycleCreep({})! {}", spawn, self.creep, result)
                self.go_to_depot()

    # def _calculate_renew_cost_per_tick(self):
    #     creep_cost = _.sum()
    #
    # def renew_me(self):
    #     spawn = self.home.spawns[0]
    #     if self.home.room.energyAvailable < min(self.home.room.energyCapacityAvailable / 2.0, )

    def is_next_block_clear(self, target):
        next_pos = __new__(RoomPosition(target.pos.x, target.pos.y, target.pos.roomName))
        creep_pos = self.creep.pos
        if creep_pos.roomName != next_pos.roomName:
            return True
        # Apparently, I thought it would be best if we start at the target position, and continue looking for open
        # spaces until we get to the origin position. Thus, if we encounter an obstacle, we use "continue", and if the
        # result is that we've reached the creep position, we return false.
        while True:
            if next_pos.x == creep_pos.x and next_pos.y == creep_pos.y:
                return False
            elif next_pos.x < 0 or next_pos.y < 0 or next_pos.x > 50 or next_pos.y > 50:
                return False

            direction = next_pos.getDirectionTo(creep_pos)

            if direction == TOP:
                next_pos.y -= 1
            elif direction == TOP_RIGHT:
                next_pos.x += 1
                next_pos.y -= 1
            elif direction == RIGHT:
                next_pos.x += 1
            elif direction == BOTTOM_RIGHT:
                next_pos.x += 1
                next_pos.y -= 1
            elif direction == BOTTOM:
                next_pos.y += 1
            elif direction == BOTTOM_LEFT:
                next_pos.x -= 1
                next_pos.y += 1
            elif direction == LEFT:
                next_pos.x -= 1
            elif direction == TOP_LEFT:
                next_pos.y -= 1
                next_pos.x -= 1
            else:
                self.log("Unknown result from pos.getDirectionTo(): {}", direction)
                return False

            creeps = next_pos.lookFor(LOOK_CREEPS)
            if len(creeps):
                continue
            terrain = next_pos.lookFor(LOOK_TERRAIN)
            if terrain[0].type & TERRAIN_MASK_WALL == TERRAIN_MASK_WALL \
                    or terrain[0].type & TERRAIN_MASK_LAVA == TERRAIN_MASK_LAVA:
                continue

            structures = next_pos.lookFor(LOOK_STRUCTURES)
            if len(structures):
                continue

            return True

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


profiling.profile_whitelist(RoleBase, [
    "_calculate_time_to_replace",
    "_follow_path_to",
    "move_to_with_queue",
    "_try_move_to",
    "move_to",
    "harvest_energy",
    "pick_up_available_energy",
    "is_next_block_clear",
])

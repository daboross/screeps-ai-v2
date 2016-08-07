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
    :type target_mind: hivemind.TargetMind
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
                    print("[{}] ticksToLive is not defined, while spawning is false!".format(self.name))
            ttr = self._calculate_time_to_replace()
            if ttr == -1:
                ttr = RoleBase._calculate_time_to_replace(self)
                store = False
            replacement_time = Game.time + ticks_to_live - ttr
            if store:
                self.memory.calculated_replacement_time = math.floor(replacement_time)
            # print("[{}] Calculated replacement time: {\n\tcurrent_time: {}\n\tttr: {}"
            #       "\n\tdeath_time: {}\n\treplacement_time: {}\n}".format(
            #     self.name, Game.time, ttr, Game.time + ticks_to_live, replacement_time
            # ))
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

    def _try_move_to(self, pos):
        here = self.creep.pos

        if here == pos:
            return None

        if here.roomName != pos.roomName:
            difference = movement.inter_room_difference(here.roomName, pos.roomName)
            if not difference:
                print("[{}] Couldn't find direction from {} to {}!!".format(
                    self.name, here.roomName, pos.roomName))
                return None
            if abs(difference[0]) > abs(difference[1]):
                if difference[0] > 0:
                    direction = RIGHT
                else:
                    direction = LEFT
            else:
                if difference[1] > 0:
                    direction = BOTTOM
                else:
                    direction = TOP

            flag_list = flags.find_flags(here.roomName, flags.DIR_TO_EXIT_FLAG[direction])
            if not len(flag_list):
                # If we have another direction (if path is diagonal), try another way?
                if abs(difference[0]) > abs(difference[1]):
                    if difference[1] > 0:
                        direction = BOTTOM
                    elif difference[1] < 0:
                        direction = TOP
                else:
                    if difference[0] > 0:
                        direction = RIGHT
                    elif difference[0] < 0:
                        direction = LEFT
                flag_list = flags.find_flags(here.roomName, flags.DIR_TO_EXIT_FLAG[direction])
            if not len(flag_list):
                print("[{}] Couldn't find exit flag in room {} to direction {}! [targetting room {} from room {}]"
                      .format(self.name, here.roomName, flags.DIR_TO_EXIT_FLAG[direction], pos.roomName, here.roomName))
                return None

            # pathfind to the flag instead
            pos = flag_list[0].pos

        return self.creep.moveTo(pos)

    def move_to(self, target, same_position_ok=False, options=None, times_tried=0):
        if not same_position_ok:
            # do this automatically, and the roles will set it to true once they've reached their destination.
            self.memory.stationary = False
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            result = self._try_move_to(pos)

            if result == ERR_NO_BODYPART:
                # TODO: check for towers here, or use RoomMind to do that.
                print("[{}] Couldn't move, all move parts dead!".format(self.name))
                if not len(self.creep.room.find(FIND_MY_STRUCTURES, {"filter": {"structureType": STRUCTURE_TOWER}})):
                    self.creep.suicide()
                    Memory.meta.clear_now = False
            elif result != OK:
                if result != ERR_NOT_FOUND:
                    print("[{}] Unknown result from creep.moveByPath: {}".format(
                        self.name, result
                    ))

                times_tried = times_tried or 0
                if times_tried < 2:
                    self.move_to(target, same_position_ok, options, times_tried + 1)
                else:
                    print("[{}] Continually failed to move from {} to {}!".format(self.name, self.creep.pos, pos))
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
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, storage, result))
                self.report(speech.default_gather_unknown_result_withdraw)
            return False

        source = self.target_mind.get_new_target(self.creep, target_source)
        if not source:
            print("[{}] Wasn't able to find a source!".format(self.name))
            self.finished_energy_harvest()
            self.go_to_depot()
            self.report(speech.default_gather_no_sources)
            return True

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            self.report(speech.default_gather_moving_between_rooms)
            return False

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            result = self.creep.pickup(piles[0])
            if result == ERR_NOT_IN_RANGE:
                self.move_to(piles[0])
                self.report(speech.default_gather_moving_to_energy)
            elif result != OK:
                print("[{}] Unknown result from creep.pickup({}): {}".format(
                    self.name, piles[0], result))
                self.report(speech.default_gather_unknown_result_pickup)
            else:
                self.report(speech.default_gather_energy_pickup_ok)
            return False

        containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
            (struct.structureType == STRUCTURE_CONTAINER
             or struct.structureType == STRUCTURE_STORAGE)
            and struct.store >= 0
        )})
        if containers.length > 0:
            if not self.creep.pos.isNearTo(containers[0]):
                self.report(speech.default_gather_moving_to_container)
                self.move_to(containers[0])

            result = self.creep.withdraw(containers[0], RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.default_gather_container_withdraw_ok)
            else:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, containers[0], result))
                self.report(speech.default_gather_unknown_result_withdraw)
            return False

        # at this point, there is no energy and no container filled.
        # we should ensure that if there's a big harvester, it hasn't died!
        if Memory.dedicated_miners_stationed \
                and Memory.dedicated_miners_stationed[source.id] \
                and not Game.creeps[Memory.dedicated_miners_stationed[source.id]]:
            Memory.meta.clear_now = True
            del Memory.dedicated_miners_stationed[source.id]

            if self.creep.getActiveBodyparts(WORK):
                self.move_to(source)
                self.report(speech.default_gather_moving_to_source)
            else:
                #TODO speach here
                self.go_to_depot()
        else:
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
                print("[{}] Unknown result from creep.harvest({}): {}".format(
                    self.name, source, result))
                self.report(speech.default_gather_unknown_result_harvest)
        return False

    def finished_energy_harvest(self):
        del self.memory.action_start_time
        self.target_mind.untarget(self.creep, target_source)

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
                print("[{}] {} committed suicide.".format(self.name, self.memory.role))
                Memory.meta.clear_now = True
            else:
                print("[{}] Unknown result from {}.recycleCreep({})! {}".format(
                    self.name, spawn, self.creep, result
                ))
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
                print("[{}] Unknown result from pos.getDirectionTo(): {}".format(
                    self.name, direction))
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


profiling.profile_class(RoleBase, ["harvesting", "name", "home"])

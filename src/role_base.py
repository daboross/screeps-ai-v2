import context
import flags
import speach
from constants import target_source
from tools import profiling
from utils import movement, pathfinding
from utils.screeps_constants import *

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

    def run(self):
        """
        Runs this role's actions.
        :return: False if completed successfully, true if this method should be called a second time.
        :rtype Boolean:
        """
        pass

    def _get_new_path_to(self, target_id, target_pos, options):
        # if not options:
        #     options = _DEFAULT_PATH_OPTIONS
        # path = self.creep.pos.findPathTo(target_pos, options)
        path = pathfinding.find_path(self.creep.room, self.creep.pos, target_pos, options)
        if path is None:
            return None
        self.memory.path[target_id] = Room.serializePath(path)
        self.memory.reset_path[target_id] = Game.time + 20  # Reset every 20 ticks
        self.memory.same_place_ticks = 0
        return path

    def _get_path_to(self, pos, same_position_ok=False, options=None):
        if not self.memory.path:
            self.memory.path = {}
        if not self.memory.reset_path:
            self.memory.reset_path = {}

        target_id = pos.x + "_" + pos.y + "_" + pos.roomName

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

            flag_list = flags.get_flags(here.roomName, flags.DIR_TO_EXIT_FLAG[direction])
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
                flag_list = flags.get_flags(here.roomName, flags.DIR_TO_EXIT_FLAG[direction])
            if not len(flag_list):
                print("[{}] Couldn't find exit flag in room {} to direction {}! [targetting room {} from room {}]"
                    .format(
                    self.name, here.roomName, flags.DIR_TO_EXIT_FLAG[direction],
                    pos.roomName, here.roomName
                ))
                return None

            # pathfind to the flag instead
            pos = flag_list[0].pos

        if self.memory.path[target_id] and self.memory.reset_path \
                and self.memory.reset_path[target_id] > Game.time:
            if not same_position_ok:
                if (self.memory.last_pos and
                            self.memory.last_pos.x == here.x and
                            self.memory.last_pos.y == here.y):
                    if not self.memory.same_place_ticks:
                        self.memory.same_place_ticks = 1
                    elif self.memory.same_place_ticks < 2:
                        self.memory.same_place_ticks += 1
                    else:
                        if not self.memory.retried_level:
                            print("[{}] Regenerating path from {} to {}".format(
                                self.name, here, pos
                            ))
                            self.memory.retried_level = 1
                            return self._get_new_path_to(target_id, pos, options)
                        elif self.memory.retried_level <= 1:
                            print("[{}] Trying avoid-all-creeps path from {} to {}".format(
                                self.name, here, pos
                            ))
                            self.memory.retried_level = 2
                            if options:
                                options["avoid_all_creeps"] = True
                            return self._get_new_path_to(target_id, pos, options)
                        else:
                            print("[{}] Trying manual move path from {} to {}! retried_level: {}".format(
                                self.name, here, pos, self.memory.retried_level
                            ))
                            self.memory.retried_level += 1
                            return None
                else:
                    del self.memory.same_place_ticks
                    del self.memory.retried_level
                    self.memory.last_pos = here
            try:
                return Room.deserializePath(self.memory.path[target_id])
            except:
                del self.memory.path[target_id]
        return self._get_new_path_to(target_id, pos, options)

    def move_to(self, target, same_position_ok=False, options=None, times_tried=0):
        if not same_position_ok:
            # do this automatically, and the roles will set it to true once they've reached their destination.
            self.memory.stationary = False
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            path = self._get_path_to(pos, same_position_ok, options)
            if path is None:  # trigger for manual movement
                print("[{}] Manually moving.".format(self.name))
                result = self.creep.moveTo(target, {"reusePath": 0})
            else:
                result = self.creep.moveByPath(path)

            if result == ERR_NO_BODYPART:
                # TODO: check for towers here, or use RoomMind to do that.
                print("[{}] Couldn't move, all move parts dead!".format(self.name))
                self.creep.suicide()
                Memory.meta.clear_now = False
            elif result != OK:
                if result != ERR_NOT_FOUND:
                    print("[{}] Unknown result from creep.moveByPath: {}".format(
                        self.name, result
                    ))

                target_id = pos.x + "_" + pos.y + "_" + pos.roomName
                del self.memory.path[target_id]
                if not times_tried:
                    times_tried = 0
                if times_tried < 2:
                    self.move_to(target, same_position_ok, options, times_tried + 1)
                else:
                    print("[{}] Continually failed to move from {} to {} (path: {})!".format(
                        self.name, self.creep.pos, pos, path))
                    self.creep.moveTo(pos, {"reusePath": 0})

    def harvest_energy(self):
        if context.room().full_storage_use:
            # Full storage use enabled! Just do that.
            storage = self.creep.room.storage
            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage)
                self.report(speach.default_gather_moving_to_storage)
                return False

            result = self.creep.withdraw(storage, RESOURCE_ENERGY)

            if result == OK:
                self.report(speach.default_gather_storage_withdraw_ok)
            else:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, storage, result))
                self.report(speach.default_gather_unknown_result_withdraw)
            return False

        source = self.target_mind.get_new_target(self.creep, target_source)
        if not source:
            print("[{}] Wasn't able to find a source!".format(self.name))
            self.finished_energy_harvest()
            self.go_to_depot()
            self.report(speach.default_gather_no_sources)
            return True

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            self.report(speach.default_gather_moving_between_rooms)
            return False

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            result = self.creep.pickup(piles[0])
            if result == ERR_NOT_IN_RANGE:
                self.move_to(piles[0])
                self.report(speach.default_gather_moving_to_energy)
            elif result != OK:
                print("[{}] Unknown result from creep.pickup({}): {}".format(
                    self.name, piles[0], result))
                self.report(speach.default_gather_unknown_result_pickup)
            else:
                self.report(speach.default_gather_energy_pickup_ok)
            return False

        containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
            (struct.structureType == STRUCTURE_CONTAINER
             or struct.structureType == STRUCTURE_STORAGE)
            and struct.store >= 0
        )})
        if containers.length > 0:
            if not self.creep.pos.isNearTo(containers[0]):
                self.report(speach.default_gather_moving_to_container)
                self.move_to(containers[0])

            result = self.creep.withdraw(containers[0], RESOURCE_ENERGY)
            if result == OK:
                self.report(speach.default_gather_container_withdraw_ok)
            else:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, containers[0], result))
                self.report(speach.default_gather_unknown_result_withdraw)
            return False

        # at this point, there is no energy and no container filled.
        # we should ensure that if there's a big harvester, it hasn't died!
        if (Memory.big_harvesters_placed
            and Memory.big_harvesters_placed[source.id]
            and not Game.creeps[Memory.big_harvesters_placed[source.id]]):
            Memory.meta.clear_now = True
            del Memory.big_harvesters_placed[source.id]
            self.move_to(source)
            self.report(speach.default_gather_moving_to_source)
        else:
            if not self.creep.pos.isNearTo(source.pos):
                self.move_to(source)
                self.report(speach.default_gather_moving_to_source)
                return False

            result = self.creep.harvest(source)

            if result == OK:
                self.report(speach.default_gather_source_harvest_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
                self.report(speach.default_gather_source_harvest_ner)
            else:
                print("[{}] Unknown result from creep.harvest({}): {}".format(
                    self.name, source, result))
                self.report(speach.default_gather_unknown_result_harvest)
        return False

    def finished_energy_harvest(self):
        self.target_mind.untarget(self.creep, target_source)

    def go_to_depot(self):
        depots = flags.get_global_flags(flags.DEPOT)
        if len(depots):
            self.move_to(depots[0], True)
        else:
            self.move_to(Game.spawns[0], True)

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

            dir = next_pos.getDirectionTo(creep_pos)

            if dir == TOP:
                next_pos.y -= 1
            elif dir == TOP_RIGHT:
                next_pos.x += 1
                next_pos.y -= 1
            elif dir == RIGHT:
                next_pos.x += 1
            elif dir == BOTTOM_RIGHT:
                next_pos.x += 1
                next_pos.y -= 1
            elif dir == BOTTOM:
                next_pos.y += 1
            elif dir == BOTTOM_LEFT:
                next_pos.x -= 1
                next_pos.y += 1
            elif dir == LEFT:
                next_pos.x -= 1
            elif dir == TOP_LEFT:
                next_pos.y -= 1
                next_pos.x -= 1
            else:
                print("[{}] Unknown result from pos.getDirectionTo(): {}".format(
                    self.name, dir))
                return False

            creeps = next_pos.lookFor(LOOK_CREEPS)
            if len(creeps):
                continue
            terrain = next_pos.lookFor(LOOK_TERRAIN)
            if (terrain[0].type & TERRAIN_MASK_WALL == TERRAIN_MASK_WALL
                or terrain[0].type & TERRAIN_MASK_LAVA == TERRAIN_MASK_LAVA):
                continue

            structures = next_pos.lookFor(LOOK_STRUCTURES)
            if len(structures):
                continue

            return True

    def report(self, task_array, arg=None):
        if not Memory.meta.quiet or task_array[1]:
            if self.memory.action_start_time:
                time = Game.time - self.memory.action_start_time
            else:
                time = Game.time
            if arg:
                stuff = task_array[0][time % len(task_array[0])].format(arg)
            else:
                stuff = task_array[0][time % len(task_array[0])]
            if stuff != None:
                self.creep.say(stuff, True)


profiling.profile_class(RoleBase, ["harvesting", "name", "home"])

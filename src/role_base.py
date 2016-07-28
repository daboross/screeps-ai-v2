import creep_utils
import flags
import hivemind
from base import *

__pragma__('noalias', 'name')

PathFinder.use(True)

_DEFAULT_PATH_OPTIONS = {"maxRooms": 1}


class RoleBase:
    """
    :type target_mind: hivemind.TargetMind
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

    def run(self):
        """
        Runs this role's actions.
        :return: False if completed successfully, true if this method should be called a second time.
        :rtype Boolean:
        """
        pass

    def _get_new_path_to(self, target_id, pos, options):
        # TODO: Use this once we get a custom CostMatrix with/ creeps figured out.
        # path = PathFinder.search(self.creep.pos, pos, {"maxRooms": 1})
        # if not path:
        #     return None
        # else:
        #     path = path.path  # it's an object
        if not options:
            options = _DEFAULT_PATH_OPTIONS
        path = self.creep.pos.findPathTo(pos, options)
        self.memory.path[target_id] = Room.serializePath(path)
        self.memory.reset_path[target_id] = Game.time + 100  # Reset every 100 ticks
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
            direction = creep_utils.parse_room_direction_to(here.roomName, pos.roomName)
            if not direction:
                print("[{}] Couldn't find direction from {} to {}!!".format(
                    self.name, here.roomName, pos.roomName))
                return None
            flag = flags.get_flags(here.roomName, flags.DIR_TO_EXIT_FLAG[direction])
            if not flag:
                print("[{}] Couldn't find exit flag in room {} to direction {}!".format(
                    self.name, here.roomName, direction))

            # pathfind to the flag instead
            pos = flag.pos

        if self.memory.path[target_id] and self.memory.reset_path \
                and self.memory.reset_path[target_id] > Game.time:
            if not same_position_ok:
                if (self.memory.last_pos and
                            self.memory.last_pos.x == here.x and
                            self.memory.last_pos.y == here.y):
                    if not self.memory.same_place_ticks:
                        self.memory.same_place_ticks = 1
                    elif self.memory.same_place_ticks < 3:
                        self.memory.same_place_ticks += 1
                    else:
                        print("[{}] Regenerating path from {} to {}".format(
                            self.name, here, pos
                        ))

                        return self._get_new_path_to(target_id, pos, options)
                else:
                    del self.memory.same_place_ticks
                    self.memory.last_pos = here
            try:
                return Room.deserializePath(self.memory.path[target_id])
            except:
                del self.memory.path[target_id]
        return self._get_new_path_to(target_id, pos, options)

    def move_to(self, target, same_position_ok=False, options=None, times_tried=0):
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            path = self._get_path_to(pos, same_position_ok, options)
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

                target_id = target.pos.x + "_" + target.pos.y + "_" + target.pos.roomName
                del self.memory.path[target_id]
                if not times_tried:
                    times_tried = 0
                if times_tried < 2:
                    self.move_to(target, same_position_ok, options, times_tried + 1)
                else:
                    print("[{}] Continually failed to move from {} to {} (path: {})!".format(
                        self.name, self.creep.pos, target.pos, path))
                    self.creep.moveTo(target)

    def harvest_energy(self):
        source = self.target_mind.get_new_target(self.creep, hivemind.target_source)
        if not source:
            print("[{}] Wasn't able to find a source!".format(self.name))
            self.finished_energy_harvest()
            self.report("D! G No S.")
            self.go_to_depot()
            return True

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            self.report("G. F. BR.")
            return False

        if source.color:
            # this is a flag
            sources = source.pos.lookFor(LOOK_SOURCES)
            if not len(sources):
                print("[{}] Warning! Couldn't find any sources at flag {}!".format(self.name, source))
                self.finished_energy_harvest()
                self.report("D! G F No S.")
                self.go_to_depot()
                return True
            source = sources[0]

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            result = self.creep.pickup(piles[0])
            if result == ERR_NOT_IN_RANGE:
                self.move_to(piles[0])
                self.report("G. Find. E.")
            elif result != OK:
                print("[{}] Unknown result from creep.pickup({}): {}".format(
                    self.name, piles[0], result))
                self.report("???")
            else:
                self.report("G. E.")
            return False

        containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
            (struct.structureType == STRUCTURE_CONTAINER
             or struct.structureType == STRUCTURE_STORAGE)
            and struct.store >= 0
        )})
        if containers.length > 0:
            result = self.creep.withdraw(containers[0], RESOURCE_ENERGY)
            if result == ERR_NOT_IN_RANGE:
                self.move_to(containers[0])
                self.report("G. Find. C.")
            elif result != OK:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, containers[0], result))
                self.report("G. C. ???!")
            else:
                self.report("G. C.")
            return False

        # at this point, there is no energy and no container filled.
        # we should ensure that if there's a big harvester, it hasn't died!
        if (Memory.big_harvesters_placed
            and Memory.big_harvesters_placed[source.id]
            and not Game.creeps[Memory.big_harvesters_placed[source.id]]):
            Memory.meta.clear_now = True
            del Memory.big_harvesters_placed[source.id]
            self.move_to(source)
            self.report("G. Find. S.")
        else:
            # TODO: Hardcoded 2 here!
            # from creep_utils import role_count
            # if role_count("big_harvester") < 2:
            result = self.creep.harvest(source)

            if result == ERR_NOT_IN_RANGE:
                self.move_to(source)
                self.report("G. Find. S.")
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
                self.report("G. W.")
            elif result != OK:
                print("[{}] Unknown result from creep.harvest({}): {}".format(
                    self.name, source, result))
                self.report("G. ???")
            else:
                self.report("G. S.")
        return False

    def finished_energy_harvest(self):
        self.target_mind.untarget(self.creep, hivemind.target_source)

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

    def report(self, current_task):
        if not Memory.meta.quiet:
            self.creep.say(current_task, True)

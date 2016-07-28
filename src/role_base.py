import hivemind
from base import *

__pragma__('noalias', 'name')

PathFinder.use(True)


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

    def _get_path_to(self, pos, same_position_ok=False):
        if not self.memory.path:
            self.memory.path = {}
        if not self.memory.reset_path:
            self.memory.reset_path = {}

        id = pos.x + "_" + pos.y + "_" + pos.roomName

        if self.creep.pos == pos:
            return None

        if self.memory.path[id] and self.memory.reset_path \
                and self.memory.reset_path[id] > Game.time:
            if not same_position_ok:
                if (self.memory.last_pos and
                            self.memory.last_pos.x == self.creep.pos.x and
                            self.memory.last_pos.y == self.creep.pos.y):
                    if not self.memory.same_place_ticks:
                        self.memory.same_place_ticks = 1
                    elif self.memory.same_place_ticks < 3:
                        self.memory.same_place_ticks += 1
                    else:
                        print("[{}] Regenerating path from {} to {}".format(
                            self.name, self.creep.pos, pos
                        ))
                        path = self.creep.pos.findPathTo(pos, {"maxRooms": 4})
                        self.memory.path[id] = Room.serializePath(path)
                        self.memory.same_place_ticks = 0
                        return path
                else:
                    del self.memory.same_place_ticks
                    self.memory.last_pos = self.creep.pos
            try:
                return Room.deserializePath(self.memory.path[id])
            except:
                del self.memory.path[id]

        path = self.creep.pos.findPathTo(pos)
        self.memory.path[id] = Room.serializePath(path)
        self.memory.reset_path[id] = Game.time + 100  # Reset every 100 ticks
        return path

    def move_to(self, target, same_position_ok=False, times_tried=0):
        if target.pos:
            pos = target.pos
        else:
            pos = target
        if self.creep.fatigue <= 0:
            path = self._get_path_to(pos, same_position_ok)
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

                id = target.pos.x + "_" + target.pos.y + "_" + target.pos.roomName
                del self.memory.path[id]
                if not times_tried:
                    times_tried = 0
                if times_tried < 2:
                    self.move_to(target, False, times_tried + 1)
                else:
                    print("[{}] Continually failed to move from {} to {} (path: {})!".format(
                        self.name, self.creep.pos, target.pos, path))
                    self.creep.moveTo(target)

    def harvest_energy(self):
        source = self.target_mind.get_new_target(self.creep, hivemind.target_source)
        if not source:
            print("[{}] Wasn't able to find a source!".format(self.name))
            self.finished_energy_harvest()
            self.creep.say("D! G No S.")
            self.go_to_depot()
            return True

        if source.pos.roomName != self.creep.pos.roomName:
            self.move_to(source)
            self.creep.say("G. F. BR.")
            return False

        if source.color:
            # this is a flag
            sources = source.pos.lookFor(LOOK_SOURCES)
            if not len(sources):
                print("[{}] Warning! Couldn't find any sources at flag {}!".format(self.name, source))
                self.finished_energy_harvest()
                self.creep.say("D! G F No S.")
                self.go_to_depot()
                return True
            source = sources[0]

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            result = self.creep.pickup(piles[0])
            if result == ERR_NOT_IN_RANGE:
                self.move_to(piles[0])
                self.creep.say("G. Find. E.")
            elif result != OK:
                print("[{}] Unknown result from creep.pickup({}): {}".format(
                    self.name, piles[0], result))
                self.creep.say("???")
            else:
                self.creep.say("G. E.")
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
                self.creep.say("G. Find. C.")
            elif result != OK:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, containers[0], result))
                self.creep.say("G. C. ???!")
            else:
                self.creep.say("G. C.")
            return False

        # at this point, there is no energy and no container filled.
        # we should ensure that if there's a big harvester, it hasn't died!
        if (Memory.big_harvesters_placed
            and Memory.big_harvesters_placed[source.id]
            and not Game.creeps[Memory.big_harvesters_placed[source.id]]):
            Memory.meta.clear_now = True
            del Memory.big_harvesters_placed[source.id]
            self.move_to(source)
            self.creep.say("G. Find. S.")
        else:
            # TODO: Hardcoded 2 here!
            # from creep_utils import role_count
            # if role_count("big_harvester") < 2:
            result = self.creep.harvest(source)

            if result == ERR_NOT_IN_RANGE:
                self.move_to(source)
                self.creep.say("G. Find. S.")
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
                self.creep.say("G. W.")
            elif result != OK:
                print("[{}] Unknown result from creep.harvest({}): {}".format(
                    self.name, source, result))
                self.creep.say("G. ???")
            else:
                self.creep.say("G. S.")
        return False

    def finished_energy_harvest(self):
        self.target_mind.untarget(self.creep, hivemind.target_source)

    def go_to_depot(self):
        flag = Game.flags["depot"]
        if flag:
            self.move_to(flag, True)
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
                print("Unknown result from pos.getDirectionTo(): {}".format(dir))
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

from base import *


class RoleBase:
    def __init__(self, creep):
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

    @property
    def name(self):
        return self.creep.name

    def get_path_to(self, target, same_position_ok=False):
        if not self.memory.path:
            self.memory.path = {}

        id = target.id
        if not id:
            print("[{}] Warning! Tried to get_path_to({}) which doesn't have an id!".format(
                self.name, target
            ))
            return None

        if self.creep.pos == target.pos:
            return None

        if self.memory.path[id]:
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
                            self.name, self.creep.pos, target.pos
                        ))
                        path = self.creep.pos.findPathTo(target)
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

        path = self.creep.pos.findPathTo(target)
        self.memory.path[id] = Room.serializePath(path)
        return path

    def move_to(self, target, same_position_ok=False, times_tried=0):
        if self.creep.fatigue <= 0:
            result = self.creep.moveByPath(self.get_path_to(target, same_position_ok))

            if result != OK:
                if result != ERR_NOT_FOUND:
                    print("[{}] Unknown result from creep.moveByPath: {}".format(
                        self.name, result
                    ))

                id = target.id
                if not id:
                    id = target.pos.x + "_" + target.pos.y + "_" + target.pos.roomName
                del self.memory.path[id]
                if not times_tried:
                    times_tried = 0
                if times_tried < 3:
                    self.move_to(target, False, times_tried + 1)
                else:
                    print("[{}] Continually failed to move from {} to {}!".format(self.name, self.creep.pos,
                                                                                  target.pos))

    def get_spread_out_target(self, resource, find_list, limit_by=None, true_limit=False):
        if not self.memory.targets:
            self.memory.targets = {}

        if self.memory.targets[resource]:
            target = Game.getObjectById(self.memory.targets[resource])
            if target:
                # don't return null targets
                return target
            else:
                print("[{}] Retargetting {}!".format(self.name, resource))
                id = self.memory.targets[resource]
                del self.memory.targets[resource]
                del Memory.targets_used[resource][id]

        if not Memory.targets_used:
            Memory.targets_used = {
                resource: {}
            }
        elif not Memory.targets_used[resource]:
            Memory.targets_used[resource] = {}

        list = find_list()
        min_count = 8000
        min_target = None
        min_target_id = None
        for prop in Object.keys(list):
            possible_target = list[prop]
            id = possible_target.id
            if not id:
                print("No ID on possible target {}".format(possible_target))
                id = possible_target.name

            if not Memory.targets_used[resource][id]:
                self.memory.targets[resource] = id
                Memory.targets_used[resource][id] = 1
                return possible_target
            elif limit_by:
                if typeof(limit_by) == "number":
                    limit = limit_by
                else:
                    limit = limit_by(possible_target)
                if Memory.targets_used[resource][id] < limit:
                    min_target_id = id
                    min_target = possible_target
                    break

            if not limit_by or not true_limit:
                if Memory.targets_used[resource][id] < min_count:
                    min_count = Memory.targets_used[resource][id]
                    min_target = possible_target
                    min_target_id = id

        if not min_target:
            return None
        else:
            Memory.targets_used[resource][min_target_id] += 1
            self.memory.targets[resource] = min_target_id
            return min_target

    def get_possible_spread_out_target(self, resource):
        if self.memory.targets and self.memory.targets[resource]:
            target = Game.getObjectById(self.memory.targets[resource])
            if target:
                return target
            else:
                id = self.memory.targets[resource]
                del self.memory.targets[resource]
                del Memory.targets_used[resource][id]

        return None

    def untarget_spread_out_target(self, resource):
        if self.memory.targets:
            id = self.memory.targets[resource]
            if id:
                if (Memory.targets_used and Memory.targets_used[resource] and
                        Memory.targets_used[resource][id]):
                    Memory.targets_used[resource][id] -= 1

                del self.memory.targets[resource]
                del self.memory.path[id]

    def harvest_energy(self):
        # def filter(source):
        #     if not Memory.big_harvesters_placed or not Memory.big_harvesters_placed[source.id]:
        #         return True
        #
        #     harvester = Game.getObjectById(Memory.big_harvesters_placed[source.id])
        #     if harvester:
        #         pos = harvester.pos
        #         energy_piles = pos.look(LOOK_ENERGY)
        #         return energy_piles.length > 0 and energy_piles[0].amount > 20
        #
        #     return True

        def find_list():
            list = self.creep.room.find(FIND_SOURCES)
            # for name in Object.keys(Game.flags):
            #     flag = Game.flags[name]
            #     if flag.memory.harvesting_spot:
            #         list.extend(flag.pos.lookFor(LOOK_SOURCES))
            return list

        source = self.get_spread_out_target("source", find_list)

        if not source:
            print("[{}] Wasn't able to find source {}".format(
                self.name, self.memory.targets["source"]
            ))
            self.finished_energy_harvest()
            self.go_to_depot()
            return

        piles = source.pos.findInRange(FIND_DROPPED_ENERGY, 3)
        if len(piles) > 0:
            result = self.creep.pickup(piles[0])
            if result == ERR_NOT_IN_RANGE:
                self.move_to(piles[0])
            elif result != OK:
                print("[{}] Unknown result from creep.pickup({}): {}".format(
                    self.name, piles[0], result))
            return

        containers = source.pos.findInRange(FIND_STRUCTURES, 3, {"filter": lambda struct: (
            (struct.structureType == STRUCTURE_CONTAINER
             or struct.structureType == STRUCTURE_STORAGE)
            and struct.store >= 0
        )})
        if containers.length > 0:
            result = self.creep.withdraw(containers[0], RESOURCE_ENERGY)
            if result == ERR_NOT_IN_RANGE:
                self.move_to(containers[0])
            elif result != OK:
                print("[{}] Unknown result from creep.withdraw({}): {}".format(
                    self.name, containers[0], result))
            return

        # at this point, there is no energy and no container filled.
        # we should ensure that if there's a big harvester, it hasn't died!
        if (Memory.big_harvesters_placed
            and Memory.big_harvesters_placed[source.id]
            and not Game.creeps[Memory.big_harvesters_placed[source.id]]):
            Memory.needs_clearing = True
            del Memory.big_harvesters_placed[source.id]
            self.move_to(source)
        else:
            # TODO: Hardcoded 2 here!
            from creep_utils import role_count
            if role_count("big_harvester") < 2:
                result = self.creep.harvest(source)

                if result == ERR_NOT_IN_RANGE:
                    self.move_to(source)
                elif result != OK:
                    print("[{}] Unknown result from creep.harvest({}): {}".format(
                        self.name, source, result))
            else:
                self.go_to_depot()

    def finished_energy_harvest(self):
        self.untarget_spread_out_target("source")

    def go_to_depot(self):
        flag = Game.flags["depot"]
        if flag:
            self.move_to(flag, True)
        else:
            self.move_to(Game.spawns[0], True)

    def is_next_block_clear(self, target):
        next_pos = __new__(RoomPosition(target.pos.x, target.pos.y, target.pos.roomName))
        creep_pos = self.creep.pos

        # Apparently, I thought it would be best if we start at the target position, and continue looking for open spaces
        # until we get to the origin position. Thus, if we encounter an obstacle, we use "continue", and if the result is
        # that we've reached the creep position, we return false.
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
                next_pos.x -= 1
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

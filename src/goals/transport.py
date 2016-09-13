from control import pathdef
from role_base import RoleBase
from utilities import movement
from utilities.screeps_constants import *

__pragma__("noalias", "name")
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class TransportPickup(RoleBase):
    def transport(self, pickup, fill):
        self.repair_nearby_roads()
        total_carried_now = _.sum(self.creep.carry)
        if self.memory.filling:
            target = pickup.pos
            if total_carried_now >= self.creep.carryCapacity:
                # TODO: once we have custom path serialization, and we can know how far along on the path we are, use
                # the percentage of how long on the path we are to calculate how much energy we should have to turn back
                self.memory.filling = False
                self.follow_energy_path(pickup, fill)
                return
            if self.pos.roomName != target.roomName or not self.pos.inRangeTo(target, 4):
                self.follow_energy_path(fill, pickup)
                return

            energy = self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, target)[0]
            if energy:
                if self.pos.isNearTo(energy):
                    result = self.creep.pickup(energy)

                    if result == OK:
                        if energy.amount > self.creep.carryCapacity - _.sum(self.creep.carry):
                            self.memory.filling = False
                            self.follow_energy_path(pickup, fill)
                    else:
                        self.log("Unknown result from creep.pickup({}): {}".format(energy, result))
                else:
                    if self.pos.isNearTo(target):
                        self.basic_move_to(energy)
                    else:
                        self.follow_energy_path(fill, pickup)
                return

            containers = self.room.find_in_range(FIND_STRUCTURES, 1, target)
            container = _.find(containers, lambda s: s.structureType == STRUCTURE_CONTAINER
                                                     or s.structureType == STRUCTURE_STORAGE)
            if container:
                if self.pos.isNearTo(container):
                    if _.sum(container.store) > container.store.energy:
                        for mtype in Object.keys(container.store):
                            amount = container.store[mtype]
                            if amount > 0 and mtype != RESOURCE_ENERGY: # Prioritize minerals over energy
                                break
                        else:
                            return
                    else:
                        mtype = RESOURCE_ENERGY
                        amount = container.store[RESOURCE_ENERGY]

                    result = self.creep.withdraw(container, mtype)
                    if result != OK:
                        self.log("Unknown result from creep.withdraw({}, {}): {}"
                                 .format(container, mtype, result))
                        return

                    if amount > self.creep.carryCapacity - _.sum(self.creep.carry):
                        self.memory.filling = False
                        self.follow_energy_path(pickup, fill)
                else:
                    if self.pos.isNearTo(target):
                        self.creep.move(pathdef.direction_to(self.pos, container))
                    else:
                        self.follow_energy_path(fill, pickup)
                return
            # No energy, let's just wait
            if not _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, target),
                          lambda c: c.getActiveBodyparts(WORK) >= 5):
                if _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                          lambda c: c.getActiveBodyparts(WORK) >= 5):
                    if Game.time % 5 == 0:
                        self.follow_energy_path(pickup, fill)
                    else:
                        self.follow_energy_path(fill, pickup)
                elif _.sum(self.creep.carry) > self.creep.carryCapacity * 0.5:
                    self.memory.filling = False
                    self.follow_energy_path(pickup, fill)
        else:
            if total_carried_now > self.creep.carry.energy and self.home.room.storage:
                fill = self.home.room.storage
            elif _.sum(self.creep.carry) <= 0:
                if self.creep.ticksToLive < 2.2 * self.path_length(fill, pickup):
                    self.creep.suicide()
                    return
                self.creep.memory.filling = True
                self.follow_energy_path(fill, pickup)
                return

            target = fill
            if target.pos:
                target = target.pos
            if fill.structureType == STRUCTURE_LINK and self.pos.roomName == target.roomName:
                self.room.links.register_target_deposit(fill, self, self.creep.carry.energy,
                                                        self.creep.pos.getRangeTo(target))

            if self.pos.roomName != target.roomName or not self.pos.isNearTo(target):
                self.follow_energy_path(pickup, fill)
                return

            is_link = fill.structureType == STRUCTURE_LINK or fill.structureType == STRUCTURE_SPAWN
            for mtype in Object.keys(self.creep.carry):
                amount = self.creep.carry[mtype]
                if amount > 0 and (not is_link or mtype == RESOURCE_ENERGY):
                    result = self.creep.transfer(fill, mtype)
                    if result != OK and result != ERR_FULL:
                        self.log("Unknown result from transport-creep.transfer({}, {}): {}".format(fill, mtype, result))
                        amount = 0
                    break
            else:
                if self.creep.ticksToLive < 2.2 * self.path_length(fill, pickup):
                    self.creep.suicide()
                    return
                self.memory.filling = True
                self.follow_energy_path(fill, pickup)
                return

            if is_link:
                empty = fill.energyCapacity - fill.energy
            else:
                empty = fill.storeCapacity - _.sum(fill.store)

            if min(amount, empty) >= _.sum(self.creep.carry):
                # self.memory.filling = True
                self.follow_energy_path(fill, pickup)

    def path_length(self, origin, target):
        if origin.pos: origin = origin.pos
        if target.pos: target = target.pos

        path = self.room.honey.find_path(origin, target)
        return len(path)

    def follow_energy_path(self, origin, target):
        # over_debug = self.name in ('30d6' ,'3b5a', '4387')
        if origin.pos: origin = origin.pos
        if target.pos: target = target.pos
        if self.creep.fatigue > 0:
            return
        # if over_debug:
        #     self.log("Following path from {} to {}!".format(origin, target))
        path = self.room.honey.find_path(origin, target, {'current_room': self.pos.roomName})
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            if self.pos.isNearTo(target):
                self.basic_move_to(target)
                return
            if not self.memory.next_ppos or self.memory.off_path_for > 100:
                self.memory.off_path_for = 0  # Recalculate next_ppos if we're off path for a long time
                all_positions = self.room.honey.list_of_room_positions_in_path(origin, target)
                closest = None
                closest_distance = Infinity
                for pos in all_positions:
                    if movement.distance_room_pos(pos, origin) < 3 or movement.distance_room_pos(pos, target) < 3:
                        room = self.hive.get_room(pos.roomName)
                        if room and not movement.is_block_clear(room, pos.x, pos.y):
                            continue  # Don't try and target where the miner is right now!
                    distance = movement.distance_room_pos(self.pos, pos)
                    if pos.roomName != self.pos.roomName or pos.x < 2 or pos.x > 48 or pos.y < 2 or pos.y > 48:
                        distance += 10
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = pos
                if not closest:
                    self.log("WARNING: Couldn't find closest position to return too! all positions: {}!".format(
                        all_positions))
                    return
                self.memory.next_ppos = closest
            mtarget = self.memory.next_ppos
            new_target = __new__(RoomPosition(mtarget.x, mtarget.y, mtarget.roomName))
            if self.pos.isEqualTo(new_target):
                del self.memory.next_ppos
                if not self.memory.tried_new_next_ppos:
                    self.memory.tried_new_next_ppos = True
                else:
                    del self.memory.tried_new_next_ppos
                    # the path is incorrect!
                    self.log("WARNING: Path from {} to {} found to be cached incorrectly - it should contain {}, but"
                             " it doesn't.".format(origin, target, new_target))
                    self.log("Path (tbd) retrieved from HoneyTrails with options (current_room: {}):\n{}".format(
                        self.pos.roomName, JSON.stringify(path, 0, 4)))
                    self.room.honey.clear_cached_path(origin, target)
            else:
                del self.memory.tried_new_next_ppos
            self.creep.moveTo(new_target)
            if not self.memory.off_path_for:
                self.memory.off_path_for = 1
            else:
                self.memory.off_path_for += 1
                # if self.memory.off_path_for > 10:
                #     self.log("Lost the path from {} to {}! Pos: {}, path: \n{}".format(
                #         origin, target, self.pos, JSON.stringify(path)))
        elif result != OK:
            self.log("Unknown result from follow_energy_path: {}".format(result))
        else:
            del self.memory.tried_new_next_ppos
            if self.memory.off_path_for:
                self.memory.on_path_for = 1
                del self.memory.off_path_for
            elif self.memory.on_path_for:
                self.memory.on_path_for += 1
                if self.memory.on_path_for >= 2:
                    del self.memory.next_ppos
                    del self.memory.on_path_for

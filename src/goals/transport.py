from control import pathdef
from role_base import RoleBase
from utilities import movement
from utilities.screeps_constants import *

__pragma__("noalias", "name")


class TransportPickup(RoleBase):
    def transport(self, pickup, fill):
        self.repair_nearby_roads()
        total_carried_now = _.sum(self.creep.carry)
        if self.memory.pickup:
            target = pickup
            if target.pos:
                target = target.pos
            if total_carried_now >= self.creep.carryCapacity:
                # TODO: once we have custom path serialization, and we can know how far along on the path we are, use
                # the percentage of how long on the path we are to calculate how much energy we should have to turn back
                self.memory.pickup = False
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
                            self.memory.pickup = False
                            self.follow_energy_path(pickup, fill)
                    else:
                        self.log("Unknown result from creep.pickup({}): {}".format(energy, result))
                else:
                    if self.pos.isNearTo(target):
                        self.creep.move(pathdef.direction_to(self.pos, energy))
                    else:
                        self.follow_energy_path(fill, pickup)
                return

            containers = self.room.find_in_range(FIND_STRUCTURES, 1, target)
            container = _.find(containers, {'structureType': STRUCTURE_CONTAINER})
            if container:
                if self.pos.isNearTo(container):
                    for mtype in Object.keys(container.store):
                        amount = container.store[mtype]
                        if amount > 0:
                            result = self.creep.withdraw(container, mtype)
                            if result != OK:
                                self.log("Unknown result from creep.withdraw({}, {}): {}"
                                         .format(container, mtype, result))
                                amount = 0
                            break
                    else:
                        return
                    if amount > self.creep.carryCapacity - _.sum(self.creep.carry):
                        self.memory.pickup = False
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
                if Game.time % 5 == 0:
                    self.follow_energy_path(pickup, fill)
                else:
                    self.follow_energy_path(fill, pickup)
        else:
            if total_carried_now > self.creep.carry.energy and self.creep.home.room.storage:
                fill = self.creep.home.room.storage
            elif self.creep.carry.energy <= 0:
                self.creep.pickup = True
                self.follow_energy_path(fill, pickup)

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
                self.memory.pickup = True
                self.follow_energy_path(fill, pickup)
                return

            if is_link:
                empty = fill.energyCapacity - fill.energy
            else:
                empty = fill.storeCapacity - _.sum(fill.store)

            if min(amount, empty) >= _.sum(self.creep.carry):
                # self.memory.pickup = True
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
        path = self.room.honey.find_path(origin, target)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND:
            # if over_debug:
            #     self.log("Not on path!")
            first = __new__(RoomPosition(path[2].x, path[2].y, origin.roomName))
            # TODO: Why doesn't transcrypt let this work? this is like one of the most awesome python things...
            # last = __new__(RoomPosition(path[-2].x, path[-2].y, target.roomName))
            last = __new__(RoomPosition(path[path.length - 4].x, path[path.length - 4].y, target.roomName))
            if movement.distance_squared_room_pos(self.pos, first) > \
                    movement.distance_squared_room_pos(self.pos, last):
                new_target = last
            else:
                new_target = first
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
            del self.memory.off_path_for
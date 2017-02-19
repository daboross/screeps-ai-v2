from constants import role_hauler, role_miner, role_recycling
from creeps.base import RoleBase
from empire import honey
from jstools.screeps import *
from utilities import movement

__pragma__("noalias", "name")
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


# TODO: abstract path movement out of TransportPickup into a higher class.
class TransportPickup(RoleBase):
    def transport(self, pickup, fill, paved):
        total_carried_now = self.carry_sum()
        if self.memory.filling:
            target = pickup.pos
            if not self.creep.carryCapacity:
                if self.creep.hits < self.creep.hitsMax and self.home.defense.healing_capable():
                    if paved:
                        self.follow_energy_path(pickup, fill, pickup)
                    else:
                        self.follow_energy_path(pickup, fill)
                else:
                    self.log("All carry parts dead, committing suicide.")
                    self.creep.suicide()
                return
            if total_carried_now >= self.creep.carryCapacity:
                # TODO: once we have custom path serialization, and we can know how far along on the path we are, use
                # the percentage of how long on the path we are to calculate how much energy we should have to turn back
                self.memory.filling = False
                if paved:
                    self.repair_nearby_roads()
                    self.follow_energy_path(pickup, fill, pickup)
                else:
                    self.follow_energy_path(pickup, fill)
                return
            if self.pos.roomName != target.roomName or not self.pos.inRangeTo(target, 4):
                if total_carried_now:
                    self.repair_nearby_roads()
                self.follow_energy_path(fill, pickup, pickup)
                return
            piles = self.room.look_for_in_area_around(LOOK_RESOURCES, target, 1)
            if len(piles):
                if len(piles) > 1:
                    best = None
                    best_amount = 0
                    for pile in piles:
                        amount = pile.resource.amount
                        if pile.resource.picked_up:
                            amount -= 500
                        if amount > best_amount:
                            best_amount = amount
                            best = pile.resource
                    energy = best
                else:
                    energy = piles[0].resource
                if self.pos.isNearTo(energy):
                    ok_to_pick_up = True
                    if energy.picked_up:
                        other_creep = energy.picked_up
                        if other_creep.carryCapacity - other_creep.carry.energy <= self.creep.carryCapacity - self.creep.carry.energy:
                            ok_to_pick_up = False
                        else:
                            other_creep.cancelOrder('pickup')

                    if ok_to_pick_up:
                        result = self.creep.pickup(energy)

                        if result == OK:
                            self.creep.picked_up = energy
                            energy.picked_up = self.creep
                            if energy.amount > self.creep.carryCapacity - total_carried_now:
                                self.memory.filling = False
                                if paved:
                                    self.follow_energy_path(pickup, fill, pickup)
                                else:
                                    self.follow_energy_path(pickup, fill)
                            elif Game.time % 6 == 1 and self.creep.ticksToLive < 10 + self.path_length(fill, pickup):
                                self.memory.filling = False
                                self.follow_energy_path(fill, pickup)
                            return
                        else:
                            self.log("Unknown result from creep.pickup({}): {}".format(energy, result))
                else:
                    if self.pos.isNearTo(target):
                        self.basic_move_to(energy)
                    else:
                        self.follow_energy_path(fill, pickup)
                    return

            containers = self.room.look_for_in_area_around(LOOK_STRUCTURES, target, 1)
            container = _.find(containers, lambda s: s.structure.structureType == STRUCTURE_CONTAINER
                                                     or s.structure.structureType == STRUCTURE_STORAGE)
            if container:
                container = container.structure
                if self.pos.isNearTo(container):
                    mtype = _.findKey(container.store)
                    amount = container.store[mtype]

                    result = self.creep.withdraw(container, mtype)
                    if result != OK:
                        self.log("Unknown result from creep.withdraw({}, {}): {}"
                                 .format(container, mtype, result))
                        return

                    if amount > self.creep.carryCapacity - total_carried_now:
                        self.memory.filling = False
                        if paved:
                            self.follow_energy_path(pickup, fill, pickup)
                        else:
                            self.follow_energy_path(pickup, fill)
                else:
                    if self.pos.isNearTo(target):
                        self.creep.move(movement.diff_as_direction(self.pos, container))
                    else:
                        self.follow_energy_path(fill, pickup)
                return
            # No energy, let's just wait
            if not _.find(self.room.look_for_in_area_around(LOOK_CREEPS, target, 1),
                          lambda o: o.creep.my and o.creep.memory.role == role_miner):
                if total_carried_now > self.creep.carryCapacity * 0.5:
                    self.memory.filling = False
                    if paved:
                        self.follow_energy_path(pickup, fill, pickup)
                    else:
                        self.follow_energy_path(pickup, fill)
                    return
        else:
            # don't use up *all* the energy doing this
            if total_carried_now and total_carried_now + 50 >= self.creep.carryCapacity / 2:
                self.repair_nearby_roads()
            if total_carried_now > self.creep.carry.energy and self.home.room.storage:
                fill = self.home.room.storage
            elif total_carried_now <= 0:
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
                                                        self.pos.getRangeTo(target))

            if self.pos.roomName != target.roomName or not self.pos.isNearTo(target):
                if paved:
                    self.follow_energy_path(pickup, fill, pickup)
                else:
                    self.follow_energy_path(pickup, fill)
                return

            energy_only = fill.structureType == STRUCTURE_LINK or fill.structureType == STRUCTURE_SPAWN
            if energy_only:
                resource = RESOURCE_ENERGY
            else:
                resource = _.findKey(self.creep.carry)
            amount = self.creep.carry[resource]
            if resource and amount:
                result = self.creep.transfer(fill, resource)
                if result != OK and result != ERR_FULL:
                    self.log("Unknown result from transport-creep.transfer({}, {}): {}".format(fill, resource, result))
                    amount = 0
            else:
                if self.creep.ticksToLive < 2.2 * self.path_length(fill, pickup):
                    self.creep.suicide()
                    return
                self.memory.filling = True
                self.follow_energy_path(fill, pickup)
                return

            if energy_only:
                empty = fill.energyCapacity - fill.energy
            else:
                empty = fill.storeCapacity - _.sum(fill.store)

            if min(amount, empty) >= total_carried_now:
                # self.memory.filling = True
                self.follow_energy_path(fill, pickup)
                return

    def path_length(self, origin, target):
        if origin.pos:
            origin = origin.pos
        if target.pos:
            target = target.pos

        return self.hive.honey.find_path_length(origin, target)

    def follow_energy_path(self, origin, target, mine=None):
        if origin.pos:
            origin = origin.pos
        if target.pos:
            target = target.pos
        if self.creep.fatigue > 0:
            return
        if origin.isNearTo(target):
            if self.pos.roomName == target.roomName:
                self.move_to(target)
                return
            else:
                origin = self.home.spawn.pos

        opts = {
            'current_room': self.pos.roomName,
            'paved_for': mine,
        }
        path = self.hive.honey.find_serialized_path(origin, target, opts)
        # TODO: manually check the next position, and if it's a creep check what direction it's going
        result = self.creep.moveByPath(path)
        if result == ERR_NOT_FOUND or result == ERR_NO_PATH:
            if self.pos.isNearTo(target):
                self.basic_move_to(target)
                return
            if not self.memory.next_ppos or self.memory.off_path_for > 10 or movement.chebyshev_distance_room_pos(
                    self, self.memory.next_ppos) > CREEP_LIFE_TIME:
                self.memory.off_path_for = 0  # Recalculate next_ppos if we're off path for a long time
                all_positions = self.hive.honey.list_of_room_positions_in_path(origin, target, opts)
                closest = None
                closest_distance = Infinity
                for index, pos in enumerate(all_positions):
                    if movement.chebyshev_distance_room_pos(pos, origin) < 3 \
                            or movement.chebyshev_distance_room_pos(pos, target) < 3:
                        room = self.hive.get_room(pos.roomName)
                        if room and not movement.is_block_clear(room, pos.x, pos.y):
                            continue  # Don't try and target where the miner is right now!
                    # subtract how far we are on the path!
                    # NOTE: 0.7 is used in building._repath_roads_for and should be changed there if changed here.
                    distance = movement.chebyshev_distance_room_pos(self.pos, pos) - index * 0.7
                    if pos.roomName != self.pos.roomName or pos.x < 2 or pos.x > 48 or pos.y < 2 or pos.y > 48:
                        distance += 10
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = pos
                if not closest or closest_distance >= CREEP_LIFE_TIME:
                    portals = _.filter(self.room.find(FIND_STRUCTURES), {'structureType': STRUCTURE_PORTAL})
                    if len(portals) and movement.chebyshev_distance_room_pos(self.pos, portals[0].pos) \
                            + movement.chebyshev_distance_room_pos(movement.center_pos(portals[0].destination),
                                                                   target) \
                            < movement.chebyshev_distance_room_pos(self.pos, target):
                        self.memory.next_ppos = self.pos.findClosestByRange(portals).pos
                    else:
                        self.log("WARNING: Transport creep off path, with no positions to return to. I'm at {}, going"
                                 " from {} to {}. All positions: {}!"
                                 .format(self.pos, origin, target, all_positions))
                        if mine and self.home.mining.is_mine_linked(mine):
                            self.log("I'm a hauler for a linked mine! Suiciding.")
                            self.memory.role = role_recycling
                        if not len(all_positions):
                            if Game.time % 20 == 10:
                                honey.clear_cached_path(origin, target)
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
                    self.log("Path (tbd) retrieved from HoneyTrails with options ({}):\n{}".format(
                        opts, JSON.stringify(path, 0, 4)))
                    honey.clear_cached_path(origin, target, opts)
            elif self.pos.isNearTo(new_target):
                self.basic_move_to(new_target)
                return
            else:
                del self.memory.tried_new_next_ppos
            self.move_to(new_target)
            if not self.memory.off_path_for:
                self.memory.off_path_for = 1
            else:
                self.memory.off_path_for += 1
        elif result != OK:
            self.log("Unknown result from follow_energy_path: {}. Going from {} to {} (path {}, in {})"
                     .format(result, origin, target, path, self.pos.roomName))
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

            serialized_pos = self.pos.x | (self.pos.y << 6)
            if self.memory.last_pos == serialized_pos:
                if 'standstill_for' in self.memory:
                    self.memory.standstill_for += 1
                else:
                    self.memory.standstill_for = 1
                if self.memory.standstill_for % 10 == 5 and \
                        (not self.memory.filling
                         or not _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                                       lambda c: c.memory.role != role_hauler and c.memory.role != role_miner)):
                    del self.memory.next_ppos
                    found_mine = False
                    for pos in self.hive.honey.find_path(origin, target, opts):
                        if pos.x == self.pos.x and pos.y == self.pos.y:
                            found_mine = True
                        elif found_mine:
                            if movement.is_block_clear(self.room, pos.x, pos.y):
                                self.memory.next_ppos = {"x": pos.x, "y": pos.y, "roomName": self.pos.roomName}
                                self.move_to(__new__(RoomPosition(pos.x, pos.y, self.pos.roomName)))
                                break
            elif not self.creep.fatigue:
                self.memory.last_pos = serialized_pos
                del self.memory.standstill_for

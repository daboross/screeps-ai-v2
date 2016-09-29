import speech
from constants import recycle_time, role_recycling, role_upgrader, PYFIND_REPAIRABLE_ROADS, PYFIND_BUILDABLE_ROADS, \
    role_builder
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def split_pos_str(pos_str):
    pos_split = pos_str.split(",")
    x = int(pos_split[0])
    y = int(pos_split[1])
    return x, y


class Upgrader(RoleBase):
    def run(self):
        link = self.get_dedicated_upgrading_link()
        if link:
            return self.run_dedicated_upgrading(link)
        else:
            return self.run_individual_upgrading()

    def get_dedicated_upgrading_link(self):
        link_id = self.home.get_cached_property("upgrader_link_id")
        if link_id:
            if link_id == -1:
                return None
            else:
                link = Game.getObjectById(link_id)
                if link:
                    return link
        links = _.filter(self.home.find_in_range(FIND_MY_STRUCTURES, 4, self.home.room.controller.pos),
                         lambda s: s.structureType == STRUCTURE_STORAGE or s.structureType == STRUCTURE_LINK)
        if len(links):
            if len(links) > 1:
                link = _.min(links, lambda l: movement.distance_squared_room_pos(l, self.home.room.controller))
                link_id = link.id
            else:
                link = links[0]
                link_id = link.id
        else:
            link = None
            link_id = -1
        self.home.store_cached_property("upgrader_link_id", link_id, 100)
        return link

    def run_dedicated_upgrading(self, link):
        controller = self.home.room.controller

        if not self.home.upgrading_paused() or self.creep.room.controller.ticksToDowngrade < 5000:
            self.upgrade(controller)
        self.harvest_from(link)

        available_positions = self.memory.controller_positions
        if not available_positions or (Game.time + self.creep.ticksToLive) % 25:
            available_positions = []
            for x in range(link.pos.x - 1, link.pos.x + 2):
                for y in range(link.pos.y - 1, link.pos.y + 2):
                    if x != link.pos.x or y != link.pos.y:
                        if abs(x - controller.pos.x) <= 3 and abs(y - controller.pos.y) <= 3 \
                                and Game.map.getTerrainAt(x, y, self.pos.roomName) != 'wall':
                            available_positions.append("{},{}".format(x, y))
            self.memory.controller_positions = available_positions

        if self.memory.get_near_controller:
            if self.creep.carry.energy > self.creep.carryCapacity * 0.5:
                if self.pos.isNearTo(link):
                    if not self.basic_move_to(controller):
                        self.move_to(controller)
                return
            else:
                del self.memory.get_near_controller

        if not self.pos.inRangeTo(controller, 3) or not self.pos.isNearTo(link):
            a_creep_with_energy = None
            for pos in available_positions:
                x, y = split_pos_str(pos)
                that_creep = _.find(self.home.find_at(FIND_MY_CREEPS, x, y))
                if not that_creep:
                    self.move_to(__new__(RoomPosition(x, y, self.home.room_name)))
                    break
                elif that_creep.carry.energy >= that_creep.carryCapacity * 0.5 \
                        and that_creep.memory.role == role_upgrader and not that_creep.memory.get_near_controller:
                    a_creep_with_energy = that_creep
            else:
                if self.creep.carry.energy < self.creep.carryCapacity * 0.25:
                    closest_full = _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                                          lambda c: c.memory.role == role_upgrader
                                                    and c.carry.energy >= c.carryCapacity * 0.75
                                                    and c.pos.inRangeTo(link.pos, 1))
                    if closest_full:
                        closest_full.move(closest_full.pos.getDirectionTo(self.pos))
                        self.creep.move(self.pos.getDirectionTo(closest_full.pos))
                    elif a_creep_with_energy:
                        a_creep_with_energy.memory.get_near_controller = True
                        self.creep.move(self.pos.getDirectionTo(link.pos))
                elif not self.pos.inRangeTo(controller, 3):
                    self.move_to(controller)
            return

        if not _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, self.pos),
                      lambda c: c.memory.role != role_upgrader):
            return  # No need to shuffle around if there's no one to move around for

        if len(available_positions):
            target_x, target_y = split_pos_str(available_positions[(Game.time + 2) % len(available_positions)])
            self.basic_move_to({'x': target_x, 'y': target_y})

    def upgrade(self, controller):
        if self.creep.carry.energy <= 0:
            return
        result = self.creep.upgradeController(controller)
        if result != OK and result != ERR_NOT_IN_RANGE:
            self.log("Unknown result from creep.upgradeController({}): {}", self.creep.room.controller, result)

    def harvest_from(self, link):
        if self.creep.ticksToLive < 20 or self.creep.carry.energy >= self.creep.carryCapacity:
            return
        energy = _.find(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, self.pos), {'resourceType': RESOURCE_ENERGY})
        if energy:
            self.creep.pickup(energy)
            return
        self.home.links.register_target_withdraw(link, self, self.creep.carryCapacity - self.creep.carry.energy,
                                                 self.creep.pos.getRangeTo(link))
        if link.energy <= 0 or not self.pos.isNearTo(link):
            return
        result = self.creep.withdraw(link, RESOURCE_ENERGY)
        if result != OK:
            self.log("Unknown result from creep.withdraw({}): {}", link, result)

    def should_pickup(self, resource_type=None):
        return not self.get_dedicated_upgrading_link() and RoleBase.should_pickup(self, resource_type) \
               and not self.home.upgrading_paused()

    def run_individual_upgrading(self):
        if self.creep.ticksToLive < recycle_time and self.home.spawn:
            self.memory.role = role_recycling
            self.memory.last_role = role_upgrader
            return False
        if self.home.overprioritize_building() and self.home.room.controller.ticksToDowngrade >= 500:
            self.memory.role = role_builder
            return False
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
            self.finished_energy_harvest()
        elif not self.memory.filling and self.creep.carry.energy <= 0:
            self.memory.filling = True
            self.finished_energy_harvest()

        if not self.home.room.controller.my or (self.home.upgrading_paused()
                                                and self.creep.room.controller.ticksToDowngrade >= 5000):
            self.report(speech.upgrading_upgrading_paused)
            if not self.empty_to_storage():
                self.go_to_depot()
            return False

        if self.memory.filling:
            self.build_swamp_roads()
            self.harvest_energy()
        else:
            target = self.home.room.controller
            if not self.creep.pos.inRangeTo(target.pos, 3):
                self.move_to(target)
                self.report(speech.upgrading_moving_to_controller)
                return False

            result = self.creep.upgradeController(target)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                if not self.memory.filling:
                    self.memory.filling = True
                    return True
            elif result == OK:
                holding = _.sum(self.creep.carry)
                self.force_basic_move_to(target, lambda c: _.sum(c.carry) < holding)
                self.report(speech.upgrading_ok)
            else:
                self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.memory.filling = True
                else:
                    self.go_to_depot()
                    self.report(speech.upgrading_unknown_result)

    def build_swamp_roads(self):
        if not self.home.room.storage and self.creep.carry.energy > 0:
            repair = _.find(self.room.find_in_range(PYFIND_REPAIRABLE_ROADS, 2, self.creep.pos),
                            lambda r: Game.map.getTerrainAt(r.pos.x, r.pos.y, r.pos.roomName) == 'swamp')
            if repair:
                result = self.creep.repair(repair)
                if result != OK:
                    self.log("Unknown result from passingby-road-repair on {}: {}".format(repair[0], result))
            else:
                build = _.find(self.room.find_in_range(PYFIND_BUILDABLE_ROADS, 2, self.creep.pos),
                               lambda r: Game.map.getTerrainAt(r.pos.x, r.pos.y, r.pos.roomName) == 'swamp')
                if build:
                    result = self.creep.build(build)
                    if result != OK:
                        self.log("Unknown result from passingby-road-build on {}: {}".format(build[0], result))

    def _calculate_time_to_replace(self):
        path = self.hive.honey.find_path(self.home.spawn, self.home.room.controller)
        # No leeway because we're assuming that we A: won't need to go all the way to the controller and B: the road
        # will be somewhat paved
        return len(path) * 2 + _.size(self.creep.body) * 3


profiling.profile_whitelist(Upgrader, ["run"])

import speech
from constants import recycle_time, role_recycling, role_upgrader, target_closest_energy_site, creep_base_full_upgrader
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


def split_pos_str(pos_str):
    pos_split = pos_str.split(",")
    x = int(pos_split[0])
    y = int(pos_split[1])
    return x, y


class Upgrader(RoleBase):
    def run(self):
        link = self.target_mind.get_new_target(self, target_closest_energy_site)
        if movement.distance_squared_room_pos(link, self.home.room.controller) <= 4 * 4:
            return self.run_dedicated_upgrading(link)
        else:
            return self.run_individual_upgrading()

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
                that_creep = _.find(self.home.room.lookForAt(LOOK_CREEPS, x, y))
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
        self.home.links.register_target_withdraw(link, self, self.creep.carryCapacity - self.creep.carry.energy,
                                                 self.creep.pos.getRangeTo(link))
        if self.creep.carry.energy >= self.creep.carryCapacity \
                or link.energy <= 0 or not self.pos.isNearTo(link):
            return
        result = self.creep.withdraw(link, RESOURCE_ENERGY)
        if result != OK:
            self.log("Unknown result from creep.withdraw({}): {}", link, result)

    def run_individual_upgrading(self):
        del self.memory.emptying
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_upgrader
            return False
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.finished_energy_harvest()

        if not self.home.room.controller.my or (self.home.upgrading_paused()
                                                and self.creep.room.controller.ticksToDowngrade >= 5000):
            self.report(speech.upgrading_upgrading_paused)
            self.memory.emptying = True  # flag for spawn fillers to not refill me.
            if not self.empty_to_storage():
                self.go_to_depot()
            return False

        if self.memory.harvesting:
            self.memory.stationary = False
            if self.harvest_energy():
                return True

        target = self.home.room.controller
        if not self.creep.pos.inRangeTo(target.pos, 3):
            if self.memory.harvesting:
                # Let's upgrade if we're in range while we're harvesting, but otherwise we can just harvest.
                return False
            self.move_to(target)
            self.memory.stationary = False
            self.report(speech.upgrading_moving_to_controller)
            return False

        self.memory.stationary = True
        result = self.creep.upgradeController(target)
        if result == ERR_NOT_ENOUGH_RESOURCES:
            if not self.memory.harvesting:
                self.memory.harvesting = True
                return True
        elif result == OK:
            # If we're a "full upgrader", with carry capacity just 50, let's keep close to the link we're gathering
            # from. Otherwise, move towards the controller to leave room for other upgraders
            if self.creep.carryCapacity > 100:
                if not self.memory.harvesting:
                    self.basic_move_to(target)
            else:
                if self.memory.base == creep_base_full_upgrader and not self.memory.harvesting and \
                                self.creep.carry.energy < self.creep.carryCapacity:
                    self.harvest_energy()
            self.report(speech.upgrading_ok)
        else:
            self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

            if self.creep.carry.energy < self.creep.carryCapacity:
                self.memory.harvesting = True
            else:
                self.go_to_depot()
                self.report(speech.upgrading_unknown_result)

        return False


profiling.profile_whitelist(Upgrader, ["run"])

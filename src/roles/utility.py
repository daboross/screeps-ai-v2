import speach
from role_base import RoleBase
from utils.screeps_constants import *


class LinkManager(RoleBase):
    def run(self):
        if self.run_creep():
            if self.run_creep():
                if self.run_creep():
                    print("[{}] Link manager tried to rerun three times!".format(self.name))
        self.run_links()
        return False

    def run_creep(self):
        storage = self.creep.room.storage
        if not storage:
            print("[{}] Link manager can't find storage in {}!".format(self.name, self.creep.room.name))
            self.go_to_depot()
            self.report(speach.link_manager_something_not_found)
            return False

        if self.memory.gathering_from_link and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.gathering_from_link = False

        if not self.memory.gathering_from_link and self.creep.carry.energy <= 0:
            self.memory.gathering_from_link = True

        if self.memory.gathering_from_link:
            link = None
            if self.memory.target_link:
                link = Game.getObjectById(self.memory.target_link)

            if not link:
                link = self.creep.room.storage.pos.findClosestByRange(FIND_STRUCTURES, {
                    "filter": {"structureType": STRUCTURE_LINK}
                })
                if not link:
                    if self.creep.carry.energy > 0:
                        self.memory.gathering_from_link = False
                        return True
                    print("[{}] Link-storage manager can't find link in {}!".format(self.name, self.creep.room.name))
                    self.go_to_depot()
                    self.report(speach.link_manager_something_not_found)
                    return False
                self.memory.target_link = link.id

            if not self.creep.pos.isNearTo(link.pos):
                self.move_to(link)
                self.report(speach.link_manager_moving)
                return False

            if link.energy <= 0:
                if self.creep.carry.energy > 0:
                    self.memory.gathering_from_link = False
                    return True
                return False

            self.memory.stationary = True

            result = self.creep.withdraw(link, RESOURCE_ENERGY)

            if result == OK:
                self.report(speach.link_manager_ok)
            elif result == ERR_FULL:
                self.memory.gathering_from_link = False
            else:
                print("[{}] Unknown result from link-manager-creep.withdraw({}): {}".format(
                    self.name, link, result
                ))
                self.report(speach.link_manager_unknown_result)
        else:
            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage)
                self.report(speach.link_manager_moving)
                return False

            self.memory.stationary = True

            result = self.creep.transfer(storage, RESOURCE_ENERGY)
            if result == OK:
                self.report(speach.link_manager_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.gathering_from_link = True
                return True
            elif result == ERR_FULL:
                print("[{}] Storage in room {} full!".format(self.name, storage.room))
                self.report(speach.link_manager_storage_full)
            else:
                print("[{}] Unknown result from link-manager-creep.transfer({}): {}".format(
                    self.name, storage, result
                ))
                self.report(speach.link_manager_unknown_result)

        return False

    def run_links(self):
        if not self.memory.target_link:
            return
        my_link = Game.getObjectById(self.memory.target_link)
        if not my_link or my_link.energy >= my_link.energyCapacity:
            return
        for link in self.creep.room.find(FIND_STRUCTURES, {"filter": {"structureType": STRUCTURE_LINK}}):
            # TODO: is a minimum like this ever helpful?
            if link.id != self.memory.gathering_from_link and link.cooldown <= 0 \
                    and (link.energy > link.energyCapacity / 4 or (link.energy > 0 and my_link.energy <= 0)):
                link.transferEnergy(my_link)

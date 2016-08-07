from role_base import RoleBase
from utilities.screeps_constants import *


class RoleDefender(RoleBase):
    def run(self):
        target = Game.getObjectById(self.memory.attack_target)

        if target is None and Memory.hostiles and len(Memory.hostiles):
            remove = []
            for target_id in Memory.hostiles:
                target = Game.getObjectById(target_id)
                if target:
                    break
                else:
                    remove.append(target_id)
                    del Memory.hostile_last_rooms[target_id]
            _.remove(Memory.hostiles, lambda x: x in remove)

        if target:
            self.move_to(target)
        else:
            self.recycle_me()

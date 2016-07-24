from base import *
from role_base import RoleBase

__pragma__('noalias', 'name')


class BigHarvester(RoleBase):
    def run(self):
        source = self.get_spread_out_target("big_source", lambda: self.creep.room.find(FIND_SOURCES))
        if not source:
            print("[{}] No sources found.".format(self.name))

        result = self.creep.harvest(source)
        if result == ERR_NOT_IN_RANGE:
            self.move_to(source)
        elif result == OK:
            if Memory.big_harvesters_placed:
                Memory.big_harvesters_placed[source.id] = self.name
            else:
                Memory.big_harvesters_placed = {
                    source.id: self.name
                }
        else:
            print("[{}] Unknown result from creep.harvest({}): {}".format(
                self.name, source, result
            ))

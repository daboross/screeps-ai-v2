import hivemind
import profiling
from base import *
from role_base import RoleBase

__pragma__('noalias', 'name')

_MOVE_OPTIONS = {"maxRooms": 1, "ignoreCreeps": True}


class BigHarvester(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self.creep, hivemind.target_big_source)

        if not source:
            print("[{}] No big sources found.".format(self.name))
            return

        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source, False, _MOVE_OPTIONS)
            self.report("HB. F. S.")
            return False

        result = self.creep.harvest(source)
        if result == OK:
            if Memory.big_harvesters_placed:
                Memory.big_harvesters_placed[source.id] = self.name
            else:
                Memory.big_harvesters_placed = {
                    source.id: self.name
                }
                self.report("HB.")
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
            self.report("HB. WW.")
        else:
            print("[{}] Unknown result from creep.harvest({}) (big): {}".format(
                self.name, source, result
            ))
            self.report("HB. ???")

        return False


profiling.profile_class(BigHarvester, profiling.ROLE_BASE_IGNORE)

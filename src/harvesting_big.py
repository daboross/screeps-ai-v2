import hivemind
from base import *
from role_base import RoleBase

__pragma__('noalias', 'name')


class BigHarvester(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self.creep, hivemind.target_big_source)

        if not source:
            print("[{}] No big sources found.".format(self.name))
            return

        result = self.creep.harvest(source)
        if result == ERR_NOT_IN_RANGE:
            self.move_to(source)
            self.creep.say("HB. F. S.")
        elif result == OK:
            if Memory.big_harvesters_placed:
                Memory.big_harvesters_placed[source.id] = self.name
            else:
                Memory.big_harvesters_placed = {
                    source.id: self.name
                }
            self.creep.say("HB.")
        elif result == -6:
            # TODO: get the enum name for -6 (no resources available)
            # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
            self.creep.say("HB. WW.")
        else:
            print("[{}] Unknown result from creep.harvest({}) (big): {}".format(
                self.name, source, result
            ))
            self.creep.say("HB. ???")

        return False

from constants import SQUAD_SIGN_CLEAR
from creeps.squads.base import BasicOffenseSquad
from jstools.errorlog import try_exec
from jstools.screeps import *
from position_management import flags

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class TripleHealSign(BasicOffenseSquad):
    def calculate_movement_order(self):
        """
        Recommended override function.

        Returns all of self members in a deterministic order - called once per tick when used, then cached.

        :rtype: list[creeps.roles.squads.SquadDrone]
        """
        healers = []
        other = []
        for member in self.members:
            if member.findSpecialty() == HEAL:
                healers.append(member)
            else:
                other.append(member)

        if len(healers) > 1:
            return [healers[0]].concat(_.sortByAll(other, 'name')).concat(_.sortByAll(healers[1:], 'name'))
        else:
            return _.sortByAll(other, 'name').concat(healers)

    def run(self):
        members = self.members_movement_order()
        for member in members:
            if member.pos.isNearTo(self.location):
                member.creep.signController(member.room.room.controller, '')
                if member.room.room.controller.sign == undefined:
                    flag = flags.look_for(member.room, self.location.pos, SQUAD_SIGN_CLEAR)
                    if flag:
                        flag.remove()
                break
        else:
            self.move_to(self.location)
        for member in members:
            try_exec(
                "squads",
                member.run_squad,
                lambda: "Error during run_squad for {}, a {}.".format(member.name, member.memory.role),
                members,
                self.location
            )

    def is_heavily_armed(self):
        return True

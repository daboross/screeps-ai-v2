from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union, cast

from creep_management import spawning
from directories import target_functions
from jstools.screeps import *
from position_management import locations

if TYPE_CHECKING:
    from creeps.base import RoleBase
    from position_management.locations import Location

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

_MAX_BUILDERS = 4
_MAX_REPAIR_WORKFORCE = 10

tmkey_targets_used = "targets_used"
tmkey_targeters_using = "targeters_using"
tmkey_workforce = "targets_workforce"
tmkey_stealable = "targets_stealable"


def _mass_count(name):
    # type: (str) -> int
    # set in spawning and role base.
    if name in Memory.creeps and (Memory.creeps[name].carry or Memory.creeps[name].work):
        carry = Memory.creeps[name].carry or 0
        work = Memory.creeps[name].work or 0
    elif name in Game.creeps:
        creep = Game.creeps[name]
        carry = spawning.carry_count(creep)
        work = spawning.work_count(creep)
    else:
        return 1
    # TODO: do we, instead of doing this, want to count two different mass targeting variables in memory?
    return max(work, carry)


__pragma__('fcall')


def update_targeters_memory_0_to_1(targeters):
    # type: (Dict[str, Dict[str, str]]) -> Dict[str, Dict[int, str]]
    string_target_names_to_numbers = {
        'source': 0,
        'generic_deposit': 1,
        'sccf': 2,
        'sccf2': 3,
        'hf': 4,
        'refill': 5,
        'construction_site': 10,
        'repair_site': 11,
        'extra_repair_site': 12,
        'ders': 13,
        'destruction_site': 14,
        'spawn_deposit_site': 20,
        'fillable_tower': 21,
        'remote_miner_mine': 30,
        'remote_mine_hauler': 31,
        'top_priority_reserve': 32,
        'rampart_def': 40,
    }
    new_targeters = {}
    for targeter_id in Object.keys(targeters):
        new_targeter_map = {}
        new_targeters[targeter_id] = new_targeter_map
        for ttype in Object.keys(targeters[targeter_id]):
            target_id = targeters[targeter_id][ttype]
            if _.isString(ttype):
                if ttype in string_target_names_to_numbers:
                    ttype = string_target_names_to_numbers[ttype]
                else:
                    msg = "WARNING: Error updating old TargetMind memory. Couldn't find ttype {} in conversion map!" \
                        .format(ttype)
                    print(msg)
                    Game.notify(msg)
                    raise AssertionError(msg)
            elif not _.isNumber(ttype):
                msg = "WARNING: Error updating old TargetMind memory. Unknown type of ttype (not string nor int): {}!" \
                    .format(ttype)
                print(msg)
                Game.notify(msg)
                raise AssertionError(msg)
            new_targeter_map[ttype] = target_id
    return new_targeters


class TargetMind:
    def __init__(self):
        if not Memory.targets:
            Memory.targets = {
                tmkey_targets_used: {},
                tmkey_targeters_using: {},
                "last_clear": Game.time,
                "version": 1,
            }
        self.mem = cast(Dict[str, Any], Memory.targets)
        if 'version' not in self.mem or self.mem.version < 1:
            targeters = self.mem[tmkey_targeters_using] or {}
            self.mem[tmkey_targeters_using] = update_targeters_memory_0_to_1(targeters)
            self._recreate_all_from_targeters()
            self.mem.version = 1
            self.mem.last_clear = Game.time
        if not self.mem[tmkey_targets_used]:
            self.mem[tmkey_targets_used] = {}
        if not self.mem[tmkey_workforce]:
            self.mem[tmkey_workforce] = {}
        if not self.mem[tmkey_targeters_using]:
            self.mem[tmkey_targeters_using] = {}
        if not self.mem[tmkey_stealable]:
            self.mem[tmkey_stealable] = {}
        if (self.mem.last_clear or 0) + 1000 < Game.time:
            self._recreate_all_from_targeters()
            self.mem.last_clear = Game.time

    def __get_targets(self):
        # type: () -> Dict[int, Dict[str, int]]
        return self.mem[tmkey_targets_used]

    def __set_targets(self, value):
        # type: (Dict[int, Dict[str, int]]) -> None
        self.mem[tmkey_targets_used] = value

    def __get_targeters(self):
        # type: () -> Dict[str, Dict[int, str]]
        return self.mem[tmkey_targeters_using]

    def __set_targeters(self, value):
        # type: (Dict[str, Dict[int, str]]) -> None
        self.mem[tmkey_targeters_using] = value

    def __get_targets_workforce(self):
        # type: () -> Dict[int, Dict[str, int]]
        return self.mem[tmkey_workforce]

    def __set_targets_workforce(self, value):
        # type: (Dict[int, Dict[str, int]]) -> None
        self.mem[tmkey_workforce] = value

    def __get_reverse_targets(self):
        # type: () -> Dict[int, Dict[str, List[str]]]
        return self.mem[tmkey_stealable]

    def __set_reverse_targets(self, value):
        # type: (Dict[int, Dict[str, List[str]]]) -> None
        self.mem[tmkey_stealable] = value

    targets = property(__get_targets, __set_targets)
    targeters = property(__get_targeters, __set_targeters)
    targets_workforce = property(__get_targets_workforce, __set_targets_workforce)
    reverse_targets = property(__get_reverse_targets, __set_reverse_targets)

    def workforce_of(self, ttype, target_id):
        # type: (int, str) -> int
        return (self.targets[ttype] and self.targets[ttype][target_id]
                and self.targets_workforce[ttype] and self.targets_workforce[ttype][target_id]) or 0

    def creeps_now_targeting(self, ttype, target_id):
        # type: (int, str) -> List[str]
        return (ttype in self.reverse_targets and self.reverse_targets[ttype][target_id]) or []

    def _register_new_targeter(self, ttype, targeter_id, target_id):
        # type: (int, str, str) -> None
        if targeter_id not in self.targeters:
            self.targeters[targeter_id] = {
                ttype: target_id
            }
        elif ttype not in self.targeters[targeter_id]:
            self.targeters[targeter_id][ttype] = target_id
        else:
            old_target_id = self.targeters[targeter_id][ttype]
            self.targeters[targeter_id][ttype] = target_id
            if old_target_id == target_id:
                return  # everything beyond here would be redundant
            self.targets[ttype][old_target_id] -= 1
            if self.targets[ttype][old_target_id] <= 0:
                del self.targets[ttype][old_target_id]
            if ttype in self.targets_workforce and old_target_id in self.targets_workforce[ttype]:
                self.targets_workforce[ttype][old_target_id] -= _mass_count(targeter_id)
                if self.targets_workforce[ttype][old_target_id] <= 0:
                    del self.targets_workforce[ttype][old_target_id]
            if ttype in self.reverse_targets and old_target_id in self.reverse_targets[ttype]:
                index = self.reverse_targets[ttype][old_target_id].indexOf(targeter_id)
                if index > -1:
                    self.reverse_targets[ttype][old_target_id].splice(index, 1)

        if ttype not in self.targets:
            self.targets[ttype] = {
                target_id: 1,
            }
        elif not self.targets[ttype][target_id]:
            self.targets[ttype][target_id] = 1
        else:
            self.targets[ttype][target_id] += 1
        if ttype not in self.targets_workforce:
            self.targets_workforce[ttype] = {
                target_id: _mass_count(targeter_id)
            }
        elif target_id not in self.targets_workforce[ttype]:
            self.targets_workforce[ttype][target_id] = _mass_count(targeter_id)
        else:
            self.targets_workforce[ttype][target_id] += _mass_count(targeter_id)
        if ttype not in self.reverse_targets:
            self.reverse_targets[ttype] = {target_id: [targeter_id]}
        elif target_id not in self.reverse_targets[ttype]:
            self.reverse_targets[ttype][target_id] = [targeter_id]
        else:
            self.reverse_targets[ttype][target_id].push(targeter_id)

    def _recreate_all_from_targeters(self):
        # type: () -> None
        new_targets = {}
        new_workforce = {}
        new_reverse = {}
        for targeter_id in Object.keys(self.targeters):
            mass = _mass_count(targeter_id)
            for ttype in Object.keys(self.targeters[targeter_id]):
                target_id = self.targeters[targeter_id][ttype]
                if ttype in new_targets:
                    if target_id in new_targets[ttype]:
                        new_targets[ttype][target_id] += 1
                    else:
                        new_targets[ttype][target_id] = 1
                else:
                    new_targets[ttype] = {target_id: 1}
                if ttype in new_workforce:
                    if target_id in new_workforce[ttype]:
                        new_workforce[ttype][target_id] += mass
                    else:
                        new_workforce[ttype][target_id] = mass
                else:
                    new_workforce[ttype] = {target_id: mass}
                # this target can be stolen, mark the targeter:
                if ttype in new_reverse:
                    if target_id in new_reverse[ttype]:
                        new_reverse[ttype][target_id].push(targeter_id)
                    else:
                        new_reverse[ttype][target_id] = [targeter_id]
                else:
                    new_reverse[ttype] = {target_id: [targeter_id]}

        self.targets = new_targets
        self.targets_workforce = new_workforce
        self.reverse_targets = new_reverse

    def _unregister_targeter(self, ttype, targeter_id):
        # type: (int, str) -> None
        existing_target = self._get_existing_target_id(ttype, targeter_id)
        if existing_target:
            if ttype in self.targets and existing_target in self.targets[ttype]:
                self.targets[ttype][existing_target] -= 1
            if ttype in self.targets_workforce and existing_target in self.targets_workforce[ttype]:
                self.targets_workforce[ttype][existing_target] -= _mass_count(targeter_id)
            if ttype in self.reverse_targets and existing_target in self.reverse_targets[ttype]:
                index = self.reverse_targets[ttype][existing_target].indexOf(targeter_id)
                if index > -1:
                    self.reverse_targets[ttype][existing_target].splice(index, 1)
            del self.targeters[targeter_id][ttype]

    def _unregister_all(self, targeter_id):
        # type: (str) -> None
        if self.targeters[targeter_id]:
            mass = _mass_count(targeter_id)
            for ttype in Object.keys(self.targeters[targeter_id]):
                target = self.targeters[targeter_id][ttype]
                if ttype in self.targets and target in self.targets[ttype]:
                    self.targets[ttype][target] -= 1
                if ttype in self.targets_workforce and target in self.targets_workforce[ttype]:
                    self.targets_workforce[ttype][target] -= mass
                if ttype in self.reverse_targets and target in self.reverse_targets[ttype]:
                    index = self.reverse_targets[ttype][target].indexOf(targeter_id)
                    if index > -1:
                        self.reverse_targets[ttype][target].splice(index, 1)
        del self.targeters[targeter_id]

    def _move_targets(self, old_targeter_id, new_targeter_id):
        # type: (str, str) -> None
        if self.targeters[old_targeter_id]:
            self.targeters[new_targeter_id] = self.targeters[old_targeter_id]
            old_mass = _mass_count(old_targeter_id)
            new_mass = _mass_count(new_targeter_id)
            for ttype in Object.keys(self.targeters[new_targeter_id]):
                target = self.targeters[new_targeter_id][ttype]
                if ttype in self.targets_workforce:
                    if target in self.targets_workforce:
                        self.targets_workforce[ttype][target] += new_mass - old_mass
                    else:
                        self.targets_workforce[ttype][target] = new_mass
                else:
                    self.targets_workforce[ttype] = {target: new_mass}
                if ttype in self.reverse_targets and target in self.reverse_targets[ttype]:
                    index = self.reverse_targets[ttype][target].indexOf(old_targeter_id)
                    if index > -1:
                        self.reverse_targets[ttype][target].splice(index, 1, new_targeter_id)
            del self.targeters[old_targeter_id]

    def _find_new_target(self, ttype, creep, extra_var):
        # type: (int, RoleBase, Optional[Any]) -> Optional[str]
        """
        :type ttype: str
        :type creep: creeps.base.RoleBase
        :type extra_var: ?
        """
        if ttype not in self.targets:
            self.targets[ttype] = {}
        if ttype not in self.targets_workforce:
            self.targets_workforce[ttype] = {}
        if ttype not in self.reverse_targets:
            self.reverse_targets[ttype] = {}
        func = target_functions.find_functions[ttype]
        if func:
            return func(self, creep, extra_var)
        else:
            raise AssertionError("Couldn't find find_function for '{}'!".format(ttype))

    def _get_existing_target_id(self, ttype, targeter_id):
        # type: (int, str) -> Optional[str]
        if targeter_id in self.targeters and ttype in self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        return None

    def _get_new_target_id(self, ttype, targeter_id, creep, extra_var):
        # type: (int, str, RoleBase, Optional[Any]) -> Optional[str]
        if targeter_id in self.targeters and ttype in self.targeters[targeter_id]:
            return self.targeters[targeter_id][ttype]
        new_target = self._find_new_target(ttype, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(ttype, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, ttype, extra_var=None, second_time=False):
        # type: (RoleBase, int, Optional[Any], bool) -> Optional[Union[RoomObject, Location]]
        target_id = self._get_new_target_id(ttype, creep.name, creep, extra_var)
        if not target_id:
            return None
        target = Game.getObjectById(target_id)
        if target is None:
            target = locations.get(target_id)
            if target is None and target_id.startswith and target_id.startswith("flag-"):
                target = Game.flags[target_id[5:]]
        if not target:
            self._unregister_targeter(ttype, creep.name)
            if not second_time:
                return self.get_new_target(creep, ttype, extra_var, True)
            else:
                return None
        return target

    def get_existing_target(self, creep, ttype):
        # type: (Union[RoleBase, Creep], int) -> Optional[Union[RoomObject, Location]]
        target_id = self._get_existing_target_id(ttype, creep.name)
        if not target_id:
            return None

        target = Game.getObjectById(target_id)
        if target is None:
            target = locations.get(target_id)
            if target is None and target_id.startswith and target_id.startswith("flag-"):
                target = Game.flags[target_id[5:]]

        if not target:
            self._unregister_targeter(ttype, creep.name)
        return target

    def manually_register(self, creep, ttype, target_id):
        # type: (Union[RoleBase, Creep], int, str) -> None
        self._register_new_targeter(ttype, creep.name, target_id)

    def untarget(self, creep, ttype):
        # type: (Union[RoleBase, Creep], int) -> None
        self._unregister_targeter(ttype, creep.name)

    def unregister_name(self, creep_name, ttype):
        # type: (str, int) -> None
        self._unregister_targeter(ttype, creep_name)

    def untarget_all(self, creep):
        # type: (Union[RoleBase, Creep]) -> None
        self._unregister_all(creep.name)

    def assume_identity(self, old_name, new_name):
        # type: (str, str) -> None
        self._move_targets(old_name, new_name)


__pragma__('nofcall')

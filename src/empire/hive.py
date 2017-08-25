from typing import Dict, List, Optional, TYPE_CHECKING, Union, cast

from constants import *
from creep_management import creep_wrappers
from empire.honey import HoneyTrails
from empire.states import StateCalc
from jstools import errorlog
from jstools.screeps import *
from position_management import flags
from rooms.room_constants import room_spending_state_visual
from rooms.room_mind import RoomMind
from utilities import movement

if TYPE_CHECKING:
    from empire.targets import TargetMind
    from creeps.base import RoleBase

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class HiveMind:
    """
    :type targets: empire.targets.TargetMind
    :type honey: empire.honey.HoneyTrails
    :type my_rooms: list[RoomMind]
    :type visible_rooms: list[RoomMind]
    """

    def __init__(self, targets):
        # type: (TargetMind) -> None
        self.targets = targets
        self.honey = HoneyTrails(self)
        self.states = StateCalc(self)
        self._my_rooms = None
        self._all_rooms = None
        self._room_to_mind = {}
        self.has_polled_for_creeps = False

    def find_my_rooms(self):
        # type: () -> List[RoomMind]
        """
        :rtype: list[RoomMind]
        """
        if not self._my_rooms:
            my_rooms = []
            all_rooms = []
            sponsoring = {}
            for name in Object.keys(Game.rooms):
                room_mind = RoomMind(self, Game.rooms[name])
                all_rooms.append(room_mind)
                if room_mind.my:
                    my_rooms.append(room_mind)
                    if not room_mind.spawn and room_mind.sponsor_name:
                        if sponsoring[room_mind.sponsor_name]:
                            sponsoring[room_mind.sponsor_name].append(room_mind)
                        else:
                            sponsoring[room_mind.sponsor_name] = [room_mind]
                self._room_to_mind[name] = room_mind
            for sponsor_name in Object.keys(sponsoring):
                sponsor = self._room_to_mind[sponsor_name]
                if sponsor:
                    for subsidiary in sponsoring[sponsor_name]:
                        sponsor.subsidiaries.append(subsidiary)
            self._my_rooms = my_rooms
            self._all_rooms = _.sortBy(all_rooms, 'room_name')
        return self._my_rooms

    def find_visible_rooms(self):
        # type: () -> List[RoomMind]
        if not self._all_rooms:
            self.find_my_rooms()
        return self._all_rooms

    __pragma__('fcall')

    def get_room(self, room_name):
        # type: (str) -> Optional[RoomMind]
        """
        Gets a visible room given its room name.
        :rtype: RoomMind
        """
        if self._all_rooms is None:
            self.find_visible_rooms()
        return self._room_to_mind[room_name]

    __pragma__('nofcall')

    def poll_remote_mining_flags(self):
        # type: () -> None
        flag_list = flags.find_flags_global(REMOTE_MINE)
        room_to_flags = {}  # type: Dict[str, List[Flag]]
        for flag in flag_list:
            room = self.get_room(flag.pos.roomName)
            if room and room.my:
                print("[{}] Removing remote mining flag {}, now that room is owned.".format(room.name, flag.name))
                flag.remove()
            else:
                sponsor = flags.flag_sponsor(flag)
                if not sponsor:
                    print("[hive] Couldn't find sponsor for mining flag {}! (sponsor name set: {})".format(
                        flag.name, flag.memory.sponsor
                    ))
                    continue
                if room_to_flags[sponsor]:
                    room_to_flags[sponsor].append(flag)
                else:
                    room_to_flags[sponsor] = [flag]
        for room in self.my_rooms:
            if room.name in room_to_flags:
                room._remote_mining_operations = room_to_flags[room.name]
                del room_to_flags[room.name]
            else:
                room._remote_mining_operations = []
        for room_name in Object.keys(room_to_flags):
            print("[hive] WARNING! Flags {} has sponsor {}, which is not an owned room!"
                  .format(room_to_flags[room_name], room_name))

    __pragma__('fcall')

    def get_closest_owned_room(self, current_room_name):
        # type: (str) -> Optional[RoomMind]
        current_room = self.get_room(current_room_name)
        if current_room and current_room.my:
            return current_room

        mining_flags = flags.find_flags(current_room_name, REMOTE_MINE)
        for flag in mining_flags:
            if 'sponsor' in flag.memory:
                sponsor = self.get_room(flag.memory.sponsor)
            else:
                sponsor = self.get_room(flag.name.split('_')[0])
            if sponsor:
                return sponsor
        current_pos = movement.parse_room_to_xy(current_room_name)
        if not current_pos:
            print("[{}] Couldn't parse room name!".format(current_room_name))
            return None
        closest_squared_distance = Infinity
        closest_room = None
        for room in self.my_rooms:
            distance = movement.squared_distance(current_pos, room.position)
            if distance < closest_squared_distance:
                closest_squared_distance = distance
                closest_room = room
        if not closest_room:
            print("[{}] ERROR: could not find closest owned room!".format(current_room_name))
        return closest_room

    __pragma__('nofcall')

    def poll_all_creeps(self):
        # type: () -> None
        new_creep_lists = {}  # type: Dict[str, List[Creep]]
        for name in Object.keys(Game.creeps):
            creep = Game.creeps[name]
            home = creep.memory.home
            if not creep.memory.home:
                home = self.get_closest_owned_room(creep.pos.roomName)
                print("[{}][{}] Giving a {} a new home.".format(home.name, creep.name, creep.memory.role))
                creep.memory.home = home.name
            if home in new_creep_lists:
                new_creep_lists[home].append(creep)
            else:
                new_creep_lists[home] = [creep]
        for name in Object.keys(new_creep_lists):
            room = self.get_room(name)
            if not room:
                print("[hive] One or more creeps has {} as its home, but {} isn't even visible!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.notify("[hive] One or more creeps has {} as its home, but {} isn't even visible!".format(
                        name, name))
                    Memory.meta.unowned_room_alerted = True
            elif not room.my:
                print("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                if not Memory.meta.unowned_room_alerted:
                    Game.notify("[hive] One or more creeps has {} as its home, but {} isn't owned!".format(name, name))
                    Memory.meta.unowned_room_alerted = True
            else:
                room._creeps = new_creep_lists[name]
        self.has_polled_for_creeps = True

    def send_everything(self, target_room):
        # type: (Union[RoomMind, Room, str]) -> None
        target_room = cast(RoomMind, target_room).name or cast(str, target_room)

        for room in self.my_rooms:
            if room.name != target_room and not room.minerals.has_no_terminal_or_storage():
                del room.minerals.mem().fulfilling[RESOURCE_ENERGY]
                room.minerals.send_minerals(target_room, RESOURCE_ENERGY, 200 * 1000)

    def mineral_report(self):
        # type: () -> str
        result = ['Hive Mineral Report:']
        tally = {}  # type: Dict[str, int]
        for room in self.my_rooms:
            if room.minerals and not room.minerals.has_no_terminal_or_storage():
                result.append(room.minerals.mineral_report())
                for mineral, amount in _.pairs(room.minerals.get_total_room_resource_counts()):
                    if mineral in tally:
                        tally[mineral] += amount
                    else:
                        tally[mineral] = amount
        result.append("totals:\t{}".format(
            "\t".join(["{} {}".format(amount, mineral) for mineral, amount in _.pairs(tally)])
        ))
        return "\n".join(result)

    def status(self):
        # type: () -> str
        result = ['Hive Status Report:']
        for room in self.my_rooms:
            room_result = []
            if room.mem[rmem_key_currently_under_siege]:
                room_result.append('under attack')
            if room.mem.pause:
                room_result.append('paused')
            if room.mem[rmem_key_now_supporting]:
                room_result.append('supporting {}'.format(room.mem[rmem_key_now_supporting]))
            if room.mem[rmem_key_prepping_defenses]:
                room_result.append('prepping defenses')
            room_result.append('spending on {}.'.format(room_spending_state_visual[room.get_spending_target()]))
            result.append('{}: {}'.format(room.name, ', '.join(room_result)))
        return '\n'.join(result)

    def checkup(self):
        # type: () -> str
        result = ['Hive Structures Checkup:']
        for room in self.my_rooms:
            room_result = []
            counts = _.countBy(room.find(FIND_STRUCTURES), 'structureType')

            if room.rcl >= 8:
                if (counts[STRUCTURE_OBSERVER] or 0) < 1:
                    room_result.append('no observer')
                if (counts[STRUCTURE_POWER_SPAWN] or 0) < 1:
                    room_result.append('no power spawn')
            if room.rcl >= 6:
                if (counts[STRUCTURE_LAB] or 0) < 3:
                    if STRUCTURE_LAB not in counts:
                        room_result.append('no labs')
                    else:
                        room_result.append('{} labs'.format(counts[STRUCTURE_LAB]))
            if (counts[STRUCTURE_SPAWN] or 0) < CONTROLLER_STRUCTURES[STRUCTURE_SPAWN][room.rcl]:
                room_result.append('{} / {} spawns'.format(counts[STRUCTURE_SPAWN] or 0,
                                                           CONTROLLER_STRUCTURES[STRUCTURE_SPAWN][room.rcl]))
            if (counts[STRUCTURE_TOWER] or 0) < CONTROLLER_STRUCTURES[STRUCTURE_TOWER][room.rcl]:
                room_result.append('{} / {} towers'.format(counts[STRUCTURE_TOWER] or 0,
                                                           CONTROLLER_STRUCTURES[STRUCTURE_TOWER][room.rcl]))
            if (counts[STRUCTURE_EXTENSION] or 0) < CONTROLLER_STRUCTURES[STRUCTURE_EXTENSION][room.rcl]:
                room_result.append('{} / {} extensions'.format(counts[STRUCTURE_EXTENSION] or 0,
                                                               CONTROLLER_STRUCTURES[STRUCTURE_EXTENSION][room.rcl]))
            if (counts[STRUCTURE_WALL] or 0) > (counts[STRUCTURE_RAMPART] or 0):
                room_result.append('more walls than ramparts: {} walls, {} ramparts'
                                   .format(counts[STRUCTURE_WALL] or 0, counts[STRUCTURE_RAMPART] or 0))

            if len(room_result):
                result.append('{}:\n\t{}'.format(room.name, '\n\t'.join(room_result)))
            else:
                result.append('{}: ✓'.format(room.name))
        return '\n'.join(result)

    def sing(self):
        # type: () -> None
        if '_ly' not in Memory:
            Memory['_ly'] = {}
        creeps_by_room = _.groupBy(Game.creeps, 'pos.roomName')  # type: Dict[str, List[Creep]]
        for room_name in Object.keys(creeps_by_room):
            room = self.get_room(room_name)
            if room:
                room.sing(creeps_by_room[room_name])
            else:
                print("[hive] WARNING: No room found with name {}, which {} creeps were supposedly in!"
                      .format(room_name, len(creeps_by_room[room])))
        if Game.time % 30 == 0:
            for name in Object.keys(Memory['_ly']):
                if name not in Game.rooms:
                    del Memory['_ly'][name]

    def wrap_creep(self, creep):
        # type: (Creep) -> Optional[RoleBase]
        """
        :type creep: Creep
        :rtype: creeps.base.RoleBase
        """
        home = self.get_room(creep.memory.home)
        if home:
            return errorlog.execute(creep_wrappers.wrap_creep, self, self.targets, home, creep)
        else:
            raise AssertionError("[hive]Invalid value to wrap_creep: {} with memory {}"
                                 .format(creep, JSON.stringify(creep.memory)))

    # noinspection PyPep8Naming
    def toString(self):
        # type: () -> str
        return "HiveMind[rooms: {}]".format(JSON.stringify([room.name for room in self.my_rooms]))

    my_rooms = property(find_my_rooms)
    visible_rooms = property(find_visible_rooms)

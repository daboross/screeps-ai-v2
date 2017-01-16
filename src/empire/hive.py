from constants import *
from creep_management import creep_wrappers
from empire.honey import HoneyTrails
from empire.states import StateCalc
from jstools.screeps_constants import *
from position_management import flags
from rooms.room_constants import room_spending_state_visual
from rooms.room_mind import RoomMind
from utilities import movement

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


class HiveMind:
    """
    :type targets: empire.targets.TargetMind
    :type honey: empire.honey.HoneyTrails
    :type my_rooms: list[RoomMind]
    :type visible_rooms: list[RoomMind]
    """

    def __init__(self, targets):
        self.targets = targets
        self.honey = HoneyTrails(self)
        self.states = StateCalc(self)
        self._my_rooms = None
        self._all_rooms = None
        self._room_to_mind = {}
        self.has_polled_for_creeps = False

    def find_my_rooms(self):
        """
        :rtype: list[RoomMind]
        """
        # Needed in RoomMind.__init__()
        if 'enemy_rooms' not in Memory:
            Memory.enemy_rooms = []
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
                            sponsoring[room_mind.sponsor_name].push(room_mind)
                        else:
                            sponsoring[room_mind.sponsor_name] = [room_mind]
                self._room_to_mind[name] = room_mind
            for sponsor_name in Object.keys(sponsoring):
                sponsor = self._room_to_mind[sponsor_name]
                if sponsor:
                    for subsidiary in sponsoring[sponsor_name]:
                        sponsor.subsidiaries.push(subsidiary)
            self._my_rooms = my_rooms
            self._all_rooms = _.sortBy(all_rooms, 'room_name')
        return self._my_rooms

    def find_visible_rooms(self):
        if not self._all_rooms:
            self.find_my_rooms()
        return self._all_rooms

    __pragma__('fcall')

    def get_room(self, room_name):
        """
        Gets a visible room given its room name.
        :rtype: RoomMind
        """
        if self._all_rooms is None:
            self.find_visible_rooms()
        return self._room_to_mind[room_name]

    __pragma__('nofcall')

    def poll_remote_mining_flags(self):
        flag_list = flags.find_flags_global(REMOTE_MINE)
        room_to_flags = {}
        for flag in flag_list:
            room = self.get_room(flag.pos.roomName)
            if room and room.my:
                print("[{}] Removing remote mining flag {}, now that room is owned.".format(room.name, flag.name))
                flag.remove()
            else:
                if not flag.memory.active:
                    continue
                if 'sponsor' in flag.memory:
                    sponsor = self.get_room(flag.memory.sponsor)
                else:
                    sponsor = self.get_room(flag.name.split('_')[0])
                if not sponsor:
                    print("[hive] Couldn't find sponsor for mining flag {}! (sponsor name set: {})".format(
                        flag.name, flag.memory.sponsor
                    ))
                    continue
                if room_to_flags[sponsor.name]:
                    room_to_flags[sponsor.name].push(flag)
                else:
                    room_to_flags[sponsor.name] = [flag]
        for room in self.my_rooms:
            if room.name in room_to_flags:
                room._remote_mining_operations = room_to_flags[room.name]
            else:
                room._remote_mining_operations = []

    __pragma__('fcall')

    def get_closest_owned_room(self, current_room_name):
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
        new_creep_lists = {}
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
        target_room = target_room.name or target_room

        for room in self.my_rooms:
            if room.name != target_room and not room.minerals.has_no_terminal_or_storage():
                del room.minerals.fulfilling[RESOURCE_ENERGY]
                room.minerals.send_minerals(target_room, RESOURCE_ENERGY, 200 * 1000)

    def mineral_report(self):
        result = ['Hive Mineral Report:']
        tally = {}
        for room in self.my_rooms:
            if room.minerals and not room.minerals.has_no_terminal_or_storage():
                result.append(room.minerals.mineral_report())
                for mineral, amount in _.pairs(room.minerals.get_total_room_resource_counts()):
                    if mineral in tally:
                        tally[mineral] += amount
                    else:
                        tally[mineral] = amount
        result.push("totals:\t{}".format(
            "\t".join(["{} {}".format(amount, mineral) for mineral, amount in _.pairs(tally)])
        ))
        return "\n".join(result)

    def status(self):
        result = ['Hive Status Report:']
        for room in self.my_rooms:
            room_result = []
            if room.mem[rmem_key_currently_under_siege]:
                room_result.push('under attack')
            if room.mem.pause:
                room_result.push('paused')
            if room.mem[rmem_key_now_supporting]:
                room_result.push('supporting {}'.format(room.mem[rmem_key_now_supporting]))
            if room.mem[rmem_key_prepping_defenses]:
                room_result.push('prepping defenses')
            room_result.push('spending on {}.'.format(room_spending_state_visual[room.main_spending_expenditure()]))
            result.push('{}: {}'.format(room.name, ', '.join(room_result)))
        return '\n'.join(result)

    def sing(self):
        if '_ly' not in Memory:
            Memory['_ly'] = {}
        creeps_by_room = _.groupBy(Game.creeps, 'pos.roomName')
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
        """
        :type creep: Creep
        :rtype: creeps.base.RoleBase
        """
        home = self.get_room(creep.memory.home)
        if home:
            return creep_wrappers.wrap_creep(self, self.targets, home, creep)
        else:
            raise ValueError("[hive]Invalid value to wrap_creep: {} with memory {}"
                             .format(creep, JSON.stringify(creep.memory)))

    def toString(self):
        return "HiveMind[rooms: {}]".format(JSON.stringify([room.name for room in self.my_rooms]))

    my_rooms = property(find_my_rooms)
    visible_rooms = property(find_visible_rooms)

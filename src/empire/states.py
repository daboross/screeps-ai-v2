from typing import TYPE_CHECKING

from constants import rmem_key_currently_under_siege
from jstools.screeps import *

if TYPE_CHECKING:
    from empire.hive import HiveMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

# 1 million on default server
_min_wall_hit_difference_to_balance = WALL_HITS_MAX / 300


class StateCalc:
    """
    :type hive: empire.hive.HiveMind
    """

    def __init__(self, hive: HiveMind):
        self.hive = hive

    def calculate_room_states(self) -> None:
        under_siege = []
        not_under_siege = []
        for room in self.hive.my_rooms:
            if room.minerals.fully_setup():
                if len(room.spawns) and (room.mem[rmem_key_currently_under_siege]
                                         or room.defense.has_significant_nukes()) \
                        or ((len(room.squads.squad_targets()) or len(room.subsidiaries))
                            and room.minerals.get_estimate_total_energy() < 200 * 1000):
                    under_siege.append(room)
                else:
                    not_under_siege.append(room)

        if len(under_siege) > 0:
            if len(not_under_siege) > 0:
                if len(under_siege) > 1:
                    under_siege = _.sortBy(under_siege, lambda x: x.calculate_smallest_wall())
                    while len(under_siege) < len(not_under_siege):
                        under_siege = under_siege.concat(under_siege)
                    for room in under_siege:
                        room.set_supporting_room(None)
                        if not len(not_under_siege):
                            break
                        closest = None
                        closest_index = None
                        closest_distance = Infinity
                        for i in range(0, len(not_under_siege)):
                            room_to_check = not_under_siege[i]
                            distance = Game.map.getRoomLinearDistance(room.name, room_to_check.name, True)
                            if distance < closest_distance:
                                closest = room_to_check
                                closest_distance = distance
                                closest_index = i
                        not_under_siege.splice(closest_index, 1)
                        closest.set_supporting_room(room.name)
                else:
                    for room in not_under_siege:
                        room.set_supporting_room(under_siege[0].name)
            else:
                for room in under_siege:
                    room.set_supporting_room(None)
        elif len(not_under_siege) > 0:
            if len(not_under_siege) > 1:
                smallest_room = None
                smallest_room_smallest_wall = Infinity
                biggest_room_smallest_wall = -Infinity
                for room in not_under_siege:
                    hits = room.calculate_smallest_wall()
                    if hits < smallest_room_smallest_wall:
                        smallest_room_smallest_wall = hits
                        smallest_room = room.name
                    elif hits > biggest_room_smallest_wall:
                        biggest_room_smallest_wall = hits
                if biggest_room_smallest_wall - smallest_room_smallest_wall > _min_wall_hit_difference_to_balance:
                    any_above_should_support = (biggest_room_smallest_wall + smallest_room_smallest_wall) / 2
                    for room in not_under_siege:
                        if room.rcl >= 8:
                            hits = room.calculate_smallest_wall()
                            if hits >= any_above_should_support:
                                room.set_supporting_room(smallest_room)
                            else:
                                room.set_supporting_room(None)
                        else:
                            room.set_supporting_room(None)
                else:
                    for room in not_under_siege:
                        room.set_supporting_room(None)
            else:
                not_under_siege[0].set_supporting_room(None)

import math
from typing import List, Optional, TYPE_CHECKING, Union, cast

from cache import volatile_cache
from constants import rmem_key_linking_mind_storage
from jstools.screeps import *
from utilities import movement

if TYPE_CHECKING:
    from rooms.room_mind import RoomMind
    from jstools.js_set_map import JSMap
    from creeps.base import RoleBase
    from creeps.roles.utility import LinkManager

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

__pragma__('fcall')


class LinkingMind:
    """
    :type room: rooms.room_mind.RoomMind
    :type link_creep: creeps.roles.utility.LinkManager

    """

    def __init__(self, room: RoomMind):
        self.room = room
        __pragma__('skip')
        self._links = undefined
        self._main_link = undefined
        self._second_link = undefined
        self.link_creep = undefined
        __pragma__('noskip')
        self.enabled_last_turn = room.get_cached_property("links_enabled") or False

    def _get_links(self):
        # type: () -> List[StructureLink]
        """
        :rtype: list[StructureLink]
        """
        if self._links is undefined:
            self._links = cast(List[StructureLink], _.filter(self.room.find(FIND_MY_STRUCTURES),
                                                             {"structureType": STRUCTURE_LINK}))
        return self._links

    def get_main_link(self):
        # type: () -> Optional[StructureLink]
        if self._main_link is undefined:
            if self.room.my and self.room.room.storage and len(self.links) >= 2:
                for link in self.links:
                    if movement.chebyshev_distance_room_pos(self.room.room.storage.pos, link.pos) <= 2:
                        if self._main_link is undefined:
                            self._main_link = link
                        else:
                            self._second_link = link
            if self._main_link is undefined:
                self._main_link = None
            if self._second_link is undefined:
                self._second_link = None
        return self._main_link

    def get_second_main_link(self):
        # type: () -> Optional[StructureLink]
        if self._main_link is undefined:
            self.get_main_link()
        return self._second_link

    main_link = property(get_main_link)
    secondary_link = property(get_second_main_link)

    def link_mem(self, link):
        # type: (StructureLink) -> _Memory
        if link.id:
            link = link.id

        if rmem_key_linking_mind_storage not in self.room.mem:
            self.room.mem[rmem_key_linking_mind_storage] = {}
        if link not in self.room.mem[rmem_key_linking_mind_storage]:
            self.room.mem[rmem_key_linking_mind_storage][link] = {}
        return self.room.mem[rmem_key_linking_mind_storage][link]

    def volatile_link_mem(self, link):
        # type: (StructureLink) -> JSMap
        if link.id:
            link = link.id

        return volatile_cache.submem('links', link)

    links = property(_get_links)

    def _enabled(self):
        # type: () -> bool
        return self.enabled_last_turn

    enabled = property(_enabled)

    def enabled_this_turn(self):
        # type: () -> bool
        if not not self.room.room.storage and self.link_creep and self.main_link and len(self.links) >= 2:
            self.room.store_cached_property("links_enabled", True, 2)
            return True
        return False

    def register_target_withdraw(self, target, targeter, needed, distance):
        # type: (StructureLink, Union[Creep, RoleBase], int, int) -> None
        targeter = targeter.name

        self.volatile_link_mem(target).set(targeter, {
            'cap': -needed,
            'distance': distance
        })
        self.link_mem(target).last_withdraw = Game.time

    def register_target_deposit(self, target, targeter, depositing, distance):
        # type: (StructureLink, Union[Creep, RoleBase], int, int) -> None
        targeter = targeter.name

        self.volatile_link_mem(target).set(targeter, {
            'cap': +depositing,
            'distance': distance
        })
        self.link_mem(target).last_deposit = Game.time

    def note_link_manager(self, creep):
        # type: (LinkManager) -> None
        """
        Notes the link manager for this tick. This should be called once per tick by the link manager when it is close
        to both the main link and storage, and then LinkingMind will give the creep the needed action at the end of the
        tick.

        :type creep: creeps.roles.utility.LinkManager
        :param creep: Link manager
        """
        if self.link_creep is not undefined:
            creep1 = self.link_creep
            creep2 = creep

            def send_to_link(link, amount):
                creep1.send_to_link(link, amount)
                if amount > creep1.creep.carryCapacity / 2:
                    creep2.send_to_link(link, amount - creep1.creep.carryCapacity / 2)

            def send_from_link(link, amount):
                creep1.send_from_link(link, amount)
                if amount > creep1.creep.carryCapacity / 2:
                    creep2.send_to_link(link, amount - creep1.creep.carryCapacity / 2)

            self.link_creep = cast(LinkManager, {
                "send_to_link": send_to_link,
                "send_from_link": send_from_link,
                # Support doing this multiple times.
                "creep": {"carryCapacity": creep1.creep.carryCapacity + creep2.creep.carryCapacity}
            })
        self.link_creep = creep

    def tick_links(self):
        # type: () -> None
        if not self.enabled_this_turn():
            return
        main_link = self.main_link
        secondary_link = self.secondary_link
        current_output_links = []
        current_input_links = []
        future_output_links = []
        future_input_links = []
        for link in self.links:
            if link.id == main_link.id or (secondary_link and link.id == secondary_link.id):
                continue
            mem = self.link_mem(link)
            vmem = self.volatile_link_mem(link)
            energy_change_now = 0
            for obj in Array.js_from(vmem.values()):
                if obj.distance <= 1:
                    energy_change_now += obj.cap
            if Memory.links_debug == self.room.name:
                print("[{}] Energy change: {}".format(link.id[-5:], energy_change_now))
            if energy_change_now > 0:
                if energy_change_now * 3 > link.energyCapacity - link.energy and link.cooldown <= 0:
                    current_input_links.append({'link': link, 'priority': -energy_change_now})
                else:
                    future_input_links.append({'link': link, 'amount': energy_change_now, 'priority': link.cooldown})
            elif energy_change_now < 0:
                if -energy_change_now * 3 > link.energy:
                    current_output_links.append({'link': link, 'priority': energy_change_now})
                else:
                    future_output_links.append({
                        'link': link,
                        'amount': -energy_change_now - link.energy,
                        'priority': math.floor(link.energy / energy_change_now)
                    })
            else:
                access_list = _.sortBy(_.filter(vmem.values(), lambda x: x.distance > 1), lambda x: x.distance)
                if len(access_list):
                    count = access_list[0].cap
                    for x in access_list:
                        if (x.cap > 0) == (count > 0):
                            # only count one type of action
                            count += x.cap
                        else:
                            break
                    if count > 0:
                        if count > link.energyCapacity - link.energy:
                            future_input_links.append({
                                'link': link,
                                'amount': -count,
                                'priority': access_list[0].distance
                            })
                    else:
                        if count < link.energy:
                            future_output_links.append({
                                'link': link,
                                'amount': count,
                                'priority': access_list[0].distance
                            })
                else:
                    if mem.last_deposit and (not mem.last_withdraw or mem.last_deposit > mem.last_withdraw):
                        future_input_links.append({'link': link, 'amount': link.energy, 'priority': 10})
                    elif mem.last_withdraw and (not mem.last_deposit or mem.last_withdraw > mem.last_deposit):
                        future_output_links.append({'link': link, 'amount': link.energy, 'priority': 10})

        current_input_links.sort(key=lambda x: x.priority)
        current_output_links.sort(key=lambda x: x.priority)
        if Memory.links_debug == self.room.name:
            if len(current_input_links):
                print("Current Input: {}".format(
                    ["{} (p:{} a:{})".format(x.link, x.priority, x.amount) for x in current_input_links]))
            if len(current_output_links):
                print("Current Output: {}".format(
                    ["{} (p:{} a:{})".format(x.link, x.priority, x.amount) for x in current_output_links]))
            if len(future_input_links):
                print("Future Input: {}".format(
                    ["{} (p:{} a:{})".format(x.link, x.priority, x.amount) for x in future_input_links]))
            if len(future_output_links):
                print("Future Output: {}".format(
                    ["{} (p:{} a:{})".format(x.link, x.priority, x.amount) for x in future_output_links]))
        # switch every 5 seconds?
        if len(current_output_links) and (not len(current_input_links) or Game.time % 12 >= 6):
            # Priority is output
            if main_link.energy < main_link.energyCapacity:
                self.link_creep.send_to_link(main_link, main_link.energyCapacity - main_link.energy)
            elif secondary_link and secondary_link.energy < secondary_link.energyCapacity:
                self.link_creep.send_to_link(secondary_link, secondary_link.energyCapacity - secondary_link.energy)
            next_output_index = 0
            priority_output = current_output_links[next_output_index]
            next_output_index += 1
            if (main_link.cooldown == 0
                and (main_link.energy == main_link.energyCapacity or
                                 main_link.energy * (1 - LINK_LOSS_RATIO)
                             >= (priority_output.link.energyCapacity - priority_output.link.energy))):
                main_link.transferEnergy(priority_output.link)
                priority_output = current_output_links[next_output_index]
                next_output_index += 1
            if (priority_output and secondary_link and secondary_link.cooldown == 0
                and (secondary_link.energy == secondary_link.energyCapacity
                     or (secondary_link.energy == secondary_link.energyCapacity or
                                     secondary_link.energy * (1 + LINK_LOSS_RATIO)
                                 >= (priority_output.link.energyCapacity - priority_output.link.energy)))):
                secondary_link.transferEnergy(priority_output.link)
                priority_output = current_output_links[next_output_index]
                next_output_index += 1
            if priority_output and len(current_input_links):
                current_input_links[0].link.transferEnergy(priority_output.link)
            elif priority_output and len(future_input_links):
                future_input_links[0].link.transferEnergy(priority_output.link)
        elif len(current_input_links):
            # Priority is input
            if main_link.energy > 0:
                self.link_creep.send_from_link(main_link, main_link.energy)
            else:
                for obj in current_input_links:
                    if obj.link.energy >= obj.link.energyCapacity * 0.85:
                        obj.link.transferEnergy(main_link)
                        break
        elif len(future_input_links):
            if main_link.energyCapacity - main_link.energy < future_input_links[0].link.energy:
                self.link_creep.send_from_link(main_link, main_link.energy)
            else:
                future_input_links[0].link.transferEnergy(main_link)
        elif len(future_output_links):
            if main_link.energy < future_output_links[0].amount - future_output_links[0].link.energy:
                self.link_creep.send_to_link(main_link,
                                             future_output_links[0].amount - future_output_links[0].link.energy
                                             - main_link.energy)
            else:
                self.main_link.transferEnergy(future_output_links[0].link)
        elif main_link.energy != main_link.energyCapacity / 2:
            if main_link.energy > main_link.energyCapacity / 2:
                self.link_creep.send_from_link(main_link, main_link.energy - main_link.energyCapacity / 2)
            else:
                self.link_creep.send_to_link(main_link, main_link.energyCapacity / 2 - main_link.energy)
        elif secondary_link and secondary_link.energy < secondary_link.energyCapacity:
            self.link_creep.send_to_link(secondary_link, secondary_link.energyCapacity - secondary_link.energy)


__pragma__('nofcall')

from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class LinkingMind:
    """
    :type room: control.hivemind.RoomMind
    :type link_creep: roles.utility.LinkManager
    """

    def __init__(self, room):
        self.room = room
        self._links = None
        self._main_link = None
        self.link_creep = None
        self.enabled_last_turn = room.get_cached_property("links_enabled") or False

    def _get_links(self):
        if self._links is None:
            self._links = _.filter(self.room.find(FIND_MY_STRUCTURES),
                                   {"structureType": STRUCTURE_LINK})
        return self._links

    def get_main_link(self):
        if self._main_link is None:
            self._main_link = self.room.find_closest_by_range(FIND_MY_STRUCTURES, self.room.room.storage.pos,
                                                              {"structureType": STRUCTURE_LINK})
        return self._main_link

    main_link = property(get_main_link)

    def link_mem(self, link):
        if link.id:
            link = link.id

        if 'links' not in self.room.mem:
            self.room.mem.links = {}
        if link not in self.room.mem.links:
            self.room.mem.links[link] = {}
        return self.room.mem.links[link]

    links = property(_get_links)

    def _enabled(self):
        return self.enabled_last_turn

    enabled = property(_enabled)

    def enabled_this_turn(self):
        if not not self.room.room.storage and self.link_creep and self.main_link and len(self.links) >= 2:
            self.room.store_cached_property("links_enabled", True, 2)
            return True
        return False

    def register_target_withdraw(self, target, targeter, needed, distance):
        if targeter.name:
            targeter = targeter.name
        self.link_mem(target)[targeter] = {
            'expire': Game.time + 2,
            'cap': -needed,
            'distance': distance
        }

    def register_target_deposit(self, target, targeter, depositing, distance):
        if targeter.name:
            targeter = targeter.name
        self.link_mem(target)[targeter] = {
            'expire': Game.time + 2,
            'cap': +depositing,
            'distance': distance
        }

    def note_link_manager(self, creep):
        """
        Notes the link manager for this tick. This should be called once per tick by the link manager when it is close
        to both the main link and storage, and then LinkingMind will give the creep the needed action at the end of the
        tick.

        :type creep: role_base.RoleBase
        :param creep: Link manager
        """
        self.link_creep = creep

    def tick_links(self):
        if not self.enabled_this_turn():
            return
        time = Game.time
        main_link = self.get_main_link()
        current_output_links = []
        current_input_links = []
        future_output_links = []
        future_input_links = []
        for link in self.links:
            if link.id == main_link.id:
                continue
            mem = self.link_mem(link)
            # deposited_at_this_distance = 0
            # for name in _.sortBy(mem, lambda obj: obj.distance):
            # TODO: the above, a more complicated (and more prone to failure) system. For now, this works.
            energy_change_now = 0
            for name in Object.keys(mem):
                if time > mem[name].expire:
                    del mem[name]
                elif mem[name].distance <= 1:
                    energy_change_now += mem[name].cap
            if energy_change_now > 0:
                if link.cooldown <= 0:
                    current_input_links.append({'link': link, 'priority': energy_change_now})
                else:
                    future_input_links.append({'link': link, 'amount': -energy_change_now, 'priority': link.cooldown})
            elif energy_change_now < 0:
                current_output_links.append({'link': link, 'priority': -energy_change_now})
            else:
                access_list = _.sortBy(_.filter(mem, lambda x: x.distance > 1), lambda x: x.distance)
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
                            future_input_links.append({'link': link, 'amount': -count,
                                                       'priority': access_list[0].distance})
                    else:
                        if count < link.energy:
                            future_output_links.append({'link': link, 'amount': count,
                                                        'priority': access_list[0].distance})

        current_input_links.sort(None, key=lambda x: x.priority)
        current_output_links.sort(None, key=lambda x: x.priority)
        if len(current_output_links):
            # Priority is output
            if main_link.energy < main_link.energyCapacity:
                self.link_creep.send_to_link(main_link.energyCapacity - main_link.energy)
            else:
                self.main_link.transferEnergy(current_output_links[0].link)
        elif len(current_input_links):
            # Priority is input
            if main_link.energy > 0:
                self.link_creep.send_from_link(main_link.energy)
            elif current_input_links[0].link.energy >= current_input_links[0].link.energyCapacity:
                current_input_links[0].link.transferEnergy(main_link)
        elif len(future_output_links):
            if main_link.energy < future_output_links[0].amount - future_output_links[0].link.energy:
                self.link_creep.send_to_link(future_output_links[0].amount - future_output_links[0].link.energy
                                             - main_link.energy)
            else:
                self.main_link.transferEnergy(future_output_links[0].link)
        elif len(future_input_links):
            if main_link.energyCapacity - main_link.energy > future_input_links[0].link.energy:
                self.link_creep.send_from_link(main_link.energy)
            else:
                future_input_links[0].link.transferEnergy(main_link)



profiling.profile_whitelist(LinkingMind, ["tick_links"])

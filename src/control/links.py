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
        return not not self.room.room.storage and self.link_creep and self.main_link and len(self.links) >= 2

    enabled = property(_enabled)

    def register_target_withdraw(self, target, targeter, capacity):
        if targeter.name:
            targeter = targeter.name
        self.link_mem(target)[targeter] = {
            'expire': Game.time + 2,
            'cap': -capacity,
        }

    def register_target_deposit(self, target, targeter, energy):
        if targeter.name:
            targeter = targeter.name
        self.link_mem(target)[targeter] = {
            'expire': Game.time + 2,
            'cap': +energy,
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
        if not self.enabled:
            # if len(self.links):
            #     print("[{}][links] Warning: not running due to not finding storage or link creep.".format(
            #         self.room.room_name))
            return  # TODO: equalize at this point? I don't know
        time = Game.time
        main_link = self.get_main_link()
        main_ready_to_send = main_link.cooldown <= 1
        sending_to_main = 0
        taking_from_main = 0
        send_from_main = []
        send_to_main = []
        for link in self.links:
            if link.id == main_link.id:
                continue
            mem = self.link_mem(link)
            # this variable tracks (current link energy) + (total deposit energy) + (total withdraw energy)
            future_energy = link.energy
            now_withdrawing = 0
            for name in Object.keys(mem):
                if time > mem[name].expire:
                    del mem[name]
                    continue
                if mem[name].cap < 0:
                    now_withdrawing += -mem[name].cap
                future_energy += mem[name].cap
            if link.cooldown <= 0:
                if future_energy > link.energyCapacity and link.energy > link.energyCapacity * 0.2:
                    # we'll have too much soon, so send all energy - but only if we're at least a little bit full.
                    send_to_main.append((link, link.energy))
                    sending_to_main += link.energy
                elif future_energy > link.energyCapacity * 0.75 and now_withdrawing < link.energy:
                    # let's just send a bit of energy
                    energy_sending = link.energy - now_withdrawing
                    send_to_main.append((link, energy_sending))
                    sending_to_main += energy_sending
                elif future_energy > link.energyCapacity * 0.5 and now_withdrawing < min(link.energy,
                                                                                         link.energyCapacity * 0.5):
                    new_energy = future_energy - now_withdrawing
                    if new_energy > link.energyCapacity * 0.5:
                        energy_sending = min(link.energy, new_energy - link.energyCapacity * 0.5)
                        send_to_main.append((link, energy_sending))
                        sending_to_main += energy_sending
                    else:
                        energy_recv = min(link.energyCapacity - link.energy, link.energy * 0.5 - new_energy)
                        send_from_main.append((link, energy_recv))
                        taking_from_main += energy_recv

            if future_energy < 0 and link.energy < link.energyCapacity * 0.75:
                # only send to if we're not mostly full already (for cooldown)
                energy_needed = min(-future_energy, link.energyCapacity - link.energy)
                send_from_main.append((link, energy_needed))
                taking_from_main += energy_needed

        # TODO: this code now assumes that the storage in roughly in the center of the room, and that it would be
        # counterproductive to send energy directly between other links because of the cool down
        if sending_to_main + main_link.energy > main_link.energyCapacity:
            send_to_main.sort(lambda t: -t[1])  # sort from biggest to smallest
            space_needed_in_main = main_link.energy + sending_to_main - main_link.energyCapacity
        else:
            space_needed_in_main = 0

        # print("[links] Vars: sending_to_main: {}, taking_from_main: {}".format(sending_to_main, taking_from_main))

        new_main_energy = main_link.energy
        for link, energy in send_to_main:
            # TODO: find out what this was meant to do, when awake again.
            # if (main_link.energyCapacity - new_main_energy) / energy < 0.75:
            #     continue
            link.transferEnergy(main_link, energy)
            new_main_energy += energy
            if new_main_energy >= main_link.energyCapacity:
                new_main_energy = main_link.energyCapacity
                break
        # TODO: This assumes that if a link sends and receives energy in the same tick, the received amount is still
        # limited by the amount in before sending. Check out that assumption.
        #
        # we can only send energy to one link at a time... is this the best way to choose?

        if taking_from_main and main_ready_to_send:
            send_from_main.sort(lambda t: -t[1])
            if main_link.energy < taking_from_main:
                sending = min(main_link.energy, send_from_main[0][1])
                # TODO: should this statement use sending?
                energy_needed_in_main = min(taking_from_main, main_link.energyCapacity) - main_link.energy
                new_main_energy -= main_link.energy
            else:
                sending = send_from_main[0][1]
                # TODO: is this the right thing to do?
                energy_needed_in_main = min(taking_from_main - sending, main_link.energyCapacity - main_link.enery)
                new_main_energy -= sending
            main_link.transferEnergy(send_from_main[0][0], sending)
        else:
            if taking_from_main and len(send_to_main) <= 1:
                energy_needed_in_main = main_link.energyCapacity - main_link.energy
            else:
                energy_needed_in_main = 0

        # TODO: this is kind of thrown together late at night, with some guesswork as to what I originally intended
        # Perhaps this should be changed, perhaps it is ideal!
        ideal_diff = energy_needed_in_main - space_needed_in_main
        # TODO: this code assumes the link creep only has energy in its hold. should we account for accidental mineral
        # pickups?
        # print("[links] Ideal diff: {}".format(ideal_diff))
        if ideal_diff < 0:
            # we should be emptying the main link
            self.link_creep.send_from_link(-ideal_diff)
        elif ideal_diff > 0:
            self.link_creep.send_to_link(ideal_diff)
        else:
            if main_link.energy < main_link.energyCapacity / 2:
                self.link_creep.send_to_link(main_link.energyCapacity / 2 - main_link.energy)
            elif main_link.energy > main_link.energyCapacity / 2 and not (taking_from_main and not main_ready_to_send):
                self.link_creep.send_from_link(main_link.energy - main_link.energyCapacity / 2)
        pass
        # TODO: do sending to main
        # TODO: do creep actions?
        # TODO: calculate if we need to deposit/withdraw to link?
        # TODO: send from main last.


profiling.profile_whitelist(LinkingMind, ["tick_links"])

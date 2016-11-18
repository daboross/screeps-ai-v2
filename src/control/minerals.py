import math

from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

_SINGLE_MINERAL_FULFILLMENT_MAX = 50 * 1000

sell_at_prices = {
    RESOURCE_OXYGEN: 2.0,
    RESOURCE_HYDROGEN: 2.0,
    RESOURCE_ZYNTHIUM: 2.0,
    RESOURCE_UTRIUM: 2.0,
    RESOURCE_LEMERGIUM: 2.0,
    RESOURCE_KEANIUM: 2.0,
}
bottom_prices = {
    RESOURCE_OXYGEN: 1.0,
    RESOURCE_HYDROGEN: 1.2,
    RESOURCE_KEANIUM: 1.2,
    RESOURCE_ZYNTHIUM: 0.2,
    RESOURCE_UTRIUM: 0.2,
    RESOURCE_LEMERGIUM: 0.2,
}

__pragma__('fcall')


# TODO: expand this for local dedicated mining as well as the remote mining
class MineralMind:
    """
    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    :type targets: control.targets.TargetMind
    """

    def __init__(self, room):
        self.room = room
        self.hive = room.hive_mind
        self.targets = self.hive.target_mind
        self.storage = room.room.storage
        self.terminal = room.room.terminal
        self._has_no_terminal_or_storage = not (self.terminal and self.storage
                                                and self.terminal.isActive() and self.storage.isActive())
        if self.has_no_terminal_or_storage():
            return
        self._target_mineral_counts = None
        self._total_resource_counts = None
        self._next_mineral_to_empty = None
        self._removing_from_terminal = None
        self._adding_to_terminal = None
        self._my_mineral_deposit_minerals = None
        self._labs = None
        self._needed_in_lab1 = None
        self._needed_in_lab2 = None
        self._energy_needed_in_labs = None
        if 'market' not in room.mem:
            # Memory format:
            # market: {
            #     total_energy_needed: TARGET_TERMINAL_ENERGY,
            #     fulfilling: { ... },
            # }
            room.mem.market = {'total_energy_needed': 0, 'fulfilling': {}}
        else:
            if 'total_energy_needed' not in room.mem.market:
                room.mem.market.total_energy_needed = 0
            if 'fulfilling' not in room.mem.market:
                # Memory format:
                # fulfilling: {
                #     RESOURCE_TYPE: [
                #         # Market order
                #         { order_id: ORDER_ID, room: ROOM_NAME, amount: AMOUNT },
                #         # Player-made trade
                #         { room: ROOM_NAME, amount: AMOUNT },
                #         ...
                #     ],
                #     ...
                # }
                room.mem.market.fulfilling = {}
        self.mem = room.mem.market
        self.fulfilling = self.mem.fulfilling
        if 'last_sold' not in self.mem:
            self.mem.last_sold = {}
        if 'last_sold_at' not in self.mem:
            self.mem.last_sold_at = {}

    def has_no_terminal_or_storage(self):
        return self._has_no_terminal_or_storage
        # return not (self.terminal and self.storage and self.terminal.isActive() and self.storage.isActive())

    def note_mineral_hauler(self, name):
        self.room.mem.mineral_hauler = name

    def send_minerals(self, target_room, mineral, amount):
        self.fulfill_market_order(target_room, mineral, amount, None)

    def fill_order(self, order_id, target_amount=Infinity):
        info = Game.market.getOrderById(order_id)
        if not info:
            self.log("WARNING: Tried to fill market order which didn't exit: {}".format(order_id))
            return
        if info.type != ORDER_BUY:
            self.log("WARNING: Tried to fill market order... which was a sell order. ({})".format(order_id))
            return
        mineral = info.resourceType
        target_room = info.roomName
        amount = min(target_amount, info.amount)
        return self.fulfill_market_order(target_room, mineral, amount, order_id)

    def fulfill_market_order(self, target_room, mineral, amount, order_id=None):
        energy_cost = Game.market.calcTransactionCost(min(_SINGLE_MINERAL_FULFILLMENT_MAX, amount),
                                                      self.room.room_name, target_room)
        if energy_cost > self.mem['total_energy_needed']:
            self.mem['total_energy_needed'] = energy_cost
        self.mem['total_energy_needed'] += energy_cost  # TODO: re-calc this every so often.
        if order_id:
            obj = {
                'order_id': order_id,
                'room': target_room,
                'amount': amount,
            }
        else:
            obj = {
                'room': target_room,
                'amount': amount,
            }
        if mineral in self.fulfilling:
            self.fulfilling[mineral].push(obj)
        else:
            self.fulfilling[mineral] = [obj]
        self.log("Now fulfilling: Order for {} {}, sent to {}!".format(amount, mineral, target_room))

    def recalculate_energy_needed(self):
        energy_needed = 0
        for order_list in _.values(self.fulfilling):
            for order in order_list:
                amount = min(_SINGLE_MINERAL_FULFILLMENT_MAX, order.amount)
                energy_needed = max(energy_needed,
                                    Game.market.calcTransactionCost(amount, self.room.room_name, order.room))
        self.mem['total_energy_needed'] = energy_needed

    def log(self, message):
        print("[{}][market] {}".format(self.room.room_name, message))

    def get_mineral_hauler(self):
        return Game.creeps[self.room.mem.mineral_hauler]

    def mineral_hauler_carry(self):
        hauler = self.get_mineral_hauler()
        if hauler:
            return hauler.carry
        else:
            return {}

    def my_mineral_deposit_minerals(self):
        if not self._my_mineral_deposit_minerals:
            result = []
            for deposit in self.room.find(FIND_MINERALS):
                if _.find(self.room.look_at(LOOK_STRUCTURES, deposit),
                          {'my': True, 'structureType': STRUCTURE_EXTRACTOR}):
                    result.append(deposit.mineralType)
            self._my_mineral_deposit_minerals = result
        return self._my_mineral_deposit_minerals

    def get_all_terminal_targets(self):
        if self._target_mineral_counts:
            return self._target_mineral_counts
        target_counts = {}

        counts = self.get_total_room_resource_counts()
        for rtype, have in _.pairs(counts):
            if have > 0:
                target = self._terminal_target_for_resource(rtype, have)
                if target > 0:
                    target_counts[rtype] = min(target, have)
        if _.sum(target_counts) == target_counts[RESOURCE_ENERGY]:
            target_counts = {}
        self._target_mineral_counts = target_counts
        return target_counts

    def removing_from_terminal(self):
        if self._removing_from_terminal is None:
            removing = []
            for resource in Object.keys(self.terminal.store):
                target = self.get_all_terminal_targets()[resource] or 0
                if self.terminal.store[resource] > target:
                    removing.append([resource, self.terminal.store[resource] - target])
            self._removing_from_terminal = removing
        return self._removing_from_terminal

    def adding_to_terminal(self):
        if self._adding_to_terminal is None:
            adding = []
            for resource, target in self.get_all_terminal_targets().items():
                current = self.terminal.store[resource] or 0
                if current < target:
                    adding.append([resource, target - current])
            self._adding_to_terminal = adding
        return self._adding_to_terminal

    def labs(self):
        if self._labs is None:
            self._labs = _.filter(self.room.find(FIND_MY_STRUCTURES), {'structureType': STRUCTURE_LAB})
        return self._labs

    def amount_needed_in_lab1(self):
        if self._needed_in_lab1 is None:
            mineral = self.get_lab_target_mineral()
            if mineral is None:
                return 0
            all_labs = _(self.labs())
            labs = all_labs.filter(lambda x: x.mineralType == mineral)
            if not labs.size():
                labs = all_labs.filter(lambda x: not x.mineralAmount)
            capacity = labs.sum('mineralCapacity')
            filled = labs.sum('mineralAmount')
            empty = capacity - filled
            available = self.get_total_room_resource_counts()[mineral] - filled
            self._needed_in_lab1 = min(empty, available)
        return self._needed_in_lab1

    def amount_needed_in_lab2(self):
        if self._needed_in_lab2 is None:
            mineral = self.get_lab2_target_mineral()
            if mineral is None:
                return 0
            all_labs = _(self.labs())
            labs = all_labs.filter(lambda x: x.mineralType == mineral)
            if not labs.size():
                labs = all_labs.filter(lambda x: not x.mineralAmount)
            capacity = labs.sum('mineralCapacity')
            filled = labs.sum('mineralAmount')
            empty = capacity - filled
            available = self.get_total_room_resource_counts()[mineral] - filled
            self._needed_in_lab2 = min(empty, available)
        return self._needed_in_lab2

    def energy_needed_in_labs(self):
        if self._energy_needed_in_labs is None:
            mineral = self.get_lab_target_mineral()
            if mineral is None:
                return 0
            labs = _(self.labs()).filter('mineralAmount')
            capacity = labs.sum('energyCapacity')
            filled = labs.sum('energy')
            empty = capacity - filled
            available = self.get_total_room_resource_counts()[RESOURCE_ENERGY] - filled
            self._energy_needed_in_labs = min(empty, available)
        return self._energy_needed_in_labs

    def get_lab_target_mineral(self):
        mineral = "XKHO2"
        if _.find(self.labs(), lambda l: l.mineralType == mineral or not l.mineralType) \
                and self.get_total_room_resource_counts()[mineral]:
            return mineral
        return None

    def get_lab2_target_mineral(self):
        mineral = "XLHO2"
        if _.find(self.labs(), lambda l: l.mineralType == mineral or not l.mineralType) \
                and self.get_total_room_resource_counts()[mineral]:
            return mineral
        return None

    def get_total_room_resource_counts(self):
        # TODO: store hauler name from last tick in memory, and use it instead of a passed argument
        if self._total_resource_counts:
            return self._total_resource_counts
        counts = {}
        for rtype, amount in _.pairs(self.storage.store):
            if rtype in counts:
                counts[rtype] += amount
            else:
                counts[rtype] = amount
        for rtype, amount in _.pairs(self.terminal.store):
            if rtype in counts:
                counts[rtype] += amount
            else:
                counts[rtype] = amount
        creep_carry = self.mineral_hauler_carry()
        for rtype, amount in _.pairs(creep_carry):
            if rtype in counts:
                counts[rtype] += amount
            else:
                counts[rtype] = amount
        for lab in self.room.find(FIND_MY_STRUCTURES):
            if lab.structureType == STRUCTURE_LAB:
                if lab.mineralAmount:
                    if lab.mineralType in counts:
                        counts[lab.mineralType] += lab.mineralAmount
                    else:
                        counts[lab.mineralType] = lab.mineralAmount
                if lab.energy:
                    if RESOURCE_ENERGY in counts:
                        counts[RESOURCE_ENERGY] += lab.energy
                    else:
                        counts[RESOURCE_ENERGY] = lab.energy
        self._total_resource_counts = counts
        return counts

    def sell_orders_by_mineral(self):
        vmem = volatile_cache.mem("market")
        if vmem.has("grouped_sell_orders"):
            return vmem.get("grouped_sell_orders")[self.room.room_name] or {}
        else:
            all_sell_orders = {}
            for order in _.values(Game.market.orders):
                if order.type == ORDER_SELL:
                    if order.roomName in all_sell_orders:
                        room_orders = all_sell_orders[order.roomName]
                    else:
                        room_orders = all_sell_orders[order.roomName] = {}
                    if order.resourceType in room_orders:
                        room_orders[order.resourceType].push(order)
                    else:
                        room_orders[order.resourceType] = [order]
            vmem.set("grouped_sell_orders", all_sell_orders)
            return all_sell_orders[self.room.room_name] or {}

    def _terminal_target_for_resource(self, mineral, currently_have):
        if mineral == RESOURCE_ENERGY:
            if currently_have < 20000:
                return 0
            elif currently_have <= 30000:
                return currently_have - 20000
            if self.room.mem.empty_to:
                min_via_empty_to = self.find_emptying_mineral_and_cost()[1]
            else:
                min_via_empty_to = 0
            min_via_fulfillment = self.mem['total_energy_needed']
            return min(currently_have - 20000, max(10000, min_via_empty_to, min_via_fulfillment))
        elif mineral == self.get_lab_target_mineral() or mineral == self.get_lab2_target_mineral():
            return 0
        else:
            if self.my_mineral_deposit_minerals().includes(mineral):
                return min(currently_have, _SINGLE_MINERAL_FULFILLMENT_MAX * 2)

            fulfilling = self.fulfilling[mineral]
            if fulfilling and len(fulfilling):
                return min(_SINGLE_MINERAL_FULFILLMENT_MAX, _.sum(fulfilling, 'amount'))

            sell_orders = self.sell_orders_by_mineral()[mineral]
            if sell_orders and len(sell_orders):
                biggest_order = 0
                for order in sell_orders:
                    if order.amountRemaining > biggest_order:
                        biggest_order = order.amountRemaining
                return biggest_order

            if currently_have >= 1000 and (mineral != RESOURCE_POWER or self.room.mem.empty_to):
                return 1000 * min(math.floor(currently_have / 1000), 20)
            else:
                return 0

    def tick_terminal(self):
        if self.has_no_terminal_or_storage() or (Game.cpu.bucket < 4300 and not (Game.time % 1020 == 8
                                                                                 or Game.time % 765 == 3
                                                                                 or Game.time % 595 == 15)):
            return
        split = Game.time % 85
        if split == 8 and not _.isEmpty(self.fulfilling):
            self.run_fulfillment()
        elif split == 3 and len(self.my_mineral_deposit_minerals()):
            self.check_orders()
        elif split == 15 and 'empty_to' in self.room.mem:
            self.run_emptying_terminal()

    def find_emptying_mineral_and_cost(self):
        if self._next_mineral_to_empty is None:
            energy = self.terminal.store.energy
            minerals = _.sum(self.terminal.store) - energy

            if minerals > 1000 or _.sum(self.storage.store) == self.storage.store.energy:
                mineral_chosen = _.find(Object.keys(self.terminal.store),
                                        lambda r: r != RESOURCE_ENERGY and self.terminal.store[r] >= 100)
                if not mineral_chosen:
                    return
                amount = self.terminal.store[mineral_chosen]
                cost = Game.market.calcTransactionCost(amount, self.room.room_name, self.room.mem.empty_to)
                self._next_mineral_to_empty = mineral_chosen, cost
            else:
                self._next_mineral_to_empty = None, 0
        return self._next_mineral_to_empty

    def run_emptying_terminal(self):
        energy = self.terminal.store.energy
        mineral, cost = self.find_emptying_mineral_and_cost()
        if energy < cost:
            return

        self.terminal.send(mineral, self.terminal.store[mineral], self.room.mem.empty_to,
                           "Emptying to {}".format(self.room.mem.empty_to))

    def run_fulfillment(self):
        self.log("Running fulfillment for {} minerals.".format(len(self.fulfilling)))
        vmem = volatile_cache.mem("market")
        for mineral in Object.keys(self.fulfilling):
            if mineral in self.terminal.store:
                target_list = self.fulfilling[mineral]
                if not len(target_list):
                    del self.fulfilling[mineral]
                    continue
                if vmem.get("market_orders_executed") >= 10:
                    break
                for target in target_list:
                    held = self.terminal.store[mineral]
                    if held >= 1000 or held >= target.amount:
                        result = self.fulfill_now(mineral, target)
                        if result == OK:
                            if vmem.has("market_orders_executed"):
                                vmem.set("market_orders_executed", vmem.get("market_orders_executed") + 1)
                            else:
                                vmem.set("market_orders_executed", 1)
                            break
            elif not self.my_mineral_deposit_minerals().includes(mineral):
                if len(self.fulfilling[mineral]):
                    self.log("Used up all of our {}: removing {} remaining orders!".format(
                        mineral, len(self.fulfilling[mineral])))
                del self.fulfilling[mineral]

    def fulfill_now(self, mineral, target_obj):
        if self.terminal.store[mineral] < 1000:
            self.log("WARNING: fulfill_now() called with mineral: {}, target: {},"
                     "but {} < {}".format(mineral, JSON.stringify(target_obj), self.terminal.store[mineral], 1000))
            return ERR_NOT_ENOUGH_RESOURCES
        amount = min(target_obj.amount, _SINGLE_MINERAL_FULFILLMENT_MAX, self.terminal.store[mineral])
        energy_cost = Game.market.calcTransactionCost(amount, self.room.room_name, target_obj.room)
        if self.terminal.store[RESOURCE_ENERGY] < energy_cost:
            return ERR_NOT_ENOUGH_RESOURCES
        if 'order_id' in target_obj:
            result = Game.market.deal(target_obj.order_id, amount, self.room.room_name)
        else:
            result = self.terminal.send(mineral, amount, target_obj.room,
                                        "Fulfilling order for {} {}".format(target_obj.amount, mineral))
        if result == OK:
            if amount < target_obj.amount:
                target_obj.amount -= amount
                self.log("Sent {} {} to {} successfully, {} left to go.".format(
                    amount, mineral, target_obj.room, target_obj.amount))
            else:
                target_index = self.fulfilling[mineral].indexOf(target_obj)
                if target_index < 0:
                    self.log("ERROR: Couldn't find indexOf target fulfillment {} for mineral {} in room {}"
                             .format(JSON.stringify(target_obj), mineral, self.room.room_name))
                self.fulfilling[mineral].splice(target_index, 1)
                if not len(self.fulfilling[mineral]):
                    del self.fulfilling[mineral]
                self.log("Sent {} {} to {} successfully, finishing the transaction.".format(
                    amount, mineral, target_obj.room))
            self.recalculate_energy_needed()
        else:
            if 'order_id' in target_obj:
                if result == ERR_INVALID_ARGS:
                    self.log('Removing market deal {} (send {} {} to {}): executed by another player.'
                             .format(target_obj.order_id, target_obj.amount, mineral, target_obj.room))
                    target_index = self.fulfilling[mineral].indexOf(target_obj)
                    if target_index < 0:
                        self.log("ERROR: Couldn't find indexOf target fulfillment {} for mineral {} in room {}"
                                 .format(JSON.stringify(target_obj), mineral, self.room.room_name))
                    self.fulfilling[mineral].splice(target_index, 1)
                    if not len(self.fulfilling[mineral]):
                        del self.fulfilling[mineral]
                else:
                    self.log("ERROR: Unknown result from Game.market.deal({}, {}, {}): {}".format(
                        target_obj.order_id, amount, self.room.room_name, result))
            else:
                self.log("ERROR: Unknown result from {}.send({}, {}, {}, {}): {}".format(
                    self.terminal, mineral, amount, self.room.room_name,
                    "'Fulfilling order for {} {}'".format(target_obj.amount, mineral), result))
        return result

    def check_orders(self):
        for mineral in self.my_mineral_deposit_minerals():
            if (mineral in self.fulfilling and len(self.fulfilling[mineral])) \
                    or (self.get_total_room_resource_counts()[mineral] or 0) < _SINGLE_MINERAL_FULFILLMENT_MAX:
                continue
            current_sell_orders = self.sell_orders_by_mineral()[mineral]
            if current_sell_orders:
                current_sell_orders = _.filter(current_sell_orders, {"roomName": self.room.room_name})
            if current_sell_orders and len(current_sell_orders):
                to_check = _.min(current_sell_orders, 'price')
                self.mem.last_sold_at[mineral] = to_check.price
                if to_check.remainingAmount < _SINGLE_MINERAL_FULFILLMENT_MAX:
                    if to_check.remainingAmount <= 100:
                        # TODO: duplicated when creating a new order.
                        if mineral in self.mem.last_sold_at:
                            price = min(max(1.0, sell_at_prices[mineral] - 1.5, self.mem.last_sold_at[mineral] + 0.1),
                                        sell_at_prices[mineral])
                        else:
                            price = sell_at_prices[mineral]
                        self.log("Increasing price on sell order for {} from {} to {}.".format(
                            mineral, to_check.price, price))
                        Game.market.changeOrderPrice(to_check.id, price)
                        Game.market.extendOrder(to_check.id, _SINGLE_MINERAL_FULFILLMENT_MAX
                                                - to_check.remainingAmount)
                    else:
                        self.log("Extending sell order for {} at price {} from {} to {} minerals."
                                 .format(mineral, to_check.price, to_check.remainingAmount,
                                         _SINGLE_MINERAL_FULFILLMENT_MAX))
                        Game.market.extendOrder(to_check.id, _SINGLE_MINERAL_FULFILLMENT_MAX - to_check.remainingAmount)
                    self.mem.last_sold[mineral] = Game.time
                elif self.mem.last_sold[mineral] < Game.time - 10000 and to_check.price \
                        > bottom_prices[mineral] + 0.01:  # market prices can't always be changed to an exact precision
                    new_price = max(bottom_prices[mineral], to_check.price - 0.1)
                    self.log("Reducing price on sell order for {} from {} to {}"
                             .format(mineral, to_check.price, new_price))
                    Game.market.changeOrderPrice(to_check.id, new_price)
                    self.mem.last_sold[mineral] = Game.time
                elif to_check.price < bottom_prices[mineral]:
                    self.log("Increasing price on sell order for {} from {} to {}"
                             .format(mineral, to_check.price, bottom_prices[mineral]))
                    Game.market.changeOrderPrice(to_check.id, bottom_prices[mineral])
            elif mineral in sell_at_prices and Game.market.credits >= 0.05 * _SINGLE_MINERAL_FULFILLMENT_MAX \
                    * sell_at_prices[mineral] and len(Game.market.orders) < 50:
                if mineral in self.mem.last_sold_at:
                    price = min(max(1.0, sell_at_prices[mineral] - 1.5, self.mem.last_sold_at[mineral] + 0.1),
                                sell_at_prices[mineral])
                else:
                    price = sell_at_prices[mineral]
                self.log("Creating new sell order for {} {} at {} credits/{}".format(
                    _SINGLE_MINERAL_FULFILLMENT_MAX, mineral, price, mineral))
                Game.market.createOrder(ORDER_SELL, mineral, price,
                                        _SINGLE_MINERAL_FULFILLMENT_MAX, self.room.room_name)
                self.mem.last_sold[mineral] = Game.time

    def place_container_construction_site(self, deposit):
        # TODO: finding in range is duplicated below (in method which calls this)
        # TODO: should this be part of ConstructionMind?
        if deposit.pos:
            pos = deposit.pos
        else:
            pos = deposit

        # TODO: this will break if there are 5 containers which aren't next to the mineral.

        for x in range(pos.x - 1, pos.x + 2):
            for y in range(pos.y - 1, pos.y + 2):
                if movement.is_block_clear(self.room, x, y) \
                        and not _.find(self.room.look_at(LOOK_CONSTRUCTION_SITES, x, y),
                                       lambda s: s.structureType == STRUCTURE_CONTAINER) \
                        and not _.find(self.room.look_at(LOOK_STRUCTURES, x, y),
                                       lambda s: s.structureType == STRUCTURE_CONTAINER):
                    result = self.room.room.createConstructionSite(x, y, STRUCTURE_CONTAINER)
                    if result == OK:
                        return
                    else:
                        self.log("WARNING: Unknown result from {}.createConstructionSite({}, {}, {}): {}"
                                 .format(self.room.room, x, y, STRUCTURE_CONTAINER, result))

        self.log("WARNING: Couldn't find any open spots to place a container near {}".format(pos))

    def get_target_mineral_miner_count(self):
        if self.has_no_terminal_or_storage() or self.room.mem.empty_to:
            return 0
        # TODO: cache this
        mineral = self.room.find(FIND_MINERALS)[0]
        if mineral and mineral.mineralAmount > 0 and _.find(self.room.look_at(LOOK_STRUCTURES, mineral),
                                                            {'my': True, 'structureType': STRUCTURE_EXTRACTOR}):
            have_now = self.get_total_room_resource_counts()
            if _.sum(have_now) - (have_now[RESOURCE_ENERGY] or 0) >= 400000:
                return 0
            container = _.find(self.room.find_in_range(FIND_STRUCTURES, 2, mineral),
                               lambda s: s.structureType == STRUCTURE_CONTAINER)
            if container:
                return 1
            else:
                container_site = _.find(self.room.find_in_range(FIND_MY_CONSTRUCTION_SITES, 2, mineral),
                                        lambda s: s.structureType == STRUCTURE_CONTAINER)
                if not container_site:
                    self.place_container_construction_site(mineral)
        return 0

    def get_target_mineral_hauler_count(self):
        if self.has_no_terminal_or_storage():
            return 0
        elif self.get_target_mineral_miner_count() or len(self.adding_to_terminal()) or self.energy_needed_in_labs() \
                or self.amount_needed_in_lab1() or self.amount_needed_in_lab2():
            # We don't really need to be spawning a new mineral hauler if we only need to remove things from the
            # terminal, and not add them.
            # or len(self.removing_from_terminal()):
            return 1
        else:
            return 0

    def mineral_report(self):
        minstrings = []
        for mineral, amount in _.pairs(self.get_total_room_resource_counts()):
            if mineral == RESOURCE_ENERGY:
                continue
            minstrings.append("{} {}".format(amount, mineral))
        orderstrings = []
        for mineral, target_list in _.pairs(self.fulfilling):
            for order in target_list:
                if order.order_id:
                    orderstrings.push("a market order {} for {} {} to {}".format(
                        order.order_id, order.amount, mineral, order.room))
                else:
                    orderstrings.push("an order for {} {} to {}".format(
                        order.amount, mineral, order.room))
        if len(minstrings):
            if len(orderstrings):
                return "{} has {}, and is fulfilling {}".format(
                    self.room.room_name, ', '.join(minstrings), ', '.join(orderstrings))
            else:
                return "{} has {}".format(self.room.room_name, ', '.join(minstrings))
        elif len(orderstrings):
            return "{} is empty, and is fulfilling {}".format(self.room.room_name, ', '.join(orderstrings))
        else:
            return "{} is empty."

__pragma__('nofcall')

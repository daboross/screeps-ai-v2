import math

from utilities import movement
from utilities import volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

_SINGLE_MINERAL_FULFILLMENT_MAX = 50 * 1000

sell_at_prices = {
    RESOURCE_OXYGEN: 1.0,
    RESOURCE_HYDROGEN: 2.1,
    RESOURCE_ZYNTHIUM: 2.3,
    RESOURCE_UTRIUM: 2.4,
    RESOURCE_LEMERGIUM: 2.5,
}
bottom_prices = {
    RESOURCE_OXYGEN: 0.55,
    RESOURCE_HYDROGEN: 0.55,
    RESOURCE_ZYNTHIUM: 0.95,
    RESOURCE_UTRIUM: 1.05,
    RESOURCE_LEMERGIUM: 1.05,
}


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
        self._target_mineral_counts = None
        self._total_resource_counts = None
        self._next_mineral_to_empty = None
        self._removing_from_terminal = None
        self._adding_to_terminal = None
        self._my_mineral_deposit_minerals = None
        if 'market' not in room.mem:
            # Memory format:
            # market: {
            #     total_energy_needed: TARGET_TERMINAL_ENERGY,
            #     fulfilling: { ... },
            # }
            room.mem.market = {'total_energy_needed': 0}
        elif 'total_energy_needed' not in room.mem.market:
            room.mem.market.total_energy_needed = 0
        self.mem = room.mem.market
        if 'fulfilling' not in self.mem:
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
        self.fulfilling = self.mem.fulfilling
        if 'last_sold' not in self.mem:
            self.mem.last_sold = {}
        if 'last_sold_at' not in self.mem:
            self.mem.last_sold_at = {}

    def has_no_terminal_or_storage(self):
        return not (self.terminal and self.storage and self.terminal.isActive() and self.storage.isActive())

    def note_mineral_hauler(self, name):
        self.room.mem.mineral_hauler = name

    def fulfill_market_order(self, target_room, mineral, amount, order_id=None):
        energy_cost = Game.market.calcTransactionCost(amount, self.room.room_name, target_room)
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
                if _.find(self.room.find_at(FIND_MY_STRUCTURES, deposit), {'structureType': STRUCTURE_EXTRACTOR}):
                    result.append(deposit.mineralType)
            self._my_mineral_deposit_minerals = result
        return self._my_mineral_deposit_minerals

    def get_all_terminal_targets(self):
        if self._target_mineral_counts:
            return self._target_mineral_counts
        target_counts = {}

        counts = self.get_total_room_resource_counts()
        for rtype in Object.keys(counts):
            target = self._terminal_target_for_resource(rtype)
            if target > 0:
                target_counts[rtype] = target
        if _.sum(target_counts) == target_counts[RESOURCE_ENERGY]:
            target_counts = {}
        self._target_mineral_counts = target_counts
        return target_counts

    def removing_from_terminal(self):
        if self._removing_from_terminal is None:
            removing = []
            for resource in Object.keys(self.terminal.store):
                target = self._terminal_target_for_resource(resource)
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

    def get_total_room_resource_counts(self):
        # TODO: store hauler name from last tick in memory, and use it instead of a passed argument
        if self._total_resource_counts:
            return self._total_resource_counts
        counts = {}
        for rtype in Object.keys(self.storage.store):
            if rtype in counts:
                counts[rtype] += self.storage.store[rtype]
            else:
                counts[rtype] = self.storage.store[rtype]
        for rtype in Object.keys(self.terminal.store):
            if rtype in counts:
                counts[rtype] += self.terminal.store[rtype]
            else:
                counts[rtype] = self.terminal.store[rtype]
        creep_carry = self.mineral_hauler_carry()
        for rtype in Object.keys(creep_carry):
            if rtype in counts:
                counts[rtype] += creep_carry[rtype]
            else:
                counts[rtype] = creep_carry[rtype]
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

    def _terminal_target_for_resource(self, mineral):
        if mineral == RESOURCE_POWER and not self.room.mem.empty_to:
            return 0
        elif mineral == RESOURCE_ENERGY:
            minimum = max(0, min(10000, self.storage.store.energy - 20000))
            min_via_target = (self.room.mem.target_terminal_energy or 0)
            if self.room.mem.empty_to:
                min_via_empty_to = self.find_emptying_mineral_and_cost()[1]
            else:
                min_via_empty_to = 0
            min_via_fulfillment = self.mem['total_energy_needed']
            return max(minimum, min_via_target, min_via_empty_to, min_via_fulfillment)
        else:
            total_counts = self.get_total_room_resource_counts()
            if mineral in total_counts and total_counts[mineral] >= 1000:
                target_amount = 1000 * min(math.floor(total_counts[mineral] / 1000), 20)
            else:
                target_amount = 0
            fulfilling = self.fulfilling[mineral]
            if fulfilling and len(fulfilling):
                fulfilment_target = 0
                for obj in fulfilling:
                    fulfilment_target += obj.amount
                target_amount += min(fulfilment_target, _SINGLE_MINERAL_FULFILLMENT_MAX)

            sell_orders = self.sell_orders_by_mineral()
            if sell_orders and mineral in sell_orders:
                biggest_order = 0
                for order in sell_orders[mineral]:
                    if order.amountRemaining > biggest_order:
                        biggest_order = order.amountRemaining
                target_amount += _.max(sell_orders[mineral], 'remainingAmount').remainingAmount

            if mineral in self.my_mineral_deposit_minerals():
                target_amount = max(target_amount, min(self.get_total_room_resource_counts()[mineral] or 0,
                                                       _SINGLE_MINERAL_FULFILLMENT_MAX * 2))

            return min(target_amount, total_counts[mineral])

    def tick_terminal(self):
        if self.has_no_terminal_or_storage() or Game.cpu.bucket < 4300:
            return
        if self.room.mem.empty_to:
            self.run_emptying_terminal()
        split = Game.time % 17
        if split == 8 and not _.isEmpty(self.fulfilling):
            self.run_fulfillment()
        elif split == 3 and len(self.my_mineral_deposit_minerals()):
            self.check_orders()

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
        for mineral, target_list in _.pairs(self.fulfilling):
            if not len(target_list):
                del self.fulfilling[mineral]
                continue
            vmem = volatile_cache.mem("market")
            if vmem.has("market_orders_executed") and vmem.get("market_orders_executed") >= 10:
                break
            if mineral in self.terminal.store:
                for target in target_list:
                    if self.terminal.store[mineral] >= min(target.amount, _SINGLE_MINERAL_FULFILLMENT_MAX):
                        result = self.fulfill_now(mineral, target)
                        if result == OK:
                            if vmem.has("market_orders_executed"):
                                vmem.set("market_orders_executed", vmem.get("market_orders_executed") + 1)
                            else:
                                vmem.set("market_orders_executed", 1)
                            break

    def fulfill_now(self, mineral, target_obj):
        amount = min(target_obj.amount, _SINGLE_MINERAL_FULFILLMENT_MAX)
        if self.terminal.store[mineral] < amount:
            self.log("WARNING: fulfill_now() called with mineral: {}, target: {},"
                     "but {} < {}".format(mineral, JSON.stringify(target_obj),
                                          self.terminal.store[mineral], amount))
            return ERR_NOT_ENOUGH_RESOURCES
        energy_cost = Game.market.calcTransactionCost(amount, self.room.room_name, target_obj.room)
        if self.terminal.store[RESOURCE_ENERGY] < energy_cost:
            return ERR_NOT_ENOUGH_RESOURCES
        if 'order_id' in target_obj:
            result = Game.market.deal(target_obj.order_id, amount, self.room.room_name)
        else:
            result = self.terminal.send(mineral, amount, target_obj.room,
                                        "Fulfilling order for {} {}".format(target_obj.amount, mineral))
        if result == OK:
            self.mem['total_energy_needed'] -= energy_cost  # TODO: re-calc this every so often.
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
                self.log("Sent {} {} to {} successfully, finishing the transaction.".format(
                    amount, mineral, target_obj.room))
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
                    self.log("Extending sell order for {} at price {} from {} to {} minerals."
                             .format(mineral, to_check.price, to_check.remainingAmount,
                                     _SINGLE_MINERAL_FULFILLMENT_MAX))
                    Game.market.extendOrder(to_check.id, _SINGLE_MINERAL_FULFILLMENT_MAX - to_check.remainingAmount)
                    self.mem.last_sold[mineral] = Game.time
                elif self.mem.last_sold[mineral] < Game.time - 1000 and to_check.price \
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

    def make_container_construction_sites(self, deposit):
        # TODO: finding in range is duplicated below (in method which calls this)
        # TODO: should this be part of ConstructionMind?
        if deposit.pos:
            pos = deposit.pos
        else:
            pos = deposit
        existing_pos = []
        for c in self.room.find_in_range(FIND_STRUCTURES, 2, pos):
            if c.structureType == STRUCTURE_CONTAINER:
                existing_pos.append(c.pos)
        for c in self.room.find_in_range(FIND_MY_CONSTRUCTION_SITES, 2, pos):
            if c.structureType == STRUCTURE_CONTAINER:
                existing_pos.append(c.pos)

        # TODO: this will break if there are 4 or more containers which aren't next to the mineral.

        for x in range(pos.x - 1, pos.x + 2):
            for y in range(pos.y - 1, pos.y + 2):
                if len(existing_pos) >= 2:
                    break
                if len(existing_pos) == 1 and not (abs(existing_pos[0].x - x) <= 1
                                                   and abs(existing_pos[1].y - y) <= 1):
                    continue
                if movement.is_block_clear(self.room, x, y):
                    self.room.room.createConstructionSite(x, y, STRUCTURE_CONTAINER)
                    existing_pos.append(__new__(RoomPosition(x, y, self.room.room_name)))
            else:
                continue
            break
        if len(existing_pos) < 2:
            if len(existing_pos) < 1:
                self.log("WARNING: Couldn't find any open spots to place a container near {}".format(pos))
                return  # no possibility here
            if not existing_pos[0].isNearTo(pos):
                self.log("WARNING: Only existing container isn't near to the mineral, and no clear places near to the"
                         "mineral could be found (pos: {}).".format(pos))
                return
            for x in range(existing_pos[0].x - 1, existing_pos[0].x + 1):
                for y in range(existing_pos[0].y - 1, existing_pos[0].y + 1):
                    if (x != existing_pos[0].x or y != existing_pos[0].y) and movement.is_block_clear(self.room, x, y):
                        self.room.room.createConstructionSite(x, y, STRUCTURE_CONTAINER)
                        break
                else:
                    continue
                break
            else:
                self.log("WARNING: No open site found to place second container near first container at {}"
                         " (deposit at {})".format(existing_pos[0], pos))

    def get_target_mineral_miner_count(self):
        if self.has_no_terminal_or_storage() or self.room.mem.empty_to:
            return 0
        # TODO: cache this
        mineral = self.room.find(FIND_MINERALS)[0]
        if mineral and mineral.mineralAmount > 0 and _.find(self.room.find_at(FIND_MY_STRUCTURES, mineral),
                                                            {'structureType': STRUCTURE_EXTRACTOR}):
            have_now = self.get_total_room_resource_counts()
            if _.sum(have_now) - (have_now[RESOURCE_ENERGY] or 0) >= 400000:
                return 0
            containers = self.room.find_in_range(FIND_STRUCTURES, 2, mineral)
            if len(containers) < 2:
                construction_sites = _.sum(self.room.find_in_range(FIND_MY_CONSTRUCTION_SITES, 2, mineral),
                                           lambda s: s.structureType == STRUCTURE_CONTAINER)
                more_needed = 2 - (len(containers) + construction_sites)
                if more_needed > 0:
                    self.make_container_construction_sites(mineral)
            if len(containers):
                return 1
        return 0

    def get_target_mineral_hauler_count(self):
        if self.has_no_terminal_or_storage():
            return 0
        elif self.get_target_mineral_miner_count() or len(self.adding_to_terminal()):
            # We don't really need to be spawning a new mineral hauler if we only need to remove things from the
            # terminal, and not add them.
            # or len(self.removing_from_terminal()):
            return 1
        else:
            return 0

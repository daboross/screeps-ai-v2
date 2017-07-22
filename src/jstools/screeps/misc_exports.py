from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

_HasPosition = Union['RoomPosition', 'RoomObject']
_FindParameter = Union[int, List[_HasPosition]]


# noinspection PyPep8Naming
class RoomPosition:
    """
    :type x: int
    :type y: int
    :type roomName: str
    :type prototype: Type[RoomPosition]
    # used for the common (pos.pos or pos).. trick for accepting RoomObject and RoomPosition
    """
    prototype = None  # type: Type[RoomPosition]

    def __init__(self, x: int, y: int, roomName: str) -> None:
        self.x = x
        self.y = y
        self.roomName = roomName

    def createConstructionSite(self, structureType: str) -> int:
        pass

    def createFlag(self, name: str = None, color: str = None, secondaryColor: str = None) -> int:
        pass

    def findClosestByPath(self, source: _FindParameter, opts: Dict[str, Any]) -> Optional[RoomObject]:
        pass

    def findClosestByRange(self, source: _FindParameter, opts: Dict[str, Any]) -> Optional[RoomObject]:
        pass

    def findInRange(self, source: _FindParameter, _range: int, opts: Dict[str, Any]) -> List[RoomObject]:
        pass

    def getDirectionTo(self, x: Union[int, 'RoomPosition', RoomObject], y: int = None) -> int:
        pass

    def getRangeTo(self, x: Union[int, 'RoomPosition', RoomObject], y: int = None) -> int:
        pass

    def inRangeTo(self, x: Union[int, 'RoomPosition', RoomObject], y_or_range: int = None,
                  _range: int = None) -> bool:
        pass

    def isEqualTo(self, x: Union[int, 'RoomPosition', RoomObject], y: int = None) -> bool:
        pass

    def isNearTo(self, x: Union[int, 'RoomPosition', RoomObject], y: int = None) -> bool:
        pass

    def look(self) -> List[Dict[str, Any]]:
        pass

    def lookFor(self, _type: str) -> List[RoomObject]:
        pass


RoomPosition.prototype = RoomPosition


class _Owner:
    """
    :type username: str
    """

    def __init__(self, username: str) -> None:
        self.username = username


class _PathPos:
    """
    :type x: int
    :type y: int
    :type dx: int
    :type dy: int
    :type direction: int
    """

    def __init__(self, x: int, y: int, dx: int, dy: int, direction: int) -> None:
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.direction = direction


# noinspection PyPep8Naming
class Room:
    """
    :type controller: StructureController
    :type storage: StructureStorage
    :type terminal: StructureTerminal
    :type energyAvailable: int
    :type energyCapacityAvailable: int
    :type memory: Dict[str, Any]
    :type mode: str
    :type name: str
    :type visual: Any
    """

    def __init__(self, controller: StructureController, storage: StructureStorage, terminal: StructureTerminal,
                 energyAvailable: int, energyCapacityAvailable: int, memory: Dict[str, Any], mode: str,
                 name: str, visual: Any) -> None:
        self.controller = controller
        self.storage = storage
        self.terminal = terminal
        self.energyAvailable = energyAvailable
        self.energyCapacityAvailable = energyCapacityAvailable
        self.memory = memory
        self.mode = mode
        self.name = name
        self.visual = visual

    @classmethod
    def serializePath(cls, path: List[Dict[str, Union[_PathPos, Dict[str, Any]]]]) -> str:
        pass

    @classmethod
    def deserializePath(cls, path: str) -> List[Union[_PathPos, Dict[str, Any]]]:
        pass

    def createConstructionSite(self, x: Union[int, RoomPosition, RoomObject], y: Union[int, str],
                               structureType: str = None) -> int:
        pass

    def createFlag(self, pos: Union[RoomPosition, RoomObject], name: str = None, color: int = None,
                   secondaryColor: int = None) -> Union[str, int]:
        pass

    def find(self, _type: _FindParameter, opts: Dict[str, Callable[[RoomObject], bool]] = None) -> List[RoomObject]:
        pass

    def findExitTo(self, room: str) -> int:
        pass

    def findPath(self, fromPos: RoomPosition, toPos: RoomPosition, opts: Dict[str, Any]) \
            -> List[Union[_PathPos, Dict[str, Any]]]:
        pass

    def getPositionAt(self, x: int, y: int) -> RoomPosition:
        pass

    def lookAt(self, x: Union[int, RoomPosition, RoomObject], y: int = None) -> List[Dict[str, Any]]:
        pass

    def lookAtArea(self, top: int, left: int, bottom: int, right: int, asArray: bool = False) \
            -> Union[List[Dict[str, Any]], Dict[int, Dict[int, Dict[str, Any]]]]:
        pass

    def lookForAt(self, _type: str, x: Union[int, RoomPosition, RoomObject], y: int = None) -> List[RoomObject]:
        pass

    def lookForAtArea(self, _type: str, top: int, left: int, bottom: int, right: int, asArray: bool = False) \
            -> Union[List[Dict[str, Any]], Dict[int, Dict[int, Dict[str, Any]]]]:
        pass


class RoomObject:
    """
    :type pos: RoomPosition
    :type room: Room
    """

    def __init__(self, pos: RoomPosition, room: Room) -> None:
        self.pos = pos
        self.room = room


class _CreepPart:
    """
    :type boost: str | None
    :type type: str
    :type hits: int
    """

    def __init__(self, _type: str, hits: int, boost: Optional[str]) -> None:
        self.type = _type
        self.hits = hits
        self.boost = boost


# noinspection PyPep8Naming
class Creep(RoomObject):
    """
    :type body: list[_CreepPart]
    :type carry: dict[str, int]
    :type carryCapacity: int
    :type fatigue: int
    :type hits: int
    :type hitsMax: int
    :type id: str
    :type memory: _Memory
    :type my: bool
    :type name: str
    :type owner: _Owner
    :type saying: Optional[str]
    :type spawning: bool
    :type ticksToLive: int
    """

    def __init__(self, pos: RoomPosition, room: Room, body: List[_CreepPart], carry: Dict[str, int],
                 carryCapacity: int, fatigue: int, hits: int, hitsMax: int, _id: str, memory: _Memory,
                 my: bool, name: str, owner: _Owner, saying: Optional[str], spawning: bool, ticksToLive: int) -> None:
        super().__init__(pos, room)
        self.body = body
        self.carry = carry
        self.carryCapacity = carryCapacity
        self.fatigue = fatigue
        self.hits = hits
        self.hitsMax = hitsMax
        self.id = _id
        self.memory = memory
        self.my = my
        self.name = name
        self.owner = owner
        self.saying = saying
        self.spawning = spawning
        self.ticksToLive = ticksToLive

    def attack(self, target: Union[Structure, 'Creep']) -> int:
        pass

    def attackController(self, target: StructureController) -> int:
        pass

    def build(self, target: ConstructionSite) -> int:
        pass

    def cancelOrder(self, methodName: str) -> int:
        pass

    def claimController(self, target: StructureController) -> int:
        pass

    def dismantle(self, target: Structure) -> int:
        pass

    def drop(self, resourceType: str, amount: int = None) -> int:
        pass

    def generateSafeMode(self, target: StructureController) -> int:
        pass

    def getActiveBodyparts(self, _type: str) -> int:
        pass

    def harvest(self, target: Union[Source, Mineral]):
        pass

    def heal(self, target: 'Creep') -> int:
        pass

    def move(self, direction: int) -> int:
        pass

    def moveByPath(self, path: Union[list, str]) -> int:
        pass

    def moveTo(self, target: RoomPosition, opts: Dict[str, Any]) -> int:
        pass

    def notifyWhenAttacked(self, enabled: bool) -> int:
        pass

    def pickup(self, target: Resource) -> int:
        pass

    def rangedAttack(self, target: Union['Creep', Structure]) -> int:
        pass

    def rangedHeal(self, target: 'Creep') -> int:
        pass

    def rangedMassAttack(self) -> int:
        pass

    def repair(self, target: Structure) -> int:
        pass

    def reserveController(self, target: StructureController) -> int:
        pass

    def say(self, message: str, public: bool = False) -> int:
        pass

    def signController(self, target: StructureController, message: str) -> int:
        pass

    def suicide(self) -> int:
        pass

    def transfer(self, target: Union['Creep', Structure], resourceType: str, amount: int = None) -> int:
        pass

    def upgradeController(self, target: StructureController) -> int:
        pass

    def withdraw(self, target: Structure, resourceType: str, amount: int = None) -> int:
        pass


# noinspection PyPep8Naming
class Flag(RoomObject):
    """
    :type room: Room | None
    :type color: int
    :type secondaryColor: int
    :type memory: dict[str, Any]
    :type name: str
    """

    def __init__(self, pos: RoomPosition, room: Optional[Room], color: int, secondaryColor: int,
                 memory: Dict[str, Any], name: str) -> None:
        super().__init__(pos, room)
        self.color = color
        self.secondaryColor = secondaryColor
        self.memory = memory
        self.name = name

    def remove(self) -> int:
        pass

    def setColor(self, color: int, secondaryColor: int = None) -> int:
        pass

    def setPosition(self, x: Union[int, RoomPosition, RoomObject], y: int = None) -> int:
        pass


# noinspection PyPep8Naming
class Mineral(RoomObject):
    """
    :type density: int
    :type mineralAmount: int
    :type mineralType: str
    :type id: str
    :type ticksToRegeneration: int
    """

    def __init__(self, pos: RoomPosition, room: Optional[Room], density: int, mineralAmount: int, mineralType: str,
                 id: str, ticksToRegeneration: int) -> None:
        super().__init__(pos, room)
        self.density = density
        self.mineralAmount = mineralAmount
        self.mineralType = mineralType
        self.id = id
        self.ticksToRegeneration = ticksToRegeneration


# noinspection PyPep8Naming
class Source(RoomObject):
    """
    :type energy: int
    :type energyCapacity: int
    :type id: str
    :type ticksToRegeneration: int
    """

    def __init__(self, pos: RoomPosition, room: Optional[Room], energy: int, energyCapacity: int, _id: str,
                 ticksToRegeneration: int) -> None:
        super().__init__(pos, room)
        self.energy = energy
        self.energyCapacity = energyCapacity
        self.id = _id
        self.ticksToRegeneration = ticksToRegeneration


# noinspection PyPep8Naming
class Structure(RoomObject):
    """
    :type id: str
    :type structureType: str
    :type hits: int
    :type hitsMax: int
    """

    def __init__(self, pos: RoomPosition, room: Room, structureType: str, _id: str, hits: int, hitsMax: int) -> None:
        super().__init__(pos, room)
        self.structureType = structureType
        self.id = _id
        self.hits = hits
        self.hitsMax = hitsMax

    def destroy(self) -> int:
        pass

    def isActive(self) -> bool:
        pass

    def notifyWhenAttacked(self, enabled: bool) -> int:
        pass


class OwnedStructure(Structure):
    """
    :type my: bool
    :type owner: _Owner
    """

    def __init__(self, pos: RoomPosition, room: Room, structureType: str, _id: str, hits: int, hitsMax: int,
                 my: bool, owner: _Owner) -> None:
        super().__init__(pos, room, structureType, _id, hits, hitsMax)
        self.my = my
        self.owner = owner


# noinspection PyPep8Naming
class ConstructionSite(RoomObject):
    """
    :type id: str
    :type my: bool
    :type owner: _Owner
    :type progress: int
    :type progressTotal: int
    :type structureType: str
    """

    def __init__(self, pos: RoomPosition, room: Room, _id: str, my: bool, owner: _Owner, progress: int,
                 progressTotal: int, structureType: str) -> None:
        super().__init__(pos, room)
        self.id = _id
        self.my = my
        self.owner = owner
        self.progress = progress
        self.progressTotal = progressTotal
        self.structureType = structureType

    def remove(self) -> int:
        pass


# noinspection PyPep8Naming
class _RoomReservation:
    """
    :type username: str
    :type ticksToEnd: int
    """

    def __init__(self, username: str, ticksToEnd: int) -> None:
        self.username = username
        self.ticksToEnd = ticksToEnd


class _ControllerSign:
    """
    :type username: str
    :type text: str
    :type time: int
    :type datetime: Any
    """

    def __init__(self, username: str, text: str, time: int, datetime: Any) -> None:
        self.time = time
        self.text = text
        self.username = username
        self.datetime = datetime


# noinspection PyPep8Naming
class StructureController(OwnedStructure):
    """
    :type level: int
    :type progress: int
    :type progressTotal: int
    :type reservation: _RoomReservation | None
    :type safeMode: int
    :type safeModeAvailable: int
    :type safeModeCooldown: int
    :type sign: _ControllerSign | None
    :type ticksToDowngrade: int
    :type upgradeBlocked: int
    """

    def __init__(self, pos: RoomPosition, room: Room, structureType: str, _id: str, hits: int, hitsMax: int, my: bool,
                 owner: _Owner, level: int, progress: int, progressTotal: int, reservation: Optional[_RoomReservation],
                 safeMode: int, safeModeAvailable: int, safeModeCooldown: int, sign: Optional[_ControllerSign],
                 ticksToDowngrade: int, upgradeBlocked: int) -> None:
        super().__init__(pos, room, structureType, _id, hits, hitsMax, my, owner)
        self.level = level
        self.progress = progress
        self.progressTotal = progressTotal
        self.reservation = reservation
        self.safeMode = safeMode
        self.safeModeAvailable = safeModeAvailable
        self.safeModeCooldown = safeModeCooldown
        self.sign = sign
        self.ticksToDowngrade = ticksToDowngrade
        self.upgradeBlocked = upgradeBlocked

    def activateSafemode(self) -> int:
        pass

    def unclaim(self) -> int:
        pass


# noinspection PyPep8Naming
class StructureStorage(OwnedStructure):
    """
    :type store: dict[str, int]
    :type storeCapacity: int
    """

    def __init__(self, pos: RoomPosition, room: Room, structureType: str, _id: str, hits: int, hitsMax: int,
                 my: bool, owner: _Owner, store: Dict[str, int], storeCapacity: int) -> None:
        super().__init__(pos, room, structureType, _id, hits, hitsMax, my, owner)
        self.store = store
        self.storeCapacity = storeCapacity


# noinspection PyPep8Naming
class StructureTerminal(OwnedStructure):
    """
    :type cooldown: int
    :type store: dict[str, int]
    :type storeCapacity: int
    """

    def __init__(self, pos: RoomPosition, room: Room, structureType: str, _id: str, hits: int, hitsMax: int,
                 my: bool, owner: _Owner, cooldown: int, store: Dict[str, int], storeCapacity: int) -> None:
        super().__init__(pos, room, structureType, _id, hits, hitsMax, my, owner)
        self.cooldown = cooldown
        self.store = store
        self.storeCapacity = storeCapacity

    def send(self, resourceType: str, amount: Union[int, float], destination: str, description: str = None) -> int:
        pass


class StructureSpawn(OwnedStructure):
    """

    """


class Resource(RoomObject):
    """
    :type amount: int
    :type id: str
    :type resourceType: str
    """

    def __init__(self, pos: RoomPosition, room: Room, _id: str, amount: int, resourceType: str) -> None:
        super().__init__(pos, room)
        self.id = _id
        self.amount = amount
        self.resourceType = resourceType


# noinspection PyPep8Naming
class _GameCpu:
    """
    :type limit: int
    :type tickLimit: int
    :type bucket: int
    """

    def __init__(self, limit: int, tickLimit: int, bucket: int) -> None:
        self.limit = limit
        self.tickLimit = tickLimit
        self.bucket = bucket

    def getUsed(self) -> float:
        pass


# noinspection PyPep8Naming
class _GameGcl:
    """
    :type level: int
    :type progress: int
    :type progressTotal: int
    """

    def __init__(self, level: int, progress: int, progressTotal: int) -> None:
        self.level = level
        self.progress = progress
        self.progressTotal = progressTotal


# noinspection PyPep8Naming
class _GameMap:
    def describeExits(self, roomName: str) -> Dict[str, str]:
        pass

    def findExit(self, fromRoom: str, toRoom: str, opts: Dict[str, Any]) -> int:
        pass

    def findRoute(self, fromRoom: str, toRoom: str, opts: Dict[str, Any]) -> List[Dict[str, Union[int, str]]]:
        pass

    def getRoomLinearDistance(self, roomName1: str, roomName2: str, terminalDistance: bool = False) -> int:
        pass

    def getTerrainAt(self, x: Union[int, RoomPosition], y: int = None, roomName: str = None) -> str:
        pass

    def isRoomAvailable(self, roomName: str) -> bool:
        pass


class _MarketTransactionOrder:
    """
    :type id: str
    :type type: str
    :type price: float
    """

    def __init__(self, _id: str, _type: str, price: int) -> None:
        self.id = _id
        self.type = _type
        self.price = price


# noinspection PyPep8Naming
class _MarketTransaction:
    """
    :type transactionId: str
    :type time: int
    :type sender: _Owner
    :type recipient: _Owner
    :type resourceType: str
    :type amount: int
    :type js_from: str
    :type to: str
    :type description: str
    :type order: _MarketTransactionOrder | None
    """

    def __init__(self, transactionId: str, time: int, sender: _Owner, recipient: _Owner, resourceType: str,
                 amount: int, js_from: str, to: str, description: str, order: Optional[_MarketTransactionOrder]) \
            -> None:
        self.transactionId = transactionId
        self.time = time
        self.sender = sender
        self.recipient = recipient
        self.resourceType = resourceType
        self.amount = amount
        self.js_from = js_from
        self.to = to
        self.description = description
        self.order = order


# noinspection PyPep8Naming
class _MarketOrder:
    """
    :type id: str
    :type created: int
    :type type: str
    :type resourceType: str
    :type roomName: str
    :type amount: int
    :type remainingAmount: int
    :type price: float
    """

    def __init__(self, _id: str, created: int, _type: str, resourceType: str, roomName: str, amount: int,
                 remainingAmount: int, price: float) -> None:
        self.id = _id
        self.created = created
        self.type = _type
        self.resourceType = resourceType
        self.roomName = roomName
        self.amount = amount
        self.remainingAmount = remainingAmount
        self.price = price


# noinspection PyPep8Naming
class _OwnedMarketOrder(_MarketOrder):
    """
    :type active: bool
    :type totalAmount: int
    """

    def __init__(self, _id: str, created: int, _type: str, resourceType: str, roomName: str, amount: int,
                 remainingAmount: int, price: float, active: bool, totalAmount: int) -> None:
        super().__init__(_id, created, _type, resourceType, roomName, amount, remainingAmount, price)
        self.active = active
        self.totalAmount = totalAmount


# noinspection PyPep8Naming
class _GameMarket:
    """
    :type credits: int
    :type incomingTransactions: list[_MarketTransaction]
    :type outgoingTransactions: list[_MarketTransaction]
    :type orders: dict[str, _OwnedMarketOrder]
    """

    def __init__(self, _credits: int, incomingTransactions: List[_MarketTransaction],
                 outgoingTransactions: List[_MarketTransaction], orders: Dict[str, _OwnedMarketOrder]) -> None:
        self.credits = _credits
        self.incomingTransactions = incomingTransactions
        self.outgoingTransactions = outgoingTransactions
        self.orders = orders

    def calcTransactionCost(self, amount: Union[int, float], roomName1: str, roomName2: str) -> int:
        pass

    def cancelOrder(self, orderId: str) -> int:
        pass

    def changeOrderPrice(self, orderId: str, newPrice: int) -> int:
        pass

    def createOrder(self, _type: str, resourceType: str, price: float, totalAmount: int, roomName: str = None) \
            -> int:
        pass

    def deal(self, orderId: str, amount: Union[int, float], yourRoomName: str = None) -> int:
        pass

    def extendOrder(self, orderId: str, addAmount: int) -> int:
        pass

    def getAllOrders(self, _filter: Union[Dict[str, Union[int, str]], Callable[[_MarketOrder], bool]]) \
            -> List[_MarketOrder]:
        pass

    def getOrderById(self, _id: str) -> _MarketOrder:
        pass


# noinspection PyPep8Naming
class Game:
    """
    :type constructionSites: dict[str, ConstructionSite]
    :type cpu: _GameCpu
    :type creeps: dict[str, Creep]
    :type flags: dict[str, Flag]
    :type gcl: _GameGcl
    :type map: _GameMap
    :type market: _GameMarket
    :type resources: dict[str, int]
    :type rooms: dict[str, Room]
    :type spawns: dict[str, StructureSpawn]
    :type structures: dict[str, Structure]
    :type time: int
    """
    constructionSites = {}  # type: Dict[str, ConstructionSite]
    cpu = None  # type: _GameCpu
    creeps = {}  # type: Dict[str, Creep]
    flags = {}  # type: Dict[str, Flag]
    gcl = None  # type: _GameGcl
    map = None  # type: _GameMap
    market = None  # type: _GameMarket
    resources = {}  # type: Dict[str, int]
    rooms = {}  # type: Dict[str, Room]
    spawns = {}  # type: Dict[str, StructureSpawn]
    structures = {}  # type: Dict[str, Structure]
    time = 0  # type: int

    @classmethod
    def getObjectById(cls, _id: str) -> RoomObject:
        pass

    @classmethod
    def notify(cls, message: str, groupInterval: int = 0):
        pass


_MemoryValue = Union[str, int, float, bool, '_Memory', List['_MemoryValue'], None]


class _Memory(dict):
    def __getattr__(self, key: str) -> _MemoryValue:
        pass

    def __setattr__(self, key: str, value: _MemoryValue) -> None:
        pass


Memory = _Memory()


class _ForeignSegment:
    """
    :type username: str
    :type id: int
    :type data: str
    """

    def __init__(self, username: str, _id: int, data: str) -> None:
        self.data = data
        self.username = username
        self.id = _id


# noinspection PyPep8Naming
class RawMemory:
    """
    :type segments: Dict[int, str]
    :type foreignSegment: _ForeignSegment | None
    """
    segments = {}  # type: Dict[int, str]
    foreignSegment = None  # type: Optional[_ForeignSegment]

    @classmethod
    def get(cls) -> str:
        pass

    @classmethod
    def set(cls, value: str):
        pass

    @classmethod
    def setActiveSegments(cls, ids: List[int]):
        pass

    @classmethod
    def setActiveForeignSegment(cls, username: Optional[str], _id: int = None):
        pass

    @classmethod
    def setDefaultPublicSegment(cls, _id: Optional[int]):
        pass

    @classmethod
    def setPublicSegments(cls, ids: List[int]):
        pass


# JavScript

_K = TypeVar('K')
_V = TypeVar('V')


# noinspection PyPep8Naming
class Object:
    """
    https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object
    """

    @classmethod
    def assign(cls, target: Any, *sources: Any):
        pass

    @classmethod
    def create(cls, proto: Any, propertiesObject: Any = None):
        pass

    @classmethod
    def defineProperties(cls, obj: Any, props: Dict[str, Any]):
        pass

    @classmethod
    def defineProperty(cls, obj: Any, prop: str, descriptor: Dict[str, Any]):
        pass

    @classmethod
    def freeze(cls, obj: Any):
        pass

    @classmethod
    def keys(cls, obj: Dict[_K, _V]) -> List[_K]:
        pass


class Math:
    """
    https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Math
    """

    @staticmethod
    def abs(x: Union[int, float]) -> Union[int, float]:
        pass

    @staticmethod
    def exp(x: Union[int, float]) -> Union[int, float]:
        pass

    @staticmethod
    def sign(x: Union[int, float]) -> int:
        pass

    @staticmethod
    def random() -> float:
        pass


# noinspection PyUnusedLocal
def typeof(x: Any) -> str:
    pass


# noinspection PyUnusedLocal
def require(name: str) -> Any:
    pass


class JSON:
    @classmethod
    def parse(cls, s: str) -> Dict[str, Any]:
        pass

    @classmethod
    def stringify(cls, v: Any) -> str:
        pass


this = None  # type: Any


# noinspection PyPep8Naming,PyShadowingBuiltins
class module:
    # noinspection PyPep8Naming
    class exports:
        loop = None  # type: Optional[Callable[[], None]]


class RegExp(str):
    def __init__(self, regex: str, args: Optional[str] = None) -> None:
        super().__init__(regex)
        self.ignoreCase = False
        self.js_global = False
        self.multiline = False

        self.source = regex

        if args is not None:
            for char in args:
                if char == 'i':
                    self.ignoreCase = True
                elif char == 'g':
                    self.js_global = True
                elif char == 'm':
                    self.multiline = True

    def exec(self, string: str) -> Optional[List[str]]:
        pass

    def test(self, string: str) -> bool:
        pass


Infinity = float('inf')

undefined = None  # type: None

_L1 = TypeVar('_L1')
_L2 = TypeVar('_L2')
_L3 = TypeVar('_L3', int, float)

_LodashPredicate = Union[Dict[str, Any], Callable[[_L1], bool], None]
_LodashIteratee = Union[str, Callable[[_L1], _L2], None]
_Collection = Union[List[_L1], Dict[str, _L1]]


# noinspection PyPep8Naming
class _LodashChain:
    def __init__(self, value):
        self.__inner = value

    def chunk(self, size: int = 1) -> '_LodashChain':
        pass

    def compact(self) -> '_LodashChain':
        pass

    def difference(self, *other: List[_L1]) -> '_LodashChain':
        pass

    def drop(self, n: int = 1) -> '_LodashChain':
        pass

    def dropRight(self, n: int = 1) -> '_LodashChain':
        pass

    def dropRightWhile(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def dropWhile(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def fill(self, value: _L1, start: int = 0, end: int = 0) -> '_LodashChain':
        pass

    def first(self) -> Optional[_L1]:
        pass

    def flatten(array: List[List[_L1]]) -> '_LodashChain':
        pass

    def flattenDeep(array: List[Any]) -> '_LodashChain':
        pass

    def initial(self) -> List[_L1]:
        pass

    def intersection(self, arrays: List[List[_L1]]) -> '_LodashChain':
        pass

    def last(self) -> Optional[Any]:
        pass

    def lastIndexOf(self, value: _L1, fromIndex: Union[int, bool] = 0) -> int:
        pass

    def pull(self, values: List[_L1]) -> '_LodashChain':
        pass

    def pullAt(self, indices: List[int]) -> '_LodashChain':
        pass

    def remove(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def rest(self) -> '_LodashChain':
        pass

    def slice(self, start: int = 0, end: int = 0) -> '_LodashChain':
        pass

    def sortedIndex(self, value: _L1, iteratee: _LodashIteratee = None, thisArg: Any = None) -> int:
        pass

    def sortedLastIndex(self, value: _L1, iteratee: _LodashIteratee = None, thisArg: Any = None) -> int:
        pass

    def take(self, n: int = 1) -> '_LodashChain':
        pass

    def takeRight(self, n: int = 1) -> '_LodashChain':
        pass

    def takeRightWhile(self, predicate: _LodashIteratee = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def takeWhile(self, predicate: _LodashIteratee = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def union(self, arrays: List[List[_L1]]) -> '_LodashChain':
        pass

    def uniq(self, isSorted: bool = False, iteratee: _LodashIteratee = None, thisArg: Any = None):
        pass

    def unzip(self) -> '_LodashChain':
        pass

    def unzipWith(self, iteratee: Optional[Callable[[Any, Any, Any, Any]]] = None,
                  thisArg: Any = None) -> '_LodashChain':
        pass

    def without(self, values: List[_L1]) -> '_LodashChain':
        pass

    def xor(self, arrays: List[List[_L1]]) -> '_LodashChain':
        pass

    def zip(self) -> '_LodashChain':
        pass

    def zipObject(self, values: Optional[List[Any]] = None) -> '_LodashChain':
        pass

    def zipWith(self, iteratee: Optional[Callable[[Any, Any, Any, Any]]] = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def all(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    def any(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    def at(self, *props: Any) -> List[_L1]:
        pass

    def countBy(self, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[_L2, int]:
        pass

    def every(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    def filter(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    def find(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    def findLast(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    def findWhere(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    def forEach(self, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    def forEachRight(self, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    def groupBy(self, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[_L2, List[_L1]]:
        pass

    def includes(self, value: _L1, fromIndex: int = 0) -> bool:
        pass

    def indexBy(self, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[str, _L1]:
        pass

    def invoke(self, path: str, *args: Any) -> '_LodashChain':
        pass

    def map(self, iteratee: _LodashIteratee = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def partition(self, predicate: _LodashPredicate = None, thisArg: Any = None) \
            -> '_LodashChain':
        pass

    def pluck(self, path: Union[str, List[str]]) -> '_LodashChain':
        pass

    def reduce(self, iteratee: Callable[[_L2, _L1], _L2] = None, accumulator: _L2 = None,
               thisArg: Any = None) -> _L2:
        pass

    def reduceRight(self, iteratee: Callable[[_L2, _L1], _L2] = None, accumulator: _L2 = None,
                    thisArg: Any = None) -> _L2:
        pass

    def reject(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def sample(self) -> Any:
        pass

    def shuffle(self) -> '_LodashChain':
        pass

    def size(self) -> int:
        pass

    def some(self, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    def sortBy(self, iteratee: _LodashIteratee = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def sortByAll(self, *iteratee: _LodashIteratee) -> '_LodashChain':
        pass

    def sortByOrder(self, iteratees: List[_LodashIteratee], orders: List[str]) -> '_LodashChain':
        pass

    def where(self, source: Any) -> '_LodashChain':
        pass

    def toArray(value: Any) -> '_LodashChain':
        pass

    def toPlainObject(value: Any) -> '_LodashChain':
        pass

    def sum(self, iteratee: Callable[[_L1], _L3] = lambda x: x, thisArg: Any = None) -> '_LodashChain':
        pass

    def keys(_object: Any) -> '_LodashChain':
        pass

    def mapKeys(_object: Any, iteratee: Callable[[str], str] = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def mapValues(self, iteratee: Callable[[Any], Any] = None, thisArg: Any = None) -> '_LodashChain':
        pass

    def omit(self, predicate: _LodashPredicate, thisArg: Any = None) -> '_LodashChain':
        pass

    def pairs(self) -> '_LodashChain':
        pass

    def values(self) -> '_LodashChain':
        pass


# noinspection PyPep8Naming
class _(_LodashChain):
    def __init__(self, value):
        super().__init__(value)

    @staticmethod
    def chunk(array: List[_L1], size: int = 1) -> List[List[_L1]]:
        pass

    @staticmethod
    def compact(array: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def difference(array: List[_L1], *other: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def drop(array: List[_L1], n: int = 1) -> List[_L1]:
        pass

    @staticmethod
    def dropRight(array: List[_L1], n: int = 1) -> List[_L1]:
        pass

    @staticmethod
    def dropRightWhile(array: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def dropWhile(array: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def fill(array: List[_L1], value: _L1, start: int = 0, end: int = 0) -> List[_L1]:
        pass

    @staticmethod
    def findIndex(array: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> int:
        pass

    @staticmethod
    def findLastIndex(array: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> int:
        pass

    @staticmethod
    def first(array: List[_L1]) -> Optional[_L1]:
        pass

    @staticmethod
    def flatten(array: List[List[_L1]]) -> List[_L1]:
        pass

    @staticmethod
    def flattenDeep(array: List[Any]) -> List[Any]:
        pass

    @staticmethod
    def indexOf(array: List[_L1], value: _L1, fromIndex: Union[int, bool] = 0) -> int:
        pass

    @staticmethod
    def initial(array: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def intersection(array: List[List[_L1]]) -> List[_L1]:
        pass

    @staticmethod
    def last(array: List[_L1]) -> Optional[_L1]:
        pass

    @staticmethod
    def lastIndexOf(array: List[_L1], value: _L1, fromIndex: Union[int, bool] = 0) -> int:
        pass

    @staticmethod
    def pull(array: List[_L1], values: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def pullAt(array: List[_L1], indices: List[int]) -> List[_L1]:
        pass

    @staticmethod
    def remove(array: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def rest(array: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def slice(array: List[_L1], start: int = 0, end: int = 0) -> List[_L1]:
        pass

    @staticmethod
    def sortedIndex(array: List[_L1], value: _L1, iteratee: _LodashIteratee = None, thisArg: Any = None) -> int:
        pass

    @staticmethod
    def sortedLastIndex(array: List[_L1], value: _L1, iteratee: _LodashIteratee = None, thisArg: Any = None) -> int:
        pass

    @staticmethod
    def take(array: List[_L1], n: int = 1) -> List[_L1]:
        pass

    @staticmethod
    def takeRight(array: List[_L1], n: int = 1) -> List[_L1]:
        pass

    @staticmethod
    def takeRightWhile(array: List[_L1], predicate: _LodashIteratee = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def takeWhile(array: List[_L1], predicate: _LodashIteratee = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def union(array: List[List[_L1]]) -> List[_L1]:
        pass

    @staticmethod
    def uniq(array: List[_L1], isSorted: bool = False, iteratee: _LodashIteratee = None, thisArg: Any = None):
        pass

    @staticmethod
    def unzip(array: List[Any]) -> List[Any]:
        pass

    @staticmethod
    def unzipWith(array: List[Any], iteratee: Optional[Callable[[Any, Any, Any, Any]]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def without(array: List[_L1], values: List[_L1]) -> List[_L1]:
        pass

    @staticmethod
    def xor(array: List[List[_L1]]) -> List[_L1]:
        pass

    @staticmethod
    def zip(array: List[Any]) -> List[Any]:
        pass

    @staticmethod
    def zipObject(props: List[Any], values: Optional[List[Any]] = None) -> Any:
        pass

    @staticmethod
    def zipWith(array: List[Any], iteratee: Optional[Callable[[Any, Any, Any, Any]]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def all(collection: List[_L1], predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    @staticmethod
    def any(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    @staticmethod
    def at(collection: _Collection, *props: Any) -> List[_L1]:
        pass

    @staticmethod
    def countBy(collection: _Collection, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[_L2, int]:
        pass

    @staticmethod
    def every(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    @staticmethod
    def filter(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def find(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    @staticmethod
    def findLast(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    @staticmethod
    def findWhere(collection: Any, predicate: _LodashPredicate = None, thisArg: Any = None) -> _L1:
        pass

    @staticmethod
    def forEach(collection: _Collection, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def forEachRight(collection: _Collection, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def groupBy(collection: _Collection, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[_L2, List[_L1]]:
        pass

    @staticmethod
    def includes(collection: _Collection, value: _L1, fromIndex: int = 0) -> bool:
        pass

    @staticmethod
    def indexBy(collection: _Collection, iteratee: _LodashIteratee = None, thisArg: Any = None) -> Dict[str, _L1]:
        pass

    @staticmethod
    def invoke(collection: _Collection, path: str, *args: Any) -> Any:
        pass

    @staticmethod
    def map(collection: _Collection, iteratee: _LodashIteratee = None, thisArg: Any = None) -> _L2:
        pass

    @staticmethod
    def partition(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) \
            -> Tuple[List[_L1], List[_L1]]:
        pass

    @staticmethod
    def pluck(collection: _Collection, path: Union[str, List[str]]) -> List[Any]:
        pass

    @staticmethod
    def reduce(collection: _Collection, iteratee: Callable[[_L2, _L1], _L2] = None, accumulator: _L2 = None,
               thisArg: Any = None) -> _L2:
        pass

    @staticmethod
    def reduceRight(collection: _Collection, iteratee: Callable[[_L2, _L1], _L2] = None, accumulator: _L2 = None,
                    thisArg: Any = None) -> _L2:
        pass

    @staticmethod
    def reject(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def sample(collection: _Collection) -> _L1:
        pass

    @staticmethod
    def shuffle(collection: _Collection) -> List[_L1]:
        pass

    @staticmethod
    def size(collection: Optional[_Collection]) -> int:
        pass

    @staticmethod
    def some(collection: _Collection, predicate: _LodashPredicate = None, thisArg: Any = None) -> bool:
        pass

    @staticmethod
    def sortBy(collection: _Collection, iteratee: _LodashIteratee = None, thisArg: Any = None) -> List[_L1]:
        pass

    @staticmethod
    def sortByAll(collection: _Collection, *iteratee: _LodashIteratee) -> List[_L1]:
        pass

    @staticmethod
    def sortByOrder(collection: _Collection, iteratees: List[_LodashIteratee], orders: List[str]) -> List[_L1]:
        pass

    @staticmethod
    def where(collection: _Collection, source: Any) -> List[_L1]:
        pass

    @staticmethod
    def clone(value: _L1) -> _L1:
        pass

    @staticmethod
    def cloneDeep(value: _L1) -> _L1:
        pass

    @staticmethod
    def gt(value: Any, other: Any) -> bool:
        pass

    @staticmethod
    def gte(value: Any, other: Any) -> bool:
        pass

    @staticmethod
    def isArguments(value: Any) -> bool:
        pass

    @staticmethod
    def isArray(value: Any) -> bool:
        pass

    @staticmethod
    def isBoolean(value: Any) -> bool:
        pass

    @staticmethod
    def isDate(value: Any) -> bool:
        pass

    @staticmethod
    def isElement(value: Any) -> bool:
        pass

    @staticmethod
    def isEmpty(value: Any) -> bool:
        pass

    @staticmethod
    def isEqual(value: Any, other: Any) -> bool:
        pass

    @staticmethod
    def isError(value: Any) -> bool:
        pass

    @staticmethod
    def isFinite(value: Any) -> bool:
        pass

    @staticmethod
    def isFunction(value: Any) -> bool:
        pass

    @staticmethod
    def isMatch(value: Any) -> bool:
        pass

    @staticmethod
    def isNaN(value: Any) -> bool:
        pass

    @staticmethod
    def isNative(value: Any) -> bool:
        pass

    @staticmethod
    def isNull(value: Any) -> bool:
        pass

    @staticmethod
    def isNumber(value: Any) -> bool:
        pass

    @staticmethod
    def isObject(value: Any) -> bool:
        pass

    @staticmethod
    def isPlainObject(value: Any) -> bool:
        pass

    @staticmethod
    def isRegExp(value: Any) -> bool:
        pass

    @staticmethod
    def isString(value: Any) -> bool:
        pass

    @staticmethod
    def isTypedArray(value: Any) -> bool:
        pass

    @staticmethod
    def isUndefined(value: Any) -> bool:
        pass

    @staticmethod
    def lt(value: Any, other: Any) -> bool:
        pass

    @staticmethod
    def lte(value: Any, other: Any) -> bool:
        pass

    @staticmethod
    def toArray(value: Any) -> List[Any]:
        pass

    @staticmethod
    def toPlainObject(value: Any) -> Any:
        pass

    @staticmethod
    def add(augend: Union[int, float], addend: Union[int, float]) -> Union[int, float]:
        pass

    @staticmethod
    def ceil(n: Union[int, float], precision: int = 0) -> Union[int, float]:
        pass

    @staticmethod
    def floor(n: Union[int, float], precision: int = 0) -> Union[int, float]:
        pass

    @staticmethod
    def max(collection: _Collection, iteratee: Callable[[_L1], _L3] = lambda x: x, thisArg: Any = None) -> _L1:
        pass

    @staticmethod
    def min(collection: _Collection, iteratee: Callable[[_L1], _L3] = lambda x: x, thisArg: Any = None) -> _L1:
        pass

    @staticmethod
    def round(n: Union[int, float], precision: int = 0) -> Union[int, float]:
        pass

    @staticmethod
    def sum(collection: _Collection, iteratee: Callable[[_L1], _L3] = lambda x: x, thisArg: Any = None) -> _L3:
        pass

    @staticmethod
    def assign(_object: Any, *sources: Any) -> Any:
        pass

    @staticmethod
    def create(prototype: Type[_L1], properties: Any = None) -> _L1:
        pass

    @staticmethod
    def defaults(_object: Any, *sources: Any) -> Any:
        pass

    @staticmethod
    def defaultsDeep(_object: Any, *sources: Any) -> Any:
        pass

    @staticmethod
    def findKey(_object: Any, predicate: _LodashPredicate = None, thisArg: Any = None) -> str:
        pass

    @staticmethod
    def findLastKey(_object: Any, predicate: _LodashPredicate = None, thisArg: Any = None) -> str:
        pass

    @staticmethod
    def forIn(_object: Any, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def forInRight(_object: Any, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def forOwn(_object: Any, iteratee: Callable[[_L1], Optional[bool]] = None, thisArg: Any = None):
        pass

    @staticmethod
    def functions(_object: Any) -> List[str]:
        pass

    @staticmethod
    def get(_object: Any, path: Union[str, List[str]], defaultValue: _L1 = None) -> _L1:
        pass

    @staticmethod
    def has(_object: Any, path: str) -> bool:
        pass

    @staticmethod
    def invert(_object: Any) -> Dict[str, str]:
        pass

    @staticmethod
    def keys(_object: Any) -> List[str]:
        pass

    @staticmethod
    def keysIn(_object: Any) -> List[str]:
        pass

    @staticmethod
    def mapKeys(_object: Any, iteratee: Callable[[str], str] = None, thisArg: Any = None) -> Any:
        pass

    @staticmethod
    def mapValues(_object: Any, iteratee: Callable[[Any], Any] = None, thisArg: Any = None) -> Any:
        pass

    @staticmethod
    def merge(_object: Any, *sources: Any) -> Any:
        pass

    @staticmethod
    def omit(_object: Any, predicate: _LodashPredicate, thisArg: Any = None) -> Any:
        pass

    @staticmethod
    def pairs(_object: Any) -> List[Tuple[str, Any]]:
        pass

    @staticmethod
    def pick(_object: Any, predicate: _LodashPredicate, thisArg: Any = None) -> Any:
        pass

    @staticmethod
    def result(_object: Any, path: str, defaultValue: _L1 = None) -> _L1:
        pass

    @staticmethod
    def set(_object: Any, path: str, value: Any):
        pass

    @staticmethod
    def transform(_object: Any, iteratee: Callable[[_L2, _L1], _L2] = None, accumulator: _L2 = None,
                  thisArg: Any = None) -> _L2:
        pass

    @staticmethod
    def values(_object: Union[Dict[str, _L2], Any]) -> List[_L2]:
        pass

    @staticmethod
    def valuesIn(_object: Union[Dict[str, _L2], Any]) -> List[_L2]:
        pass


__all__ = [
    # Classes
    "Creep",
    "Game",
    "Memory",
    "Room",
    "Flag",
    "RoomPosition",
    "RoomObject",
    "PathFinder",
    "Structure",
    "StructureSpawn",
    "StructureStorage",
    "StructureTerminal",
    "StructureController",
    "OwnedStructure",
    "ConstructionSite",
    "Source",
    "Mineral",
    "_PathPos",
    "Object",
    "Math",
    # JavaScript things
    "typeof",
    "require",
    "module",
    "JSON",
    "this",
    "RegExp",
    "Array",
    "Error",
    "Infinity",
    "console",
    "undefined",
    "Map",
    "Set",
    "String",
    "isFinite",
    "_",
]

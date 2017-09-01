from typing import List, Optional


class StoredObstacleType:
    OTHER_IMPASSABLE = 0
    ROAD = 1
    CONTROLLER = 2
    SOURCE = 3
    MINERAL = 4
    SOURCE_KEEPER_SOURCE = 5
    SOURCE_KEEPER_MINERAL = 6
    SOURCE_KEEPER_LAIR = 7


class StoredHostileStructureType:
    TOWER_LOADED = 0
    TOWER_EMPTY = 1
    SPAWN = 2
    WALL = 3
    RAMPART = 4
    OTHER_LOW_NONTARGET = 5
    OTHER_LOW_SEMITARGET = 6
    OTHER_LOW_TARGET = 7


class StoredEnemyRoomState:
    FULLY_FUNCTIONAL = 0
    RESERVED = 1
    JUST_MINING = 2
    OWNED_DEAD = 3


class StoredObstacle:
    """
    :type x: int
    :type y: int
    :type type: int
    :type source_capacity: int
    """

    def __init__(self, x, y, thing_type, source_capacity=0):
        # type: (int, int, StoredObstacleType, int) -> None
        self.x = x
        self.y = y
        self.type = thing_type
        self.source_capacity = source_capacity


class StoredHostileStructure:
    """
    :type x: int
    :type y: int
    :type type: int
    :type wall_hits: int
    """

    def __init__(self, x, y, thing_type, wall_hits=0):
        # type: (int, int, StoredHostileStructureType, int) -> None
        self.x = x
        self.y = y
        self.type = thing_type
        self.wall_hits = wall_hits


class StoredEnemyRoomOwner:
    def __init__(self, name, state):
        # type: (str, int) -> None
        self.name = name
        self.state = state


class StoredRoom:
    def __init__(self, obstacles=None, structures=None, last_updated=None, reservation_end=None, owner=None,
                 avoid_always=None):
        # type: (List[StoredObstacle], List[StoredHostileStructure], int, int, StoredEnemyRoomOwner, bool) -> None
        if obstacles is None:
            obstacles = []
        if structures is None:
            structures = []
        if last_updated is None:
            last_updated = 0  # type: int
        if reservation_end is None:
            reservation_end = 0
        self.obstacles = obstacles  # type: List[StoredObstacle]
        self.structures = structures  # type: List[StoredHostileStructure]
        self.last_updated = last_updated  # type: int
        self.reservation_end = reservation_end  # type: int
        self.owner = owner  # type: Optional[StoredEnemyRoomOwner]
        self.avoid_always = avoid_always  # type: bool

    @staticmethod
    def decode(string):
        # type: (str) -> StoredRoom
        pass

    def encode(self):
        # type: () -> str
        pass

class StoredStructureType:
    OTHER_IMPASSABLE = 0
    ROAD = 1
    CONTROLLER = 2
    SOURCE = 3
    MINERAL = 4
    SOURCE_KEEPER_SOURCE = 5
    SOURCE_KEEPER_MINERAL = 6
    SOURCE_KEEPER_LAIR = 7


class RoomOwnedState:
    FULLY_FUNCTIONAL = 0
    RESERVED = 1
    JUST_MINING = 2


class StoredStructure:
    """
    :type x: int
    :type y: int
    :type type: int
    :type source_capacity: int
    """

    def __init__(self, x, y, thing_type, source_capacity=0):
        self.x = x
        self.y = y
        self.type = thing_type
        self.source_capacity = source_capacity


class StoredRoomOwner:
    """
    :type name: str
    :type state: int
    """

    def __init__(self, name, state):
        self.name = name
        self.state = state


class StoredRoom:
    """
    :type structures: list[StoredStructure]
    :type structures_last_updated: int
    :type reservation_end: int
    :type owner: StoredRoomOwner
    """

    def __init__(self, structures=None, structures_last_updated=None, reservation_end=None, owner=None):
        if structures is None:
            structures = []
        if structures_last_updated is None:
            structures_last_updated = 0
        if reservation_end is None:
            reservation_end = 0
        self.structures = structures
        self.structures_last_updated = structures_last_updated
        self.reservation_end = reservation_end
        self.owner = owner

    @staticmethod
    def decode(string):
        """
        :type string: str
        :rtype: StoredRoom
        """

    def encode(self):
        """
        :rtype str
        """

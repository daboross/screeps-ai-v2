class StoredStructureType:
    OTHER_IMPASSABLE = 0
    ROAD = 1
    CONTROLLER = 2
    SOURCE = 3


class StoredStructure:
    """
    :type x: int
    :type y: int
    :type type: int
    """

    def __init__(self, x, y, thing_type):
        """
        :type x: int
        :type y: int
        :type thing_type: int
        """
        self.x = x
        self.y = y
        self.type = thing_type

    @staticmethod
    def decode(string):
        """
        :type string: str
        :rtype: StoredStructure
        """

    def encode(self):
        """
        :rtype str
        """


class StoredRoom:
    """
    :type structures: list[StoredStructure]
    """

    def __init__(self, structures=None):
        """
        :type structures: list[StoredStructure] | None
        """
        if structures is None:
            self.structures = []
        else:
            self.structures = structures

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

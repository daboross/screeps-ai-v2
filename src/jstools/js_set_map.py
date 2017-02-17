from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')

__pragma__('skip')


class JSMap:
    def has(self, key):
        """
        :type key: Any
        :rtype: bool
        """

    def get(self, key):
        """
        :type key: Any
        :rtype: Any
        """

    def set(self, key, value):
        """
        :type key: Any
        :type value: Any
        :rtype: None
        """

    def delete(self, key):
        """
        :type key: Any
        """

    def entries(self):
        """
        :rtype: list[(Any, Any)]
        """

    def keys(self):
        """
        :rtype: list[Any]
        """

    def values(self):
        """
        :rtype: list[Any]
        """


class JSSet:
    def has(self, key):
        """
        :type key: Any
        :rtype: bool
        """

    def add(self, key):
        """
        :type key: Any
        :rtype: Any
        """

    def keys(self):
        """
        :rtype: list[Any]
        """

    def values(self):
        """
        :rtype: list[Any]
        """


__pragma__('noskip')


def new_map(iterable=undefined):
    """
    :rtype: JSMap
    """
    return __new__(Map(iterable))


def new_set(iterable=undefined):
    """
    :rtype: JSSet
    """
    return __new__(Set(iterable))

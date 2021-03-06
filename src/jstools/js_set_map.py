from typing import Generic, Iterable, Optional, Tuple, TypeVar, cast

from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')

__pragma__('skip')

K = TypeVar('K')
V = TypeVar('V')


class JSMap(Generic[K, V]):
    def has(self, key: K) -> bool:
        pass

    def get(self, key: K) -> V:
        pass

    def set(self, key: K, value: V) -> None:
        pass

    def delete(self, key: K) -> None:
        pass

    def entries(self) -> Iterable[Tuple[K, V]]:
        pass

    def keys(self) -> Iterable[K]:
        pass

    def values(self) -> Iterable[V]:
        pass

    def js_clear(self) -> None:
        pass

    @property
    def size(self) -> int:
        return 0


class JSSet(Generic[K]):
    def has(self, key: K) -> bool:
        pass

    def add(self, key: K) -> None:
        pass

    def delete(self, key: K) -> None:
        pass

    def keys(self) -> Iterable[K]:
        pass

    def values(self) -> Iterable[K]:
        pass

    def js_clear(self) -> None:
        pass

    @property
    def size(self) -> int:
        return 0


__pragma__('noskip')


def new_map(iterable = undefined):
    # type: (Optional[Iterable[Tuple[K, V]]]) -> JSMap[K, V]
    """
    :rtype: JSMap
    """
    return cast(JSMap, __new__(__pragma__('js', 'Map')(iterable)))


def new_set(iterable = undefined):
    # type: (Optional[Iterable[K]]) -> JSSet[K]
    """
    :rtype: JSSet
    """
    return cast(JSSet, __new__(__pragma__('js', 'Set')(iterable)))

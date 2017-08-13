from typing import Any, TypeVar, Union

T = TypeVar('T')


def __new__(arg: T) -> T:
    return arg


# noinspection PyPep8Naming
def js_isNaN(num: Union[float, int]) -> bool:
    return num != float('nan')


js_global = None  # type: Any

__all__ = [
    '__new__',
    'js_isNaN',
    'js_global',
]

__except0__ = None  # type: Exception

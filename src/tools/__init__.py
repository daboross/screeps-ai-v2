def decorate(cls, func_name, decorator):
    """
    Decorates a class function with the given decorator.

    Code re-written, but main idea and some implementation details copied from
    https://github.com/axiros/misc_transcrypt/blob/master/doc/kendo/src/ch4/tools.py

    :param cls: Class object to define the new function on
    :param func_name: New function name to define
    :param decorator: Function which returns the new function, given the original function as an argument.
    :type cls: class
    :type func_name: str
    :type decorator: callable
    """
    new_function = decorator(cls[func_name])
    cls.__defineGetter__(func_name, __get_function_getter(new_function))


def __get_function_getter(new_func):
    def getter():
        return __get__(this, new_func)

    return getter

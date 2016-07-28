# Tools copied from @axiros's Transcrypt misc repository,
# https://github.com/axiros/misc_transcrypt/blob/master/doc/kendo/src/ch4/tools.py

# Original function
# # noinspection PyUnresolvedReferences
# def decorate(cls, func, dfunc):
#     """
#        class : a Transcrypt class
#        func  : name of method to decorate
#        dfunc : decorator function
#        Example:
#            e.g. dfunc =
#                def mydeco(obj, func, *a): return func(obj, *a)
#            class A:
#                i = 2
#                def foo(self, j, k): return self.i * int(j) * int(k)
#            decorate(A, 'foo', dfunc)
#            A().foo(4, 5) -> will pass the args and the result through the mydeco
#        """
#
#     def d3(*a):
#         # stage 3: call the decorator like known in python (obj, func, args):
#         return this['dfunc'](this['self'], this['orig'], *a)
#
#     # noinspection PyUnresolvedReferences
#     def d2(f, dfunc):
#         # stage2: return stage3 function, with context
#         return lambda: d3.bind({'self': this, 'orig': f, 'dfunc': dfunc})
#
#     # stage1: define the getter, func = name of original function:
#     cls.__defineGetter__(func, d2(cls[func], dfunc))


# # New decorate function
def decorate(obj, func_name, decorator):
    """
    :param obj: Class object to define the new function on
    :param func_name: New function name to define
    :param decorator: Function which returns the new function, given the original function as an argument.
    :type obj: class
    :type func_name: str
    :type decorator: callable
    """
    new_function = decorator(obj[func_name])
    obj.__defineGetter__(func_name, __get_function_getter(new_function))


def __get_function_getter(new_func):
    return lambda: new_func

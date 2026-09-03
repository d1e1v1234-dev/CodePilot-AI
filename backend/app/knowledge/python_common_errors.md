# Common Python Runtime Errors

## ZeroDivisionError
Raised when dividing by zero. Always validate divisors before
performing division, especially when the divisor comes from user
input or external data.

## TypeError
Occurs when an operation is applied to an incompatible type, e.g.
adding a string to an integer, or calling a function with the wrong
argument types. Type hints and input validation reduce this risk.

## KeyError / IndexError
Raised when accessing a dictionary key or list index that does not
exist. Use `.get()` with a default for dictionaries, and check bounds
or use try/except for list access when the index is not guaranteed
to be valid.

## AttributeError
Raised when calling a method or accessing an attribute that doesn't
exist on an object, often due to `None` being passed where an object
was expected. Guard against `None` before attribute access.

## Mutable Default Argument Bug
Using a mutable object (list, dict) as a default function argument
causes the same object to persist across calls, leading to unexpected
accumulation of state. Use `None` as the default and initialize inside
the function body instead.

## Off-by-One Errors
Common in loop bounds and slicing (e.g. `range(len(x))` vs
`range(len(x) - 1)`). Carefully verify loop boundaries, especially
when translating mathematical formulas into code.

## Resource Leaks
Failing to close files, database connections, or network sockets can
cause resource exhaustion. Use context managers (`with` statements)
to guarantee cleanup even when exceptions occur.
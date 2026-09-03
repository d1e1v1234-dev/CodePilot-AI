# Python Best Practices & PEP 8

## Naming
- Use snake_case for functions and variables, PascalCase for classes,
  UPPER_CASE for constants.
- Avoid single-letter names except in short loops (i, j) or well-known
  math contexts.

## Formatting
- Limit lines to 79-99 characters depending on team convention.
- Use 4 spaces per indentation level, never tabs.
- Put function bodies on a new line under `def`, not on the same line.
- Use blank lines to separate top-level functions and classes (2 lines)
  and methods inside a class (1 line).

## Functions
- Keep functions small and focused on a single responsibility.
- Use type hints for parameters and return values to improve
  readability and enable static analysis.
- Provide docstrings for public functions, classes, and modules.
- Avoid mutable default arguments (e.g. `def f(x, items=[])`), since
  the default is shared across calls and can cause subtle bugs.

## Error Handling
- Prefer explicit exception handling over silent failures.
- Catch specific exceptions rather than bare `except:`.
- Validate inputs (e.g. check for zero divisors, None values, empty
  collections) before performing operations that could fail.

## General
- Avoid global mutable state where possible.
- Prefer list/dict comprehensions over manual loops for simple
  transformations, but avoid overly complex one-liners.
- Use context managers (`with` statement) for resource handling
  (files, connections) to ensure proper cleanup.
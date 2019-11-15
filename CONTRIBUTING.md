
# Pull Request

For bug fixes you should provide some information about how to reproduce the problem so it can be verified if the new code solves the bug.

All CI tests must pass (Travis-CI)

Follow the code quality standards described in this file.

You are responsible for ensuring the code is mergeable and for fixing any issues that can occur if other code was merged before your code.

Always ensure docs are up to date based on your changes. If docs are missing and you think it should exists you are responsible for writing it.

For all PRs you should do/include the following
 - A line about the change in the `CHANGES` file Add it in the section `Next release`, create it if needed.
 - If you change something already implemented, for example adding/removing an argument you should add a line in `docs/Upgrading.md` describing how to migrate existing code from the old to the new code. Add it in the section `Next release`, create it if needed.
 - Add yourself to `docs/Authors` file (This is optional if you want)



# Code standard

In general, you should follow the established pep8 coding standard, but with the following exceptions/changes. https://www.python.org/dev/peps/pep-0008/

 - The default max line length (80) should not be followed religiously. Instead try to not exceed ~140 characters.
   Use the `flake8` tool to ensure you have good code quality.
 - Try to document as much as possible in the method docstring and avoid doc inside the code. Code should describe itself as much as possible.
 - Follow the `KISS` rule and `Make it work first, optimize later`
 - When indenting, try to indent with json style. For example:
```
# Do not use this style
from foo import (bar, qwe, rty,
                 foobar, barfoo)

print("foobar {barfoo} {qwert}".format(barfoo=foo,
                                       qwerty=bar))
```

```
# Use this style instead
from foo import (
    bar, qwe, rty,
    foobar, barfoo,
)

print("foobar {barfoo} {qwert}".format(
    barfoo=foo, qwerty=bar))
```



# Tests

I (Johan/Grokzen) have been allowed (by andymccurdy) explicitly to use all test code that already exists inside `redis-py` lib. If possible you should reuse code that exists in there.

All code should aim to have 100% test coverage. This is just a target and not a requirement.

All new features must implement tests to show that it works as intended.

All implemented tests must pass on all supported python versions. List of supported versions can be found in `README.md`.

All tests should be assumed to work against the test environment that is implemented when running in `travis-ci`. Currently that means 6 nodes in the cluster, 3 masters, 3 slaves, using port `7000-7005` and the node on port `7000` must be accessible on `127.0.0.1`


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



# Documentation

This project currently uses RST files and sphinx to build the documentation and to allow for it to be hosted on ReadTheDocs.

To test your documentation changes you must first install sphinx and sphinx-reload to render and view the docs files on your local machine before commiting them to this repo.

Install the dependencies inside a python virtualenv

```
pip install sphinx sphinx-reload
```

To start the local webbserver and render the docs folder, run from the root of this project

```
sphinx-reload docs/
```

It will open up the rendered website in your browser automatically.

At some point in the future the docs format will change from RST to MkDocs.



# Tests

I (Johan/Grokzen) have been allowed (by andymccurdy) explicitly to use all test code that already exists inside `redis-py` lib. If possible you should reuse code that exists in there.

All code should aim to have 100% test coverage. This is just a target and not a requirement.

All new features must implement tests to show that it works as intended.

All implemented tests must pass on all supported python versions. List of supported versions can be found in `README.md`.

All tests should be assumed to work against the test environment that is implemented when running in `travis-ci`. Currently that means 6 nodes in the cluster, 3 masters, 3 slaves, using port `7000-7005` and the node on port `7000` must be accessible on `127.0.0.1`


## Testing strategy and how to implement cluster specific tests

A new way of having the old upstream tests from redis-py combined with the cluster specific and unique tests that is needed to validate cluster functionality. This has been designed to improve the speed of which tests is updated from upstream as new redis-py releases is made and to make it easier to port them into the cluster variant.

How do you implement a test for this code?

The simplest case, this is a new cluster only/specific test that has nothing to do with the upstream redis-py package. If the test is related or could be classified to be added to one of the already existing test files that is mirrored from redis-py, then you should put this new test in the `..._cluster.py` version of the same file.

If you need to make some kind of cluster unique adjustment to a test mirrorer from redis-py upstream, then do the following. In the mirrored file, for example `test_commands.py` you add the following decorator `@skip_for_no_cluster_impl()` to the method you want to modify. Then you copy the entire method and add it to the same class/method structure but inside the cluster specific version of the test file. In this example you would put it in `test_commands_cluster.py`. Copy the entire test method and keep it as similar as possible to make it easier to update in the future in-case there is changes in upstream redis-py tests.

In the case where some command or feature is not supported natively or is decided not to be supported by this library, you should block any tests from upstream redis-py package that deals with that feature with the following decorator `@skip_for_no_cluster_impl()`. This will mark it to not be run during tests. This is also a good indicator for users of this library what features is not supported or there is not really a good cluster implementation for.

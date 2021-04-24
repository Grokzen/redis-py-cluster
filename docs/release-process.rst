Release process
===============

This section describes the process and how a release is made of this package.

All steps for twine tool can be found here https://twine.readthedocs.io/en/latest/


Install helper tools
--------------------

We use the standard sdist package build solution to package the source dist and wheel package into the format that pip and pypi understands.

We then use `twine` as the helper tool to upload and interact with pypi to submit the package to both pypi & testpypi.

First create a new venv that uses at least python3.7 but it is recommended to use the latest python version always. Published releases will be built with python 3.9.0+

Install twine with

.. code-block::

	pip install twine


Build python package
--------------------

First ensure that your `dist/` folder is empty so that you will not attempt to upload a dev version or other packages to the public index.

Create the source dist and wheel dist by running

.. code-block::

	python setup.py sdist bdist_wheel

The built python pakages can be found in ´dist/`


Submit to testpypi
------------------

It is always good to test out the build first locally so there are no obvious code problems but also to submit the build to testpypi to verify that the upload works and that you get the version number and `README` section working correct.

To upload to `testpypi` run

.. code-block::

	twine upload -r testpypi dist/*

It will upload everything to https://test.pypi.org/project/redis-py-cluster/


Submit build to public pypi
---------------------------

To submit the final package to public official pypi run

.. code-block::

	twine upload dist/*

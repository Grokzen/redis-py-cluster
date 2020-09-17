Development
===========


Documentation
-------------

To build and test/view documentation you need to install sphinx and addons to be able to run the local dev server to render the documentation.

Install sphinx plus addons

.. code-block::

	pip install sphinx sphinx-autobuild sphinx-rtd-theme

To start the local development server run from the root folder of this git repo

.. code-block::

	sphinx-autobuild docs docs/_build/html

Open up `localhost:8000` in your web-browser to view the online documentaion

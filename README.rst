python-foreman
==============

.. image:: https://travis-ci.org/david-caro/python-foreman.png
    :target: https://travis-ci.org/david-caro/python-foreman

Simple library to acces the Foreman API, the full documentation can be found
here:

 http://python-foreman.readthedocs.org


Installation
==============

Execute as root::

  $ python setup.py sdist
  $ pip install ./dist/python-foreman-\*.tar.gz


Plugins
=============

The plugins should be a simple module file with the a dictionary named *DEFS*
with the definitions of the new methods as in the `definitions.py` file

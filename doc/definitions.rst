Definitions files
=======================================

The Python Foreman can get the methods and it's definitions from two places
the ``definitions`` directory or the foreman instance.

This ``definitions`` directory contains some apipie json definitions retrieved from
different foreman versions and api versions, by default it will try to match the foreman version
with the fittest of those files.

It can also get it's definitions from the live Foreman instance, to do that,
you have to make sure that the urls:

* ``FOREMAN_URL/apidoc/v2.json``
* ``FOREMAN_URL/apidoc/v1.json``

are available, usually that means that you'll have to set the ``config.use_cache``
parameter for the apipie gem to false (normally found under
``FOREMAN_HOME/config/initializers/apipie.rb``)

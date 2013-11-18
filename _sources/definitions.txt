Definitions file
=======================================

The Python Foreman gets the methods and it's definitions from a module named
``definitions``.
This module contains a dictionary that can be manually edited, but in case
that you are just lazy (like me :) ) you can let the client generate it for
you. Whe you import the client module if that file does not exist, it
downloads it from the web.

**CAUTION**: it relies on the web structure so it may break anytime.

Let's see it in action, if we have this on our directory::

   client.py
   |
   \-- client.py


And we import the module :mod:`foreman.client`, we will end up with this::



   client.py
   |
   |-- client.py
   \-- definitions.py


**Notice**: it will not overwrite it if it does find the module, so to update
the file you must rename it and import the module.

The function that generates the file is :class:`foreman.client.generate_defs_file`.

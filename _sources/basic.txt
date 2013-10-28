Basic Tutorial
=======================================


Connect
----------------------

To connect to a foreman server just instantiate a :class:`foreman.client.Foreman` object with the server's url and authentication aprameters, like this:

>>> from getpass import getpass
>>> from foreman.client import Foreman
>>> f = Foreman('http://myforeman.server:3000', ('myuser', getpass()))


index
-----------------------


Those are the main methods to get info for groups of objects, for example, to get a sumary of all the hosts you could do:

>>> f.index_hosts()

Take into account that it accepts some parameters to handle the paging and the ammount of elements to get.


show
------------------------

This methods give you all the information for a specific object, for example:

>>> f.show_hosts(id=1)

Will show all the info for the host with id 1.


create
---------------------

This methods create a new object into foreman. An example:

>>> f.create_host(host={'name': 'mynewhost', 'ip': '192.168.1.1', 'mac': '00:00:00:00:00:00'})

To see the exact parameters look at the docs.


update
---------------------

This methods update the info for the given object, usually called with an id and a hash representating the object.


destroy
----------------------

This methods give you a way to destroy any object.

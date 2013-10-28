#!/usr/bin/env python

from distutils.core import setup

setup(name = "python-foreman",
    version = "0.1.2",
    description = "Simple low-level client library to access the Foreman API",
    author = "David Caro",
    author_email = "dcaroest@redhat.com",
    packages = ['foreman', 'foreman_plugins'],
    url = 'nowhere',
    install_requires = [
        'requests>=0.14',
    ]
) 

#!/usr/bin/env python

from setuptools import setup

long_desc = open('README.rst').read()

setup(
    name="python-foreman",
    version="0.2.1",
    description="Simple low-level client library to access the Foreman API",
    long_description=long_desc,
    author="David Caro",
    author_email="dcaroest@redhat.com",
    packages=['foreman', 'foreman_plugins'],
    url='https://github.com/david-caro/python-foreman',
    install_requires=[
        'requests>=0.14',
    ],
    package_data={
        'foreman': ['definitions/*.json'],
    },
)

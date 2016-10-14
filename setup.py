#!/usr/bin/env python
from setuptools import setup

PACKAGE_NAME = 'python-foreman'
URL = 'https://github.com/david-caro/python-foreman'


if __name__ == '__main__':
    setup(
        autosemver=True,
        install_requires=[
            'autosemver',
            'requests',
            'six',
        ],
        setup_requires=['autosemver'],
        name=PACKAGE_NAME,
        include_package_data=True,
        packages=['foreman'],
        description=(
            'Simple low-level client library to access the Foreman API'
        ),
        author='David Caro',
        author_email='david@dcaro.es',
        url=URL,
        bugtracker_url=URL + '/issues/',
        license='GPLv2',
        classifiers=[
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
        ],
    )

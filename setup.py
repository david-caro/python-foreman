#!/usr/bin/env python
from setuptools import setup

from autosemver.packaging import (
    get_authors,
    get_current_version,
    get_changelog,
)


PACKAGE_NAME = 'python-foreman'
URL = 'https://github.com/david-caro/python-foreman'


if __name__ == '__main__':
    with open('AUTHORS', 'w') as authors_fd:
        authors_fd.write('\n'.join(get_authors()))

    with open('CHANGELOG', 'w') as changelog_fd:
        changelog = get_changelog(bugtracker_url=URL + '/issues')
        try:
            changelog_fd.write(changelog.decode())
        except AttributeError:
            changelog_fd.write(changelog)

    setup(
        install_requires=[
            'requests',
            'six',
        ],
        setup_requires=['autosemver'],
        name=PACKAGE_NAME,
        version=get_current_version(project_name=PACKAGE_NAME),
        include_package_data=True,
        description=(
            'Simple low-level client library to access the Foreman API'
        ),
        author='David Caro',
        author_email='david@dcaro.es',
        url=URL,
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

#!/usr/bin/env python
import os
import subprocess
from setuptools import setup


def check_output(args):
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    if proc.returncode:
        raise RuntimeError(
            'Failed to run %s\nrc=%s\nstdout=\n%sstderr=%s'
            % (args, proc.returncode, stdout, stderr)
        )

    return stdout


def get_version():
    """
    Retrieves the version of the package, from the PKG-INFO file or generates
    it with the version script

    Returns:
        str: Version for the package

    Raises:
        RuntimeError: If the version could not be retrieved
    """
    version = None
    if os.path.exists('PKG-INFO'):
        with open('PKG-INFO') as info_fd:
            for line in info_fd.readlines():
                if line.startswith('Version: '):
                    version = line.split(' ', 1)[-1]

    elif os.path.exists('scripts/version_manager.py'):
        version = check_output(
            ['scripts/version_manager.py', '.', 'version']
        ).strip()

    if version is None:
        raise RuntimeError('Failed to get package version')

    # py3 compatibility step
    if not isinstance(version, str) and isinstance(version, bytes):
        version = version.decode()

    return version


def get_changelog(project_dir=os.curdir):
    """
    Retrieves the changelog, from the CHANGELOG file (if in a package) or
    generates it with the version script
    Returns:
        str: changelog
    Raises:
        RuntimeError: If the changelog could not be retrieved
    """
    changelog = ''
    pkg_info_file = os.path.join(project_dir, 'PKG-INFO')
    changelog_file = os.path.join(project_dir, 'CHANGELOG')
    version_manager = os.path.join(project_dir, 'scripts/version_manager.py')
    if os.path.exists(pkg_info_file) and os.path.exists(changelog_file):
        with open(changelog_file) as changelog_fd:
            changelog = changelog_fd.read()

    elif os.path.exists(version_manager):
        changelog = check_output(
            [version_manager, project_dir, 'changelog']
        ).strip()

    return changelog


def get_authors(project_dir=os.curdir):
    """
    Retrieves the authors list, from the AUTHORS file (if in a package) or
    generates it with the version script
    Returns:
        list(str): List of authors
    Raises:
        RuntimeError: If the authors could not be retrieved
    """
    authors = set()
    pkg_info_file = os.path.join(project_dir, 'PKG-INFO')
    authors_file = os.path.join(project_dir, 'AUTHORS')
    version_manager = os.path.join(project_dir, 'scripts/version_manager.py')
    if os.path.exists(pkg_info_file) and os.path.exists(authors_file):
        with open(authors_file) as authors_fd:
            authors = set(authors_fd.read().splitlines())

    elif os.path.exists(version_manager):
        authors = set(check_output(
            [version_manager, project_dir, 'authors']
        ).strip().decode().splitlines())

    return authors


if __name__ == '__main__':
    with open('AUTHORS', 'w') as authors_fd:
        authors_fd.write('\n'.join(get_authors()))

    with open('CHANGELOG', 'w') as changelog_fd:
        try:
            changelog_fd.write(get_changelog().decode())
        except AttributeError:
            changelog_fd.write(get_changelog())

    setup(
        install_requires=[
            'requests',
            'six',
        ],
        name='python-foreman',
        version=get_version(),
        include_package_data=True,
        description=(
            'Simple low-level client library to access the Foreman API'
        ),
        author='David Caro',
        author_email='david@dcaro.es',
        url='https://github.com/david-caro/python-foreman',
        license='GPLv2',
        classifiers=[
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
        ],
    )

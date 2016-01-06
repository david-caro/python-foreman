#!/usr/bin/env python
import os
from setuptools import setup
from subprocess import check_output


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

    elif os.path.exists('scripts/generate_version.sh'):
        version = check_output(['scripts/generate_version.sh']).strip()

    if version is None:
        raise RuntimeError('Failed to get package version')

    return version


os.environ['PBR_VERSION'] = get_version()


setup(
    setup_requires=['pbr'],
    pbr=True,
)

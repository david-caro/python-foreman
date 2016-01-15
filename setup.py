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

    elif os.path.exists('scripts/generate_version.sh'):
        version = check_output(['scripts/generate_version.sh']).strip()

    if version is None:
        raise RuntimeError('Failed to get package version')

    # py3 compatibility step
    if not isinstance(version, str) and isinstance(version, bytes):
        version = version.decode()

    return version


os.environ['PBR_VERSION'] = get_version()


setup(
    setup_requires=['pbr'],
    pbr=True,
)

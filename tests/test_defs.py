#!/usr/bin/env python
# encoding: utf-8
from __future__ import absolute_import, division, print_function

import os
import six

import pytest
from foreman.client import Foreman, Resource, requests

from .mocks import SessionMock


URL = 'foreman.example.com'


class HasConflictingMethods(Exception):
    def __init__(self, resource, conflicting_methods):
        super(HasConflictingMethods, self).__init__(
            '%s has conflicting methods:' +
            '\n    '.join(str(method) for method in conflicting_methods)
        )


def check_api(url, foreman_version, api_version, cache_dir):
    cli = generate_api(url, foreman_version, api_version, cache_dir)
    for value in six.itervalues(cli.__dict__):
        if not isinstance(value, Resource):
            continue

        check_resource(resource=value)


def generate_api(url, foreman_version, api_version, cache_dir):
    requests.Session = SessionMock(url, foreman_version)
    print("Generating api")
    return Foreman(
        url,
        version=foreman_version,
        api_version=api_version,
        cache_dir=cache_dir,
    )


def check_resource(resource):
    print("Checking resource: %s" % resource)
    conflicting_methods = getattr(resource, '_conflicting_methods', [])
    if getattr(resource, '_conflicting_methods', []):
        raise HasConflictingMethods(
            resource,
            conflicting_methods,
        )

    assert resource._own_methods


def api_versions_in_dir(defs_dir):
    api_versions = []
    for json_file in os.listdir(defs_dir):
        if json_file.endswith('.json'):
            version = json_file.strip('.json').rsplit('-', 1)
            api_versions.append(version)

    return api_versions


def all_api_versions():
    defs_dirs = [
        'foreman/definitions',
        'tests/fixtures/definitions'
    ]
    api_versions = []
    for dirname in defs_dirs:
        api_versions.extend(
            api_versions_in_dir(defs_dir=dirname)
        )

    return api_versions


@pytest.mark.parametrize(
    'api_version',
    all_api_versions(),
    ids=[':'.join(ver) for ver in all_api_versions()],
)
def test_apis(api_version, capsys):
    try:
        check_api(
            url=URL,
            foreman_version=api_version[0],
            api_version=api_version[1].strip('v'),
            cache_dir='tests/fixtures',
        )
    except HasConflictingMethods as error:
        print('Got conflicting methods: %s' % error)

import os
import six
import logging
from foreman.client import Foreman, Resource, requests
from .mocks import SessionMock


class DefsGen(object):

    url = 'foreman.example.com'

    def __init__(self, foreman_version, api_version):
        self.frmn_ver = foreman_version
        self.api_ver = api_version
        self.logger = logging.getLogger(
            "Foreman-%s-%s" % (self.frmn_ver, self.api_ver)
        )

    def check_api(self):
        f = self.generate_api()
        for value in six.itervalues(f.__dict__):
            if not isinstance(value, Resource):
                continue
            self.check_resource(value)

    def generate_api(self):
        requests.Session = SessionMock(self.url, self.frmn_ver)
        self.logger.info("Generate api")
        return Foreman(
            self.url,
            version=self.frmn_ver,
            api_version=self.api_ver,
        )

    def check_resource(self, resource):
        self.logger.info("Checking resource: %s", resource)
        # assert not resource._unbound_methods

    def __repr__(self):
        return "DefsGen(frmn_ver=%s, api_ver=%s)" % (
            self.frmn_ver,
            self.api_ver,
        )


def test_apis():
    for json_file in os.listdir("foreman/definitions"):
        if json_file.endswith('.json'):
            version = json_file.strip('.json').split('-')
            if len(version) != 2:
                continue
            test = DefsGen(version[0], version[1].strip('v'))
            yield test.check_api,

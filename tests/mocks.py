from copy import deepcopy


class ResponseMock(object):
    def __init__(self, url, code=200, text=None):
        self.url = url
        self.status_code = code
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400


class SessionMock(object):

    def __init__(self, url, version):
        self.url = url
        self.v = version
        self.headers = {}
        self.auth = None
        self.dr = {
            "GET": {
                self.url: ResponseMock(self.url, text="Version %s" % self.v),
            }
        }
        self.r = None
        self.map_responses(dict())

    def __call__(self):
        return self

    def map_responses(self, dict_):
        self.r = deepcopy(self.dr)
        self.r.update(dict_)

    def mapping(self, method, url, **kwargs):
        try:
            return self.r[method][url]
        except KeyError as ex:
            return ResponseMock(url, code=404, text=str(ex))

    def get(self, url, **kwargs):
        return self.mapping('GET', url)

    def post(self, url, data=None, **kwargs):
        return self.mapping('POST', url)

    def put(self, url, data=None, **kwargs):
        return self.mapping('PUT', url)

    def delete(self, url, **kwargs):
        return self.mapping('DELETE', url)

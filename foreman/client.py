"""
This module provides access to the API of a foreman server
"""
import re
import six
import json
import copy
import types
import pprint
import logging
import os.path
import pkgutil
import glob

import requests

try:
    import foreman_plugins
    PKG_PATH = os.path.dirname(foreman_plugins.__file__)
    PLUGINS = [name for _, name, _ in pkgutil.iter_modules([PKG_PATH])]
except ImportError:
    PLUGINS = []


if requests.__version__.split('.', 1)[0] == '0':
    OLD_REQ = True
else:
    OLD_REQ = False

logger = logging.getLogger(__name__)


def set_loglevel(level):
    """
    Sets the loglevel for the python-foreman module.

    :param loglevel: a loglevel constant from the logging module.
    """
    logger.setLevel(level)


def try_int(what):
    try:
        return int(what)
    except ValueError:
        return what


def parse_version(version_string):
    """
    :param version_string: Version string to parse, like '1.2.3'

    Passing to int as many of the elements as possible to support comparing
    ints of different number of chars (2<10 but '2'>'10'). So we just accept
    that any element with chars will be considered lesser to any int element.
    """
    return tuple(
        try_int(token)
        for token in version_string.replace('-', '.', 1).split('.')
    )


def res_to_str(res):
    """
    :param res: :class:`requests.Response` object

    Parse the given request and generate an informative string from it
    """
    if 'Authorization' in res.request.headers:
        res.request.headers['Authorization'] = "*****"
    return """
####################################
url = %s
headers = %s
-------- data sent -----------------
%s
------------------------------------
@@@@@ response @@@@@@@@@@@@@@@@
headers = %s
code = %d
reason = %s
--------- data received ------------
%s
------------------------------------
####################################
""" % (res.url,
       str(res.request.headers),
       OLD_REQ and res.request.data or res.request.body,
       res.headers,
       res.status_code,
       res.reason,
       res.text)


class ForemanException(Exception):
    def __init__(self, res, msg):
        """
        This exception wraps an error message and let's the caller to get the
        :class:`requests.Response` that failed
        """
        Exception.__init__(self, msg)
        self.res = res


class ObjectNotFound(ForemanException):
    pass


class Unacceptable(ForemanException):
    pass


class ForemanVersionException(Exception):
    pass


class MethodAPIDescription(object):
    exclude_html_reg = re.compile('</?[^>/]+/?>')
    resource_pattern = re.compile(r'^/api(/v[12])?/(?P<resource>\w+).*')

    def __init__(self, resource, method, api):
        self._method = copy.deepcopy(method)
        self._api = copy.deepcopy(api)
        self._apipie_resource = resource
        self.url = self._api['api_url']
        self.url_params = re.findall('/:([^/]+)(?:/|$)', self.url)
        self.params = self._method['params']
        self.resource = self.parse_resource_from_url(self.url) or ''
        self.name = self._get_name()
        self.http_method = self._api['http_method']
        self.short_desc = self._api['short_description'] or ''

    def __repr__(self):
        return "<resource:%s, name:%s>" % (self.resource, self.name)

    def parse_resource_from_url(self, url):
        """
        Returns the appropriate resource name for the given URL.

        :param url:  API URL stub, like: '/api/hosts'
        :return: Resource name, like 'hosts', or None if not found
        """
        # special case for the api root
        if url == '/api':
            return 'api'

        match = self.resource_pattern.match(url)
        if match:
            return match.groupdict().get('resource', None)

    def _get_name(self):
        """
        There are three cases, because apipie definitions can have multiple
        signatures but python does not
        For example, the api endpoint:
           /api/myres/:myres_id/subres/:subres_id/subres2

        for method *index* will be translated to the api method name:
            subres_index_subres2

        So when you want to call it from v2 object, you'll have:

          myres.subres_index_subres2

        """
        if self.url.count(':') > 1:
            # /api/one/two/:three/four -> two_:three_four
            base_name = self.url.split('/', 3)[-1].replace('/', '_')[1:]
            # :one_two_three -> two_three
            if base_name.startswith(':'):
                base_name = base_name.split('_')[-1]
            # one_:two_three_:four_five -> one_three_five
            base_name = re.sub('_:[^/]+', '', base_name)
            # in case that the last term was a parameter
            if base_name.endswith('_'):
                base_name = base_name[:-1]
            # one_two_three -> one_two_method_three
            base_name = (
                '_' + self._method['name']
            ).join(base_name.rsplit('_', 1))
        else:
            base_name = self._method['name']
        if self._apipie_resource != self.resource:
            return '%s_%s' % (self._apipie_resource, base_name)
        else:
            return base_name

    def get_global_method_name(self):
        return '%s_%s' % (self.resource, self.name.replace('.', '_'))

    def generate_func(self, as_global=False):
        """
        Generate function for specific method and using specific api

        :param as_global: if set, will use the global function name, instead of
            the class method (usually {resource}_{class_method}) when defining
            the function
        """
        keywords = []
        params_def = []
        params_doc = ""
        original_names = {}

        params = dict(
            (param['name'], param)
            for param in self.params
        )

        # parse the url required params, as sometimes they are skipped in the
        # parameters list of the definition
        for param in self.url_params:
            if param not in params:
                param = {
                    'name': param,
                    'required': True,
                    'description': '',
                    'validator': '',
                }
                params[param['name']] = param
            else:
                params[param]['required'] = True

        # split required and non-required params for the definition
        req_params = []
        nonreq_params = []
        for param in six.itervalues(params):
            if param['required']:
                req_params.append(param)
            else:
                nonreq_params.append(param)

        for param in req_params + nonreq_params:
            params_doc += self.create_param_doc(param) + "\n"
            local_name = param['name']
            # some params collide with python keywords, that's why we do
            # this switch (and undo it inside the function we generate)
            if param['name'] == 'except':
                local_name = 'except_'
            original_names[local_name] = param['name']
            keywords.append(local_name)
            if param['required']:
                params_def.append("%s" % local_name)
            else:
                params_def.append("%s=None" % local_name)

        func_head = 'def {0}(self, {1}):'.format(
            as_global and self.get_global_method_name() or self.name,
            ', '.join(params_def)
        )
        code_body = (
            '   _vars_ = locals()\n'
            '   _url = self._fill_url("{url}", _vars_, {url_params})\n'
            '   _original_names = {original_names}\n'
            '   _kwargs = dict((_original_names[k], _vars_[k])\n'
            '                   for k in {keywords} if _vars_[k])\n'
            '   return self._foreman.do_{http_method}(_url, _kwargs)')
        code_body = code_body.format(
            http_method=self.http_method.lower(),
            url=self.url,
            url_params=self.url_params,
            keywords=keywords,
            original_names=original_names,
        )

        code = [
            func_head,
            '   """',
            self.short_desc,
            '',
            params_doc,
            '   """',
            code_body,
        ]

        code = '\n'.join(code)

        six.exec_(code)

        function = locals()[self.name]
        # to ease debugging, all the funcs have the definitions attached
        setattr(function, 'defs', self)
        return function

    @classmethod
    def create_param_doc(cls, param, prefix=None):
        """
        Generate documentation for single parameter of function
        :param param: dict contains info about parameter
        :param sub: prefix string for recursive purposes
        """
        desc = cls.exclude_html_reg.sub('', param['description']).strip()
        if not desc:
            desc = "<no description>"
        name = param['name']
        if prefix:
            name = "%s[%s]" % (prefix, name)
        doc_ = ":param %s: %s; %s" % (name, desc, param['validator'])
        if param['required']:
            doc_ += " (REQUIRED)"
        else:
            doc_ += " (OPTIONAL)"
        for param in param.get('params', []):
            doc_ += "\n" + cls.create_param_doc(param, name)
        return doc_


def parse_resource_definition(resource_name, resource_dct):
    """
    Returns all the info extracted from a resource section of the apipie json

    :param resource_name: Name of the resource that is defined by the section
    :param resrouce_dict: Dictionary as generated by apipie of the resource
        definition
    """
    new_dict = {
        '__module__': resource_dct.get('__module__', __name__),
        '__doc__': resource_dct['full_description'],
        '_resource_name': resource_name,
        '_own_methods': set(),
        '_conflicting_methods': [],
    }

    # methods in foreign_methods are meant for other resources,
    # that is, the url and the resource field do not match /api/{resource}
    foreign_methods = {}

    # as defined per apipie gem, each method can have more than one api,
    # for example, /api/hosts can have the GET /api/hosts api and the GET
    # /api/hosts/:id api or DELETE /api/hosts
    for method in resource_dct['methods']:
        # set the docstring if it only has one api
        if not new_dict['__doc__'] and len(method['apis']) == 1:
            new_dict['__doc__'] = \
                method['apis'][0]['short_description']
        for api in method['apis']:
            api = MethodAPIDescription(resource_name, method, api)

            if api.resource != resource_name:
                # this means that the json apipie passed says that an
                # endpoint in the form: /api/{resource}/* belongs to
                # {different_resource}, we just put it under {resource}
                # later, storing it under _foreign_methods for now as we
                # might not have parsed {resource} yet
                functions = foreign_methods.setdefault(api.resource, {})
                if api.name in functions:
                    old_api = functions.get(api.name).defs
                    # show only in debug the repeated but identical definitions
                    log_method = logger.warning
                    if api.url == old_api.url:
                        log_method = logger.debug

                    log_method(
                        "There is a conflict trying to redefine a method "
                        "for a foreign resource (%s): \n"
                        "\tresource:\n"
                        "\tapipie_resource: %s\n"
                        "\tnew_api: %s\n"
                        "\tnew_url: %s\n"
                        "\told_api: %s\n"
                        "\told_url: %s",
                        api.name,
                        resource_name,
                        pprint.pformat(api),
                        api.url,
                        pprint.pformat(old_api),
                        old_api.url,
                    )
                    new_dict['_conflicting_methods'].append(api)
                    continue
                functions[api.name] = api.generate_func()

            else:
                # it's an own method, resource and url match
                if api.name in new_dict['_own_methods']:
                    old_api = new_dict.get(api.name).defs
                    log_method = logger.warning
                    # show only in debug the repeated but identical definitions
                    if api.url == old_api.url:
                        log_method = logger.debug

                    log_method(
                        "There is a conflict trying to redefine method "
                        "(%s): \n"
                        "\tapipie_resource: %s\n"
                        "\tnew_api: %s\n"
                        "\tnew_url: %s\n"
                        "\told_api: %s\n"
                        "\told_url: %s",
                        api.name,
                        resource_name,
                        pprint.pformat(api),
                        api.url,
                        pprint.pformat(old_api),
                        old_api.url,
                    )
                    new_dict['_conflicting_methods'].append(api)
                    continue
                new_dict['_own_methods'].add(api.name)
                new_dict[api.name] = api.generate_func()

    return new_dict, foreign_methods


class ResourceMeta(type):
    """
    This type composes methods for resource class
    """
    def __new__(meta, name, bases, data):
        if name == 'Resource':  # Skip base class
            return type.__new__(meta, name, bases, data)

        # element_name => ElementName
        cls_name = ''.join([x.capitalize() for x in name.split('_')])
        return type.__new__(meta, str(cls_name), bases, data)


class Resource(object):
    """
    Provides entry point for specific resource.
    """
    __metaclass__ = ResourceMeta
    _params_reg = re.compile(":([^/]+)")

    def __init__(self, foreman):
        """
        :param foreman: instance of Foreman class
        """
        self._foreman = foreman
        # Preserve backward compatibility with old interface and declare global
        # methods to access the common methods
        for method_name in ('index', 'show', 'update', 'destroy', 'create'):
            method = getattr(self, method_name, None)
            method_name = "%s_%s" % (
                method_name,
                self.__class__.__name__.lower(),
            )
            if method:
                setattr(self._foreman, method_name, method)

    def _fill_url(self, url, vars_, params):
        kwargs = dict((k, vars_[k]) for k in params)
        url = self._params_reg.sub(lambda match: '{%s}' % match.groups(), url)
        return url.format(**kwargs)


class MetaForeman(type):
    def __new__(meta, cls_name, bases, attrs):
        """
        This class is called when defining the Foreman class, and populates it
        with the defined methods.
        :param meta: This metaclass
        :param cls_name: Name of the class that is going to be created
        :param bases: Bases for the new class
        :param attrs: Attributes of the new class
        """
        entries = {
            'name': 'plugins',
            'methods': [],
            'full_description': "Binds foreman_plugins",
        }
        for plugin in (pl for pl in PLUGINS if not pl.startswith('_')):
            try:
                myplugin = __import__(
                    'foreman_plugins.' + plugin,
                    globals(),
                    locals(),
                    ['DEFS'],
                )
            except ImportError:
                logger.error('Unable to import plugin module %s', plugin)
                continue
            for http_method, funcs in six.iteritems(myplugin.DEFS):
                methods = MetaForeman.convert_plugin_def(http_method, funcs)
                entries['methods'].extend(methods)

        def _init(self, foreman):
            super(self.__class__, self).__init__(foreman)
            for name, value in six.iteritems(self.__class__.__dict__):
                if isinstance(value, types.FunctionType) and name[0] != '_':
                    logger.debug(
                        'Registering plugin method %s',
                        name,
                    )
                    setattr(self._foreman, name, getattr(self, name))

        resource_data, foreigns = parse_resource_definition('plugins', entries)
        # by default, all the methods are detected as foreign, we must manually
        # add them
        for mname, method_dict in six.iteritems(foreigns):
            resource_data[mname] = tuple(method_dict.values())[0]
            resource_data['_own_methods'].add(mname)

        plugins_cls = ResourceMeta.__new__(
            ResourceMeta,
            'plugins',
            (Resource,),
            resource_data,
        )
        plugins_cls.__init__ = _init
        attrs['_plugins_resources'] = plugins_cls
        return type.__new__(meta, cls_name, bases, attrs)

    @staticmethod
    def convert_plugin_def(http_method, funcs):
        """
        This function parses one of the elements of the definitions dict for a
        plugin and extracts the relevant information

        :param http_method: HTTP method that uses (GET, POST, DELETE, ...)
        :param funcs: functions related to that HTTP method
        """
        methods = []
        if http_method not in ('GET', 'PUT', 'POST', 'DELETE'):
            logger.error(
                'Plugin load failure, HTTP method %s unsupported.',
                http_method,
            )
            return methods
        for fname, params in six.iteritems(funcs):
            method = {
                'apis': [{'short_description': 'no-doc'}],
                'params': [],
            }
            method['apis'][0]['http_method'] = http_method
            method['apis'][0]['api_url'] = '/api/' + fname
            method['name'] = fname
            for pname, pdef in six.iteritems(params):
                param = {
                    'name': pname,
                    'validator': "Must be %s" % pdef['ptype'],
                    'description': '',
                    'required': pdef['required'],
                }
                method['params'].append(param)
            methods.append(method)
        return methods


@six.add_metaclass(MetaForeman)
class Foreman(object):
    """
    Main client class. It's methods will be autogenerated, check the API docs
    for your foreman version `here <http://theforeman.org/api.html>`_.
    """

    def __init__(self, url, auth=None, version=None, api_version=None,
                 use_cache=True, strict_cache=True, timeout=60,
                 timeout_post=600, timeout_delete=600, timeout_put=None,
                 verify=False):
        """
        :param url: Full url to the foreman server
        :param auth: Tuple with the user and the pass
        :param version: Foreman version (will autodetect by default)
        :param api_version: Version of the api to use (1 by default)
        :param use_cache: if True, will use local api definitions, if False,
            will try to get them from the remote Foreman instance (it needs
            you to have disabled use_cache in the apipie configuration in your
            foreman instance)
        :param strict_cache: If True, will not use a similar version
            definitions file
        :param timeout: Timeout in seconds for each http request (default 60)
            If None or 0, then no timeout.
        :param timeout_post: Timeout in seconds for POST requests (eg. host
            creation, default 600 as it may take a long time depending on
            compute resource).
            If None, then global timeout is used, 0 means no timeout.
        :param timeout_delete: Timeout in seconds for DELETE requests (eg. host
            deletion, default 600 as it may take a long time depending on
            compute resource)
            If None, then global timeout is used, 0 means no timeout.
        :param timeout_put: Timeout in seconds for PUT requests
            If None, then global timeout is used, 0 means no timeout.
        :param verify: path to certificates bundle for SSL verification. If
            False, SSL will not be validated
        """
        if api_version is None:
            api_version = 1
            logger.warning(
                "Api v1 will not be the default in the next version, if you "
                "still want to use it, change the call to explicitly ask for "
                "it. Though we recommend using the new and improved version 2"
            )
        self.url = url
        self._req_params = {}
        self.timeout = {'DEFAULT': timeout or None}

        if timeout_post is not None:
            self.set_timeout(timeout_post, 'POST')
        if timeout_delete is not None:
            self.set_timeout(timeout_delete, 'DELETE')
        if timeout_put is not None:
            self.set_timeout(timeout_put, 'PUT')

        self.version = version
        self.api_version = api_version
        self.session = requests.Session()
        self.session.verify = verify
        if auth is not None:
            self.session.auth = auth
        self.session.headers.update(
            {
                'Accept': 'application/json; version=%s' % api_version,
                'Content-type': 'application/json',
            })
        if self.version is None:
            self.version = self.get_foreman_version()

        self._generate_api_defs(use_cache, strict_cache)
        # Instantiate plugins
        self.plugins = self._plugins_resources(self)

    def get_timeout(self, method=None):
        """
        Get timeout for given request method

        :param method: Request method (eg. GET, POST, ..). If None, return
            default timeout.
        """
        return self.timeout.get(method, self.timeout['DEFAULT'])

    def set_timeout(self, timeout, method='DEFAULT'):
        """
        Set the timeout for any connection, the timeout is the requests module
        timeout (for conneciton inactivity rather than request total time)

        :param timeout: Timeout in seconds for the connection inactivity
        :param method: Request method (eg. GET, POST, ..). By default, set
            default timeout.
        """
        self.timeout[method] = timeout or None

    def unset_timeout(self, method):
        """
        Ensure timeout for given method is not set.

        :param method: Request method (eg. GET, POST, ..)
        """
        try:
            self.timeout.pop(method)
        except KeyError:
            pass

    def get_foreman_version(self):
        """
        Even if we have an api method that returns the foreman version, we need
        the version first to know its path, so instead of that we get the
        main page and extract the version from the footer.
        """
        params = dict(self._req_params)
        home_page = requests.get(
            self.url,
            verify=self.session.verify,
            timeout=self.get_timeout('GET'),
            **params
        )

        match = re.search(
            r'Version\s+(?P<version>[^\s<]+)?',
            home_page.text,
        )
        if match:
            return match.groupdict()['version']
        else:
            # on newer versions the version can be taken from the status page
            res = self.session.get(
                self.url + '/api/status',
                timeout=self.get_timeout('GET'),
                **params
            )
            if res.status_code < 200 or res.status_code >= 300:
                raise ForemanException(
                    res,
                    'Something went wrong:%s' % res_to_str(res)
                )
            res = res.json()
            if 'version' in res:
                return res['version']
            else:
                raise ForemanVersionException('Unable to get version')

    def _get_local_defs(self, strict=True):
        """
        Gets the cached definition or the any previous from the same major
        version if not strict passed.

        :param strict: Use any version that shared major version and has lower
             minor version if no total match found
        """
        version = parse_version(self.version)
        for cache_dir in [
            os.path.join(os.path.expanduser('~'), '.python-foreman'),
            os.path.dirname(__file__)
        ]:
            defs_path = os.path.join(cache_dir, 'definitions')
            files = glob.glob('%s/*-v%s.json' % (defs_path, self.api_version))
            files_version = [
                (fn, parse_version(os.path.basename(fn).rsplit('-', 1)[0]))
                for fn in files
            ]

            last_major_match = None
            for f_name, f_ver in sorted(files_version, key=lambda x: x[1]):
                if f_ver == version:
                    logger.debug('Found local cached version %s' % f_name)
                    return json.loads(open(f_name).read())
                if f_ver[:2] == version[:2]:
                    last_major_match = f_name
                if f_ver[0] > version[0]:
                    break

        if last_major_match:
            if strict:
                raise ForemanVersionException(
                    "Unable to get suitable json definition for Foreman "
                    "%s, but found a similar cached version %s, run "
                    "without strict flag to use it"
                    % (self.version, last_major_match))
            else:
                logger.warn(
                    "Not exact version found, got cached %s for Foreman %s",
                    last_major_match,
                    self.version,
                )
                return json.loads(open(last_major_match).read())
        raise ForemanVersionException(
            "No suitable cache found for version=%s api_version=%s strict=%s."
            "\nAvailable: %s"
            % (
                self.version,
                self.api_version,
                strict,
                '\n\t' + '\n\t'.join(files)
            )
        )

    def _get_remote_defs(self):
        """
        Retrieves the json definitions from remote foreman instance.
        """
        res = self.session.get(
            '%s/%s' % (self.url, 'apidoc/v%s.json' % self.api_version),
            timeout=self.get_timeout('GET'),
            **self._req_params
        )

        if res.ok:
            data = json.loads(res.text)
            defs_path = os.path.join(
                os.path.expanduser('~'),
                '.python-foreman',
                'definitions'
            )
            if not os.path.exists(defs_path):
                try:
                    os.makedirs(defs_path)
                except:
                    logger.debug('Unable to create cache dir %s', defs_path)
                    return data
            cache_fn = '%s/%s-v%s.json' % (
                defs_path, self.version,
                self.api_version,
            )
            try:
                with open(cache_fn, 'w') as cache_fd:
                    cache_fd.write(json.dumps(data, indent=4, default=str))
                    logger.debug('Wrote cache file %s', cache_fn)
            except:
                logger.debug('Unable to write cache file %s', cache_fn)
        else:
            if res.status_code == 404:
                logger.warn(
                    "Unable to get api definition from live Foreman instance "
                    "at '%s', you might want to set the strict_cache to False."
                    "\nNOTE: Make sure that you have set the config.use_cache "
                    "parameter to false in apipie initializer (usually "
                    "FOREMAN_HOME/config/initializers/apipie.rb).",
                    res.url,
                )
            raise ForemanVersionException(
                "There was an error trying to get api definition from %s/%s"
                % (self.url, 'apidoc/v%s.json' % self.api_version)
            )
        return data

    def _get_defs(self, use_cache, strict_cache):
        data = None
        if use_cache:
            try:
                logger.debug("Trying local cached definitions first")
                data = self._get_local_defs(strict=strict_cache)
            except ForemanVersionException as exc:
                logger.debug(exc)
        if not data:
            logger.debug("Checking remote server for definitions")
            data = self._get_remote_defs()
        return data

    def _generate_api_defs(self, use_cache=True, strict_cache=True):
        """
        This method populates the class with the api definitions.

        :param use_cache: If set, will try to get the definitions from the
            local cache first, then from the remote server, and at last will
            try to get the closest one from the local cached
        :param strict_cache: If True, will not accept a similar version cached
            definitions file as valid
        """
        data = self._get_defs(use_cache, strict_cache=strict_cache)

        resource_defs = {}
        # parse all the defs first, as they may define methods cross-resource
        for res_name, res_dct in six.iteritems(data["docs"]["resources"]):
            new_resource, extra_foreign_methods = parse_resource_definition(
                res_name.lower(),
                res_dct,
            )
            # if the resource did already exist (for example, was defined
            # through a foreign method by enother resource), complain if it
            # overwrites any methods
            if res_name in resource_defs:
                old_res = resource_defs[res_name]
                for prop_name, prop_val in six.iteritems(new_resource):
                    if (
                        prop_name == '_own_methods' and
                        prop_name in new_resource
                    ):
                        old_res[prop_name].union(prop_val)
                        continue
                    # skip internal/private/magic methods
                    if prop_name.startswith('_'):
                        continue
                    if prop_name in old_res:
                        logger.warning(
                            "There is conflict trying to redefine method "
                            "(%s) with foreign method: \n"
                            "\tapipie_resource: %s\n",
                            prop_name,
                            res_name,
                        )
                        continue
                    old_res[prop_name] = prop_val
            else:
                resource_defs[res_name] = new_resource

            # update the other resources with the foreign methods, create
            # the resources if not there yet, merge if it already exists
            for f_res_name, f_methods in six.iteritems(extra_foreign_methods):
                methods = resource_defs.setdefault(
                    f_res_name,
                    {'_own_methods': set()},
                )

                for f_mname, f_method in six.iteritems(f_methods):
                    if f_mname in methods:
                        logger.warning(
                            "There is conflict trying to redefine method "
                            "(%s) with foreign method: \n"
                            "\tapipie_resource: %s\n",
                            f_mname,
                            f_res_name,
                        )
                        continue
                    methods[f_mname] = f_method
                    methods['_own_methods'].add(f_mname)

        # Finally ceate the resource classes for all the collected resources
        # instantiate and bind them to this class
        for resource_name, resource_data in six.iteritems(resource_defs):
            new_resource = ResourceMeta.__new__(
                ResourceMeta,
                str(resource_name),
                (Resource,),
                resource_data,
            )
            if not resource_data['_own_methods']:
                logger.debug('Skipping empty resource %s' % resource_name)
                continue
            instance = new_resource(self)
            setattr(self, resource_name, instance)

    def _process_request_result(self, res):
        """Generic function to process the result of an HTTP request"""
        if res.status_code < 200 or res.status_code >= 300:
            if res.status_code == 404:
                return []
            elif res.status_code == 406:
                raise Unacceptable(res, None)
            raise ForemanException(
                res,
                'Something went wrong:%s' % res_to_str(res)
            )
        try:
            return OLD_REQ and res.json or res.json()
        except ValueError:
            return res.text

    def do_get(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        res = self.session.get(
            '%s%s' % (self.url, url),
            params=kwargs,
            timeout=self.get_timeout('GET'),
            **self._req_params
        )
        return self._process_request_result(res)

    def do_post(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        data = json.dumps(kwargs)
        res = self.session.post(
            '%s%s' % (self.url, url),
            data=data,
            timeout=self.get_timeout('POST'),
            **self._req_params
        )
        return self._process_request_result(res)

    def do_put(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        data = json.dumps(kwargs)
        res = self.session.put(
            '%s%s' % (self.url, url),
            data=data,
            timeout=self.get_timeout('PUT'),
            **self._req_params
        )
        return self._process_request_result(res)

    def do_delete(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        res = self.session.delete(
            '%s%s' % (self.url, url),
            timeout=self.get_timeout('DELETE'),
            **self._req_params
        )
        return self._process_request_result(res)

#!/usr/bin/env python
#encoding: utf-8
"""
This module provides acces to the API of a foreman server
"""
import re
import json
import copy
import types
import requests
import logging
import glob
try:
    import foreman_plugins
    import os.path
    import pkgutil
    pkg_path = os.path.dirname(foreman_plugins.__file__)
    plugins = [name for _, name, _ in pkgutil.iter_modules([pkg_path])]
except ImportError:
    plugins = []


if requests.__version__.split('.', 1)[0] == '0':
    OLD_REQ = True
else:
    OLD_REQ = False


def ver_cmp(ver_a, ver_b):
    ver_a = ver_a.split('-')[0].split('.')
    ver_b = ver_b.split('-')[0].split('.')
    return cmp(ver_a, ver_b)


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


class ResourceMeta(type):
    """
    This type composes methods for resource class
    """
    params_reg = re.compile(":[^/]+")
    multi_api_reg = re.compile(r'/([a-z_]+)s/(:\1_id)/([a-z_]+)(?:/(:id))?')
    exclude_html_reg = re.compile('</?[^>/]+/?>')

    def __new__(meta, name, bases, dct):
        if name == 'Resource':  # Skip base class
            return type.__new__(meta, name, bases, dct)

        # NOTE: regarding to __module__, it will be better to close
        # these classes into own module per each Foreman instance.
        # it could cause problems in case of having more instances
        # connected to different versions of foreman.
        new_dict = {'__module__': dct.get('__module__', __name__),
                    '__doc__': dct['full_description'],
                    '_resource_name': name,
                    '_foreign_methods': {}}

        for definition in dct['methods']:

            for api in definition['apis']:
                m = meta.multi_api_reg.search(api['api_url'])
                if m:
                    # Multi-api match
                    resource, _, _, _ = m.groups()
                    new_definition = copy.deepcopy(definition)
                    new_definition['name'] += "_%s" % name

                    resources = new_dict['_foreign_methods']
                    # NOTE: adding 's' in order to create plural
                    # WARN: may cause problem with 'es'
                    functions = resources.setdefault(resource+'s', {})

                    func = meta.create_func(new_definition, api)
                    functions[new_definition['name']] = func
                else:
                    func = meta.create_func(definition, api)
                    new_dict[definition['name']] = func

        # element_name => ElementName
        cls_name = ''.join([x.capitalize() for x in name.split('_')])
        return type.__new__(meta, cls_name, bases, new_dict)

    @classmethod
    def create_param_doc(meta, param, prefix=None):
        """
        Generate documentation for single parameter of function
        :param param: dict contains info about parameter
        :param sub: prefix string for recursive purposes
        """
        desc = meta.exclude_html_reg.sub('', param['description']).strip()
        if not desc:
            desc = "<no description>"
        name = param['name']
        if prefix:
            name = "%s[%s]" % (prefix, name)
        doc_ = ":param %s: %s; %s" % (name, desc, param['validator'])
        if param['required']:
            doc_ += " (REQUIRED)"
        for param in param.get('params', []):
            doc_ += "\n" + meta.create_param_doc(param, name)
        return doc_

    @classmethod
    def create_func(meta, definition, api):
        """
        Generate function for specific method and using specific api
        :param definition: dict contains definition of function
        :param api: dict contains api URL
        """
        params = [x.strip(":")
                  for x in meta.params_reg.findall(api['api_url'])]

        keywords = []
        params_def = []
        params_doc = ""

        for param in definition['params']:
            params_doc += meta.create_param_doc(param) + "\n"
            if param['name'] not in params:
                keywords.append(param['name'])
                params_def.append("%s=None" % param['name'])

        params_def = params + params_def

        func_head = 'def {0}(self, {1}):'.format(definition['name'],
                                                 ', '.join(params_def))
        code_body = (
            '   _vars_ = locals()\n'
            '   _url = self._fill_url("{1}", _vars_, {2})\n'
            '   _kwargs = dict((k, _vars_[k]) for k in {3} if _vars_[k])\n'
            '   return self._f.do_{0}(_url, _kwargs)')
        code_body = code_body.format(api['http_method'].lower(),
                                     api['api_url'], params, keywords)

        code = [func_head,
                '   """',
                api['short_description'] or '',
                '',
                params_doc,
                '   """',
                code_body]

        code = '\n'.join(code)

        exec code
        return locals()[definition['name']]


class Resource(object):
    """
    Provides entry point for specific resource
    """
    __metaclass__ = ResourceMeta
    _params_reg = re.compile(":([^/]+)")

    def __init__(self, foreman):
        """
        :param foreman: instance of Foreman class
        """
        self._f = foreman
        # Preserve backward compatibility with old interface
        for method_name in ('index', 'show', 'update', 'destroy'):
            method = getattr(self, method_name, None)
            method_name = "%s_%s" % (method_name, self._resource_name)
            if method:
                setattr(self._f, method_name, method)

    def _fill_url(self, url, vars_, params):
        kwargs = dict((k, vars_[k]) for k in params)
        url = self._params_reg.sub('{\\1}', url)
        return url.format(**kwargs)


class MetaForeman(type):
    def __new__(meta, cls_name, bases, attrs):
        """
        This class is called when defining the Foreman class, and populates it
        with the defined methods
        """
        entires = {'name': 'plugins',
                   'methods': [],
                   'full_description': "Binds foreman_plugins"}
        for plugin in (pl for pl in plugins if not pl.startswith('_')):
            try:
                myplugin = __import__('foreman_plugins.' + plugin, globals(),
                                      locals(),
                                      ['DEFS'])
            except ImportError:
                logging.error('Unable to import plugin module %s'
                              % plugin)
                continue
            for mname, funcs in myplugin.DEFS.iteritems():
                methods = meta.convert_plugin_def(mname, funcs)
                entires['methods'].extend(methods)

        def _init(self, foreman):
            super(self.__class__, self).__init__(foreman)
            for name, value in self.__class__.__dict__.iteritems():
                if isinstance(value, types.FunctionType) and name[0] != '_':
                    setattr(self._f, name, getattr(self, name))

        plugins_cls = ResourceMeta.__new__(ResourceMeta, 'plugins',
                                           (Resource,), entires)
        plugins_cls.__init__ = _init
        attrs['_plugins_resources'] = plugins_cls
        return type.__new__(meta, cls_name, bases, attrs)

    @classmethod
    def convert_plugin_def(meta, mname, funcs):
        methods = []
        for fname, params in funcs.iteritems():
            method = {'apis': [{'short_description': 'no-doc'}],
                      'params': []}
            if mname in ['GET', 'PUT', 'POST', 'DELETE']:
                full_fname = fname
                method['apis'][0]['http_method'] = mname
            else:
                full_fname = '%s_%s' % (fname, mname)
                method['apis'][0]['http_method'] = 'GET'
            method['apis'][0]['api_url'] = '/api/' + full_fname
            method['name'] = full_fname
            for pname, pdef in params.iteritems():
                doc_ = "Must be %s" % pdef['ptype']
                param = {'name': pname,
                         'validator': doc_,
                         'description': doc_,
                         'required': pdef['required']}
                method['params'].append(param)
            methods.append(method)
        return methods


class Foreman(object):
    """
    Main client class.
    """
    __metaclass__ = MetaForeman

    def __init__(self, url, auth=None, version=None, api_version=2,
                 use_cache=True):
        """
        :param url: Full url to the foreman server
        :param auth: Tuple with the user and the pass
        :param version: Foreman version (will autodetect by default)
        :param api_version: Version of the api to use (2 by default)
        :param use_cache: if True, will use local api definitions, if False,
            will try to get them from the remote Foreman instance (it needs
            you to have disabled use_cache in the apipie configuration in your
            foreman instance)
        """
        self.url = url
        self.session = requests.Session()
        self._req_params = {
            'verify': False,
            }
        if auth is not None:
            self.session.auth = auth
        self.session.headers.update(
            {
                'Accept': 'application/json; version=%s' % api_version,
                'Content-type': 'application/json',
            })
        if version is None:
            version = self.get_foreman_version()
        self._generate_api_defs(version, api_version, use_cache)

        # Instantiate plugins
        self.plugins = self._plugins_resources(self)

    def get_foreman_version(self):
        """
        Even if we have an api method that return the foreman version, we need
        the version first to know it's path, so instead of that we get the
        main page and extract the version from the footer.
        """
        params = dict(self._req_params)
        home_page = self.session.get(self.url, **params)
        match = re.search(r'Version\s+(?P<version>\S+)', home_page.text)
        if match:
            return match.groupdict()['version']
        else:
            # on newer versions the version can be taken from the status page
            res = self.session.get(self.url + '/api/status', **params)
            if res.status_code < 200 or res.status_code >= 300:
                logging.error(res_to_str(res))
                raise ForemanException(res, 'Something went wrong')
            res = res.json()
            if 'version' in res:
                return res['version']
            else:
                raise ForemanVersionException('Unable to get version')

    def _get_local_defs(self, version, api_version):
        defs_path = os.path.join(os.path.dirname(__file__), 'definitions')
        files = glob.glob('%s/*-v%s.json' % (defs_path, api_version))
        last_major_match = None
        for f_name in sorted(files):
            f_ver = os.path.basename(f_name).split('-')[0]
            if f_ver == version:
                return json.loads(open(f_name).read())
            if f_ver.split('.')[:2] == version.split('.')[:2]:
                last_major_match = f_name
            if ver_cmp(f_ver, version) < 0:
                logging.warn("Not exact version found, using %s from cache "
                             "for Foreman %s" % (f_ver, version))
                return json.loads(open(f_name).read())
        if last_major_match:
            logging.warn("Not exact version found, using %s from cache "
                         "for Foreman %s" % (f_ver, version))
            return json.loads(open(last_major_match).read())
        raise ForemanVersionException(
            "No suitable cache found for version=%s api_version=%s."
            "\nAvailable: %s"
            % (version, api_version, '\n\t' + '\n\t'.join(files)))

    def _generate_api_defs(self, version, api_version, use_cache=True):
        if use_cache:
            data = self._get_local_defs(version, api_version)
        else:
            res = self.session.get(
                '%s/%s' % (self.url, 'apidoc/v%s.json' % version),
                **self._req_params)
            if res.ok:
                data = json.loads(res.text)
            if res.status_code == 404:
                logging.warn(
                    "Unable to get api definition from live foreman instance "
                    "at '%s', trying cache.\nNOTE: Make sure that you have "
                    "set the config.use_cache parameter to false in apipie "
                    "initializer (usually "
                    "FOREMAN_HOME/config/initializers/apipie.rb)."
                    % res.url)
                data = self._get_local_defs(version, api_version)
            else:
                raise ForemanVersionException(
                    "There was an error trying to get api definition from %s"
                    % self.url)
        resources = {}
        for name, entires in data['docs']["resources"].iteritems():
            new_resource = ResourceMeta.__new__(ResourceMeta, str(name),
                                                (Resource,), entires)
            resources[name] = new_resource
        for name, resource in resources.iteritems():
            for fname, ffunctions in resource._foreign_methods.iteritems():
                for func_name, func in ffunctions.iteritems():
                    setattr(resources[fname], func_name, func)
        for name, resource in resources.iteritems():
            instance = resource(self)
            setattr(self, resource._resource_name, instance)

    def _process_request_result(self, res):
        if res.status_code < 200 or res.status_code >= 300:
            if res.status_code == 404:
                return []
            elif res.status_code == 406:
                raise Unacceptable(res, None)
            logging.error(res_to_str(res))
            raise ForemanException(res, 'Something went wrong')
        try:
            return OLD_REQ and res.json or res.json()
        except requests.JSONDecodeError:
            return res.text

    def do_get(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        res = self.session.get('%s%s' % (self.url, url),
                               params=kwargs, **self._req_params)
        return self._process_request_result(res)

    def do_post(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        data = json.dumps(kwargs)
        res = self.session.post('%s%s' % (self.url, url),
                                data=data, **self._req_params)
        return self._process_request_result(res)

    def do_put(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        data = json.dumps(kwargs)
        res = self.session.put('%s%s' % (self.url, url),
                               data=data, **self._req_params)
        return self._process_request_result(res)

    def do_delete(self, url, kwargs):
        """
        :param url: relative url to resource
        :param kwargs: parameters for the api call
        """
        res = self.session.delete('%s%s' % (self.url, url),
                                  **self._req_params)
        return self._process_request_result(res)

#!/usr/bin/env python
#encoding: utf-8
"""
This module provides acces to the API of a foreman server
"""

import os
import re
import logging
import json
import requests
import pprint
try:
    import definitions as defs
    download_defs = False
except ImportError, e:
    download_defs = True
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


BASE_DOC_URL = "http://theforeman.org/api"


def get_methods_urls():
    """
    Get the first level of the pages of the documentation
    """
    methodslist = requests.get(BASE_DOC_URL + '/apidoc.html').text
    match_method = re.compile(r'.*(?P<url>/apidoc/(?P<main>[^/]+)/'
                              r'(?P<mtype>[^/]+).html)')
    methods = {}
    for line in methodslist.splitlines():
        match = match_method.match(line)
        if match:
            res = match.groupdict()
            if res['main'] not in methods:
                methods[res['main']] = {}
            methods[res['main']][res['mtype']] = res['url']
    return methods


def get_method_definition(method_url):
    """
    :param method_url: relative url to the method's documentation page

    For a specific method url doc page, return it's definition
    """
    method_page = requests.get(BASE_DOC_URL + '/' + method_url).text
    method_page = method_page.splitlines()
    method_page.reverse()
    match_def = re.compile(r'.*((?P<required>(required|optional))|'
                           r'<strong>(?P<pname>[^<]+)</strong>|'
                           r'Value: Must (be (an? )?|match )(?P<ptype>.+))')
    params = {}
    started = None
    while method_page:
        line = method_page.pop()
        if not started:
            started = re.match(r'.*<h2>Params</h2>', line)
            continue
        method_info = match_def.match(line)
        if method_info:
            newinfo = method_info.groupdict()
            for name, val in newinfo.iteritems():
                if val:
                    val = str(val)
                    if name == 'ptype':
                        if val == '&#x27;true&#x27; or &#x27;false&#x27;':
                            val = "'true' or 'false'"
                    if name == 'pname':
                        params[val] = {}
                        current_param = params[val]
                    else:
                        if name == 'required':
                            val = val == 'required'
                        current_param[str(name)] = val
    return params


def generate_defs_file(fname='definitions.py'):
    """
    :param fname: Name of the file todump the definitoins to.

    Fetch the docs and generate the definitions of the api methods.
    """
    all_defs = {}
    for model, methods in get_methods_urls().iteritems():
        model_def = {}
        for mname, murl in methods.iteritems():
            mdef = get_method_definition(murl)
            model_def.update({str(mname): mdef})
        all_defs[str(model)] = model_def
    ## Add the special 'status' case
    with open(fname, 'w') as fd_defs:
        fd_defs.write('DEFS = ')
        fd_defs.write(pprint.pformat(all_defs))


def gen_fun_line(params):
    """
    :param params: Dict with the funciton parameters as found in the
    definitions file

    Generates the python code that defines a function from it's definition
    """
    args_str = ['self']
    default_args = []
    for arg, val in params.iteritems():
        if '[' in arg:
            continue
        if val['required']:
            args_str.append('%s' % arg.strip())
        else:
            default_args.append('%s=None' % arg.strip())
    return ', '.join(args_str) + ', ' + ', '.join(default_args)


def gen_fun_doc(fdef):
    """
    :param fdef: Function definition as found in the definitions file

    Generate the documtation for the given function definition
    """
    doc_str = ''
    for arg, val in fdef.iteritems():
        arg = arg.strip()
        doc_str += '\n\t:param %s: type %s, %s' % (
            arg, val['ptype'].strip(),
            val['required'] and 'required' or 'optional')
    return doc_str


def get_funct(fname, mname, fdef):
    """
    :param fname: Funtion name
    :param fdef: Function definition as in the definitions file


    Generate the function from the given function and definition
    """
    params = ['{0}={0}'.format(i.strip())
              for i in fdef.iterkeys()
              if '[' not in i]
    if mname in ['GET', 'POST', 'PUT', 'DELETE']:
        fun_name, fname, mname = fname, mname, fname
    else:
        fun_name = fname + '_' + mname
    code_str = '''
def {5}({0}):
    """
    {1}
    """
    return self.send_request('{2}',mtype='{3}', {4})'''.format(
        gen_fun_line(fdef),
        gen_fun_doc(fdef),
        fname,
        mname,
        ', '.join(params),
        fun_name)
    exec code_str
    return locals()[fun_name]


## Before getting any further, make sure that the definitions file exists
if download_defs:
    fpath = os.path.dirname(os.path.abspath(__file__))
    logging.info("Downloading definitions for the first tine at "
                 + "%s/definitions.py" % fpath)
    generate_defs_file(fpath + '/definitions.py')
    import definitions as defs


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


class MetaForeman(type):
    def __new__(meta, cls_name, bases, attrs):
        """
        This class is called when defining the Foreman class, and populates it
        with the defined methods
        """
        for mname, funcs in defs.DEFS.iteritems():
            for fname, fdef in funcs.iteritems():
                full_fname = '%s_%s' % (fname, mname)
                newfunc = get_funct(fname, mname, fdef)
                attrs[full_fname] = newfunc
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
                for fname, fdef in funcs.iteritems():
                    if mname in ['GET', 'PUT', 'POST', 'DELETE']:
                        full_fname = fname
                    else:
                        full_fname = '%s_%s' % (fname, mname)
                    newfunc = get_funct(fname, mname, fdef)
                    attrs[full_fname] = newfunc
        return type.__new__(meta, cls_name, bases, attrs)


class Foreman():
    __metaclass__ = MetaForeman

    def __init__(self, url='http://localhost:3000', auth=None, version=None):
        """
        :param url: Full url to the foreman server
        :param auth: Tuple with the user and the pass
        :param version: Version string for the given foreman url. If None
        given it will try to autodiscover it from the main page's footer.

        Main client class.
        """
        self.url = url
        self.session = requests.Session()
        self._req_params = {
            'verify': False,
            }
        if auth is not None:
            self.session.auth = auth
        self.version = version or self.get_foreman_version()
        self._extra_url = ''
        if self.version.split('.')[1] >= 1:
            self._extra_url = '/api'
        self.session.headers.update(
            {
                'Accept': 'application/json',
                'Content-type': 'application/json',
            })

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
            # on newer versions the version is in the headers
            about_page = self.session.get(self.url + '/api', **params)
            if 'foreman_version' in about_page.headers:
                return about_page.headers['foreman_version']
            else:
                raise ForemanVersionException('Unable to get version')

    def send_request(self, rtype, mtype, **params):
        """
        :param rtype: Request type, one of ['index', 'show', 'status',
        'create', 'update', 'destroy', 'GET', 'POST', 'PUT', 'DELETE']
        :param mtype: Model type, the data model with wich we are interacting,
        for example host or environment.
        :param \*\*params: parameters for the api call
        """
        # get rid of unnecessary parameters
        topop = []
        for key, val in params.iteritems():
            if val is None:
                topop.append(key)
        for key in topop:
            params.pop(key)
        if rtype in ['index', 'show', 'status',
                     'bootfiles', 'build_pxe_default',
                     'GET']:
            res = self.do_get(rtype, mtype, **params)
        elif rtype in ['create', 'POST']:
            res = self.do_post(rtype, mtype, **params)
        elif rtype in ['update', 'PUT']:
            res = self.do_put(rtype, mtype, **params)
        elif rtype in ['destroy', 'DEL']:
            res = self.do_delete(rtype, mtype, **params)
        else:
            raise Exception("Wrong method type %s" % rtype)
        if res.status_code < 200 or res.status_code >= 300:
            if res.status_code == 404:
                return []
            elif res.status_code == 406:
                raise Unacceptable(res, None)
            logging.error(res_to_str(res))
            raise ForemanException(res, 'Something went wrong')
        try:
            return OLD_REQ and res.json or res.json()
        except requests.JSONDecodeError, e:
            return res.text

    def do_get(self, rtype, mtype, **kwargs):
        """
        :param rtype: Request type, one of ['index', 'show', 'status',
        'create', 'update', 'destroy']
        :param mtype: Model type, the data model with wich we are interacting,
        for example host or environment.
        :param \*\*kwargs: parameters for the api call
        """
        ## The special 'home' model type does not have the same url format
        if not self.session:
            self.session = requests.Session()
        if mtype == 'home':
            res = self.session.get(
                '%s/%s' % (
                    self.url + self._extra_url,
                    rtype == 'status' and rtype or ''),
                params=kwargs,
                **self._req_params)
        elif rtype in ['index', 'GET']:
            res = self.session.get(
                '%s/%s' % (
                    self.url + self._extra_url,
                    mtype),
                params=kwargs,
                **self._req_params)
        elif rtype == 'show':
            elem_id = kwargs.pop('id')
            res = self.session.get(
                '%s/%s/%s' % (
                    self.url + self._extra_url,
                    mtype,
                    elem_id),
                params=kwargs,
                **self._req_params)
        elif rtype == 'status':
            if not self.version.startswith('1.1'):
                raise ForemanVersionException(
                    'Not available for Foreman versions '
                    'below 1.1')
            elem_id = kwargs.pop('id')
            res = self.session.get(
                '%s/%s/%s/status' % (
                    self.url + self._extra_url,
                    mtype,
                    elem_id),
                params=kwargs,
                **self._req_params)
        elif rtype == 'bootfiles':
            elem_id = kwargs.pop('id')
            res = self.sessions.get(
                '%s/%s/%s/bootfiles' % (
                    self.url + self._extra_url,
                    mtype,
                    elem_id),
                params=kwargs,
                **self._req_params)
        elif rtype == 'build_pxe_default':
            res = self.session.get(
                '%s/%s/build_pxe_default' % (
                    self.url + self._extra_url,
                    mtype),
                params=kwargs,
                **self._req_params)
        return res

    def do_post(self, rtype, mtype, **kwargs):
        """
        :param rtype: Request type, one of ['index', 'show', 'status',
        'create', 'update', 'destroy']
        :param mtype: Model type, the data model with wich we are interacting,
        for example host or environment.
        :param \*\*kwargs: parameters for the api call
        """
        data = json.dumps(kwargs)
        if rtype in ['create', 'POST']:
            res = self.session.post(
                '%s/%s' % (
                    self.url + self._extra_url,
                    mtype),
                data=data,
                **self._req_params)
        return res

    def do_put(self, rtype, mtype, **kwargs):
        """
        :param rtype: Request type, one of ['index', 'show', 'status',
        'create', 'update', 'destroy']
        :param mtype: Model type, the data model with wich we are interacting,
        for example host or environment.
        :param \*\*kwargs: parameters for the api call
        """
        mid = kwargs.pop('id')
        data = json.dumps(kwargs)
        if rtype in ['PUT', 'update']:
            res = self.session.put(
                '%s/%s/%s' % (
                    self.url + self._extra_url,
                    mtype,
                    mid),
                data=data,
                **self._req_params)
        return res

    def do_delete(self, rtype, mtype, **kwargs):
        """
        :param rtype: Request type, one of ['index', 'show', 'status',
        'create', 'update', 'destroy']
        :param mtype: Model type, the data model with wich we are interacting,
        for example host or environment.
        :param \*\*kwargs: parameters for the api call
        """
        if rtype in ['DELETE', 'destroy']:
            elem_id = kwargs.pop('id')
            res = self.session.delete(
                '%s/%s/%s' % (
                    self.url + self._extra_url,
                    mtype,
                    elem_id),
                **self._req_params)
        return res

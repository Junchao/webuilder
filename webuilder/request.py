import itertools

import werkzeug

from urllib.parse import quote, unquote, parse_qsl
from tempfile import TemporaryFile
from io import BytesIO

from .helpers import cached_property, environ_value_to_unicode
from .datastructures import MultiDict, RequestHeader, FormDict, CookieDict


class BaseRequest:

    '''基本的请求类，封装了WSGI environ'''

    _incoming_body_limit=100*1024

    def __init__(self, environ=None):
        if environ:
            self.initialize(environ)
        else:
            self._environ={}

    def initialize(self, environ=None):
        if not isinstance(environ, dict):
            raise TypeError('WSGI environ must be a dictionary, %s got.'
                            %type(environ))
        self._environ=environ

    @property
    def environ(self):
        return self._environ.copy()

    @property
    def path(self):
        path=environ_value_to_unicode(
            self._environ.get('PATH_INFO', ''), encoding='utf-8')
        return '/'+path.lstrip('/')

    @property
    def raw_query_string(self):
        qs=self._environ.get('QUERY_STRING', '')
        return qs

    @property
    def url(self):
        url=''
        path=quote(self.path)
        qs=self.raw_query_string
        if qs:
            url=path+'?'+qs
        return url

    @cached_property
    def full_url(self):
        env=self.environ
        url=env['wsgi.url_scheme']+'://'
        if env.get('HTTP_HOST'):
            url+=env['HTTP_HOST']
        else:
            url+=env['SERVER_NAME']
            if env['wsgi.url_scheme']=='https':
                if env['SERVER_PORT']!='443':
                    url+=':'+env['SERVER_PORT']
                else:
                    if env['SERVER_PORT']!='80':
                        url+=':'+env['SERVER_PORT']
        
        url+=self.url
        return url

    @property
    def host(self):
        return werkzeug.wsgi.get_host(self.environ)

    @property
    def method(self):
        return self._environ.get('REQUEST_METHOD', 'GET').upper()

    @property
    def header(self):
        header=RequestHeader(self.environ)
        return header
    
    @property
    def content_type(self):
        content_type=self._environ.get('CONTENT_TYPE', 'text/html').split(';', 1)[0]
        return content_type.lower()

    @property
    def content_length(self):
        return int(self._environ.get('CONTENT_LENGTH', 0))

    @cached_property
    def cookie(self):
        cookie=CookieDict()
        environ_cookies=self._environ.get('HTTP_COOKIE', '')
        if environ_cookies:
            cookies_list=environ_cookies.split(';')
            for _cookie in cookies_list:
                cookie_pair=_cookie.split('=', 1)
                key, value=cookie_pair[0], unquote(cookie_pair[-1])
                cookie[key]=value
        return cookie

    @property
    #不用cached_property，因为每次获取body都要seek。
    def body(self):
        try:
            incoming_body=self.environ['wsgi.input_seekable']
        except KeyError:
            pass
        else:
            incoming_body.seek(0)
            return incoming_body

        try:
            incoming_body=self.environ['wsgi.input']
        except KeyError:
            self._environ['wsgi.input_seekable']=BytesIO()
            return self._environ['wsgi.input_seekable']

        content_length=self.content_length
        if content_length<=self._incoming_body_limit:
            body=BytesIO()
            body.write(incoming_body.read(content_length))
        else:
            body=TemporaryFile() #默认模式w+b
            while content_length>0:
                data=incoming_body.read(min(content_length, self._incoming_body_limit))
                body.write(data)
                content_length-=len(data)

        body.seek(0)
        self._environ['wsgi.input_seekable']=body
        return self._environ['wsgi.input_seekable']

    @cached_property
    #暂不支持上传文件，不太好写...
    def POST(self):
        if not self.method=='POST':
            raise ValueError('Not a post request.')
        else:
            post_data_dict=MultiDict()

        if self.content_type=='application/x-www-form-urlencoded':
            post_data_str=self.body.read().decode('latin1')
            post_data_pairs=parse_qsl(post_data_str,
                                      keep_blank_values=True, encoding='latin1')
            post_data_dict.update(post_data_pairs)
        elif self.content_type=='multipart/form-data':
            raise NotImplementedError('Working on it...')
        else:
            raise TypeError('Not a html form submission.')
        
        return FormDict(post_data_dict)

    @cached_property
    def GET(self):
        qs_dict=MultiDict()
        raw_qs=self.raw_query_string
        if raw_qs:
            qs_pairs=parse_qsl(raw_qs, keep_blank_values=True, encoding='latin1')
            qs_dict.update(qs_pairs)
        return FormDict(qs_dict)

    @cached_property
    def form(self):
        #POST和GET
        qs_data=self.GET.get_raw_dict()
        try:
            post_data=self.POST.get_raw_dict()
        except (ValueError, TypeError):
            post_data=''
        
        qs_data.update(post_data)
        return FormDict(qs_data)

    def __getitem__(self, key):
        return self.header.get(key, '')

    def __len__(self):
        return len(self.header)

    def __iter__(self):
        return iter(self.header)

    def __str__(self):
        if self.form:
            form_data_pairs=self.form.items_all()
            return '\n'.join(['%s : %s' %(key, value) for key, value in form_data_pairs])
        else:
            return 'No forms data received.'


class Request(BaseRequest):
    pass
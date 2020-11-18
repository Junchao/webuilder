import datetime
import itertools

import arrow

from http.client import responses
from urllib.parse import quote

from .configuration import config
from .datastructures import ResponseHeader
from .templates import get_template_cls


_HTTP_STATUS_CODE=responses.copy()


class BaseResponse:

    '''设置响应header, body等的类'''

    _default_status='200 OK'
    _default_charset='utf-8'
    _default_content_type="text/html;charset=UTF-8"
    _default_body=''
    
    def __init__(self, template_file=None, body=None, **template_args):
        self._status=self._default_status
        self._header=ResponseHeader()
        self._cookies={}
        
        if template_file:
            self._body=None
            self.set_template(template_file, **template_args)
        elif body:
            self._template=None
            self.body=body
        else:
            self._template=self._body=None
       
    def _get_status(self):
        return self._status or self._default_status
    
    def _set_status(self, status):
        try:
            code=int(status)
        except (ValueError, TypeError):
            if ' ' in status:
                code, status=status.strip().split(1)
                if not int(code) in _HTTP_STATUS_CODE:
                    raise ValueError('HTTP code must be between 100 to 511, %d got.' %code)
                self._status='%s %s' %(code, status)
            else:
                raise ValueError('Bad HTTP status format %s.' %status)            
        else:
            try:
                status=_HTTP_STATUS_CODE[code]
                self._status='%d %s' (code, status)
            except KeyError:
                raise ValueError('HTTP Status Code must be between 100 to 511, %d got.' %code)
    
    status=property(_get_status, _set_status)
    
    @property
    def code(self):
        code=self._status.split(' ', 1)[0]
        return int(code)
    
    @property
    def header(self):
        return self._header
    
    @property
    def headerlist(self):
        headerlist=list(self._header.items())
        if not 'Content-Type' in self._header:
            if self.get_body():
                headerlist.append(('Content-Type', self._default_content_type))
        if not 'Content-Length' in self._header:
            #如果body是generator，会报错。
            #暂不清楚怎么处理body是generator的情形。
            try:
                content_length=len(self.get_body()[0])
            except IndexError:
                content_length=0
            headerlist.append(('Content-Length', str(content_length)))
        if self._cookies:
            for cookie in self._cookies.values():
                headerlist.append(('Set-Cookie', cookie))
        return headerlist
                
    def _charset_get(self):
        content_type=self._header.get('Content-Type', '')
        if content_type:
            if 'charset=' in content_type:
                charset=content_type.split('charset=')[-1].split(';')[0].strip()
                return charset
        return self._default_charset

    def _charset_set(self, value):
        content_type=self._header.get('Content-Type', '')
        if not content_type:
            content_type=self._default_content_type
        if 'charset=' in content_type:
            _parts1, _parts2=content_type.split('charset=')
            if ';' in _parts2:
                _parts2=_parts2.split(';', 1)[-1]
            else:
                _parts2=''
            _parts1=_parts1 if _parts2 else _parts1.rstrip(';')
            content_type=_parts1+';'+_parts2+'charset=%s' %value
        else:
            content_type+=';'+'charset=%s' %value
        self._header['Content-Type']=content_type
    
    charset=property(_charset_get, _charset_set)    

    def set_cookie(self, name, value,  
                   max_age=None, expires=None, path='/', domain=None, 
                   secure=False, http_only=True):
        value=value if isinstance(value, str) else str(value)
        
        name, value=quote(name), quote(value)
        cookies_list=['%s=%s' %(name, value)]  
        cookies_list.append('Path=%s' %path)
        
        if expires:
            if isinstance(expires, datetime.datetime):
                expires=arrow.get(expires).format('ddd, DD MMM YYYY HH:mm:ss')+' '+'GMT'
            elif isinstance(expires, str):
                try:
                    expires=arrow.get(expires)
                except arrow.parser.ParserError as e:
                    raise ValueError('Bad expires time format %s' %expires) from e
                else:
                    expires=expires.format('ddd, DD MMM YYYY HH:mm:ss')+' '+'GMT'
            cookies_list.append('Expires=%s' %expires)
        elif max_age:
            try:
                max_age=int(float(max_age))
                cookies_list.append('Max-Age=%d' %max_age)     
            except (ValueError, TypeError) as e:
                raise ValueError('Bad max-age format.')
        if domain:
            cookies_list.append('Domain=%s' %domain)
        if secure:
            cookies_list.append('Secure')
        if http_only:
            cookies_list.append('HttpOnly')
        
        self._cookies[name]='; '.join(cookies_list)
    
    @property
    def cookies(self):
        if self._cookies:
            return '\n'.join(self._cookies.values())
        return None
    
    def delete_cookie(self, name, value='deleted', **kwargs):
        kwargs['expires']='1970-01-01 00:00:00'
        self.set_cookie(name=name, value=value, **kwargs)
    
    def _get_body(self):
        return self._body
    
    def _set_body(self, body):      
        #不能同时设置body和template。
        if self._template:
            raise TypeError('Can not set both body and template.')
        if not body:
            self._body=None
            return
        
        if isinstance(body, (tuple, list)):
            if not all(isinstance(item, (str, bytes)) for item in body):
                raise TypeError('Body iterable can only contain str/bytes')
            else:
                body=body[0][0:0].join(body)
        if isinstance(body, str):
            body=body.encode(self.charset)
        if isinstance(body, bytes):
            self._body=body
            return
        
        try:
            body=iter(body)
            first_yield=next(body)
            while not first_yield:
                first_yield=next(body)
        except StopIteration:
            raise ValueError('Body can not be empty.')
        except Exception:
            raise
        else:
            if isinstance(first_yield, str):
                body=map(lambda item:item.encode(self.charset),
                         itertools.chain([first_yield], body))
            elif isinstance(first_yield, bytes):
                body=itertools.chain([first_yield], body)
            else:
                raise TypeError('Unsupported body type.' %type(first_yield))        
            self._body=body
    
    body=property(_get_body, _set_body)
    
    def set_template(self, template_file, **template_args):
        if self._body:
            raise TypeError('Can not set both body and template.')
        if not template_file:
            self._template=None
            return
        
        try:
            template_engine=get_template_cls(
                config['TEMPLATE_ENGINE'])
        except KeyError as e:
            raise KeyError('Unsupported template engine %s.' 
                           %config['TEMPLATE_ENGINE']) from e  
        
        try:
            template_file_dir=config['TEMPLATE_FILE_DIR']
        except KeyError:
            config['TEMPLATE_FILE_DIR']='templates'
            template_file_dir=config['TEMPLATE_FILE_DIR']
            
        self._template=template_engine(
            template_file_dir, template_file, **template_args)
    
    @property
    def template(self):
        return self._template
    
    def get_body(self):
        if self._template:
            body=[self._template().encode('utf-8')]
        else:
            body=[self._body] if self._body else [self._default_body.encode(self.charset)]
        return body
    
    def copy(self):
        response=self.__class__()
        response._status=self._status
        response._header=self._header
        response._cookies=self._cookies
        
        if self._template:
            response._template=self._template
        else:
            response.body=self._body
        return response
    
    def __getitem__(self, key):
        return self._header[key]

    def __setitem__(self, key, value):
        self._header[key]=value
    
    def __delitem__(self, key):
        del self._header[key]
        
    def __str__(self):
        status_part='%s : %s' %('Status', self.status)
        header_part=['%s : %s' %(key, value) for key, value in self.headerlist]
        header_part.insert(0, status_part)
        return '\n'.join(header_part)


class ContentTypeMixin:

    def _content_type_get(self):
        content_type=self._header.get('Content-Type', '') or self._default_content_type
        return content_type.split(';', 1)[0]

    def _content_type_set(self, value):
        if not ';' in value:
            content_type=self._header.pop('Content-Type', '')
            if ';' in content_type:
                content_type_parts=content_type.split(';', 1)[-1]
                value+=';'+content_type_parts
        self._header['Content-Type']=value
        
    content_type=property(_content_type_get, _content_type_set)
    
    
class Response(BaseResponse, ContentTypeMixin):
    pass
from http.client import responses

from .exceptions import HTTPError
from .helpers import load_obj, func_has_args


_HTTP_STATUS_CODE=responses.copy()


_DEFAULT_ERROR_BODY='''<html>
<h1>
<center>%d %s</center>
<hr style="height:1px;border:none;border-top:1px solid #555555;" />
</h1>
</html>
'''


class Redirect(HTTPError):
    
    _default_status='303 See Other'
    _default_body=''
    
    def __init__(self, redirect_url=None, template_file=None, body=None, **template_args):
        HTTPError.__init__(self, template_file=template_file, body=body, **template_args)
        self.header['Location']=redirect_url


class NotModified(HTTPError):
    
    _default_status='304 Not Modified'
    _default_body='' 
    
    def __init__(self, last_modified=None, template_file=None, body=None, **template_args):
        HTTPError.__init__(self, template_file=template_file, body=body, **template_args)
        self.header['Last-Modified']=last_modified        


class BadRequest(HTTPError):
    
    _default_status='400 Bad Request'
    _default_body=_DEFAULT_ERROR_BODY %(400, 'Bad Request')


class Unauthorized(HTTPError):

    _default_status='401 Unauthorized'
    _default_body=_DEFAULT_ERROR_BODY %(401, 'Unauthorized')


class Forbidden(HTTPError):
    
    _default_status='403 Forbidden'
    _default_body=_DEFAULT_ERROR_BODY %(403, 'Forbidden')


class NotFound(HTTPError):
    
    _default_status='404 Not Found'
    _default_body=_DEFAULT_ERROR_BODY %(404, 'Not Found')
    

class MethodNotAllow(HTTPError):
    
    _default_status='405 Method Not Allow'
    _default_body=_DEFAULT_ERROR_BODY %(405, 'Method Not Allow')


class InternalServerError(HTTPError):
    
    _default_status='500 Internal Server Error'
    _default_body=_DEFAULT_ERROR_BODY %(500, 'Internal Server Error')
    

class ErrorHandler:

    '''处理HTTP Error的类'''

    def __init__(self):
        self.handlers={}
    
    def add_handler(self, code, handler):
        if isinstance(handler, str):
            handler=load_obj(handler)
        if not func_has_args(handler, 'request')==1:
            raise ValueError('Error handler must take exactly 1 positional argument request.')

        try:
            _=int(code)
        except (ValueError, TypeError) as e:
            raise ValueError('HTTP error code must be a integet, %s got.'
                             %type(code)) from e
        else:
            if int(code) in _HTTP_STATUS_CODE:
                self.handlers[int(code)]=handler
            else:
                raise ValueError('HTTP error code must be between 100 to 511.')    
    
    def handle_error(self, request, error):
        if error.body or error.template\
           or error.code not in self.handlers:
            response=error.create_response()
        else:
            try:
                response=self.handlers[error.code](request)
            except HTTPError as e:
                response=self.handle_error(request, e)
                
        return response
                
    
    
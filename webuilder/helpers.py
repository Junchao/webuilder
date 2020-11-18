import sys
import os
import mimetypes

from importlib import import_module

import arrow
    

class cached_property:
    
    '''被修饰的属性只计算一次，保存结果，下次直接返回。'''
    
    def __init__(self, func):
        self.func=func
        self.name=func.__name__
        self.__doc__=func.__doc__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        else:
            value=obj.__dict__[self.name]=self.func(obj)
            return value
        

def make_list(data):
    if isinstance(data, (list, tuple, set)):
        return list(data)
    else:
        return [data]


def get_module_dir(obj_name):
    try:
        path=os.path.dirname(os.path.abspath(sys.modules[obj_name].__file__))
        return path
    except (KeyError, AttributeError):
        return os.getcwd()
    
    
def func_has_args(func, *args):
    try:
        func_args=func.__code__.co_varnames[:func.__code__.co_argcount]
    except AttributeError as e:
        raise TypeError('Expect a function, %s got.' %type(func))

    for arg in args:
        if arg not in func_args:
            return False
    return len(func_args)


def load_obj(obj):
    module, target=obj.split(':', 1)
    if not module in sys.modules:
        import_module(module)  
    return getattr(sys.modules[module], target)


def is_iterable(obj):
    try:
        _=iter(obj)
    except TypeError:
        return False
    else:
        return True
    
    
def environ_value_to_unicode(environ_value, encoding='utf-8'):
    if isinstance(environ_value, bytes):
        return environ_value.decode(encoding)
    elif isinstance(environ_value, str):
        return environ_value.encode('latin1').decode(encoding)        
    

def make_static_file_router():
    from .configuration import config
    from .router import Router
    from .errors import NotFound, NotModified, Forbidden
    from .response import Response
    
    router=Router()
    
    @router.get('/static/<filename>')
    def serve_static_file(request, filename):
        try:
            statc_file_dir=config['STATIC_FILE_DIR']
        except KeyError:
            config['STATIC_FILE_DIR']='static'
            statc_file_dir=config['STATIC_FILE_DIR']        
            
        file_path=os.path.abspath(
            os.path.join(statc_file_dir, filename))

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            raise NotFound
        if not os.access(file_path, os.R_OK):
            raise Forbidden
    
        last_modified_sec=os.path.getmtime(file_path)
        last_modified_str=arrow.get(last_modified_sec).format(
            'ddd, DD MMM YYYY HH:mm:ss')+' '+'GMT'
        
        if_modified_since_str=request.environ.get('IF_MODIFIED_SINCE', '')
        if if_modified_since_str:
            if_modified_since_str.split(',', 1)[-1]
            if_modified_since_sec=arrow.get(if_modified_since_str).timestamp
            if if_modified_since_sec>last_modified_sec:
                response=NotModified(last_modified=last_modified).make_response()
                return response
    
        response=Response()
    
        mimetype, encoding=mimetypes.guess_type(file_path)
        mimetype=mimetype or 'text/plain'
        response.header['Content-Type']=mimetype
        if encoding:
            response.header['Content-Encoding']=encoding
        response.header['Last-Modified']=last_modified_str
    
        with open(file_path, 'rb') as f:
            response.body=f.read()
        return response
    
    return router
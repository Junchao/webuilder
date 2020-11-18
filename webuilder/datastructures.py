import os

from collections.abc import MutableMapping
from importlib.machinery import SourceFileLoader
from importlib import import_module

from .helpers import is_iterable, environ_value_to_unicode


class AppStack:

    '''app实例栈。'''

    def __init__(self, *apps):
        self._stack=list(apps)
    
    def push(self, app):
        self._stack.append(app)
    
    def pop(self):
        try:
            return self._stack.pop()
        except IndexError as e:
            raise IndexError('App stack is empty.') from e
    
    def top(self):
        try:
            return self._stack[-1]
        except IndexError as e:
            raise IndexError('App stack is empty.') from e        
    
    @property
    def empty(self):
        return False if self._stack else True
    
    def __len__(self):
        return len(self._stack)
    
    def __str__(self):
        return self._stack.__str__()


class EasyAccessMixin:

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key]=value

    def __delattr__(self, key):
        del self[key]
        

class EasyAccessDict(dict):

    '''通过属性获取键值的字典。'''

    def __init__(self, *args, **kwargs):
        if len(args)>1:
            raise TypeError('EasyAccessDict expect at most one positional argument, %d got.'
                            %len(arg))
        dict.__init__(self, *args, **kwargs)

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key]=value

    def __delattr__(self, key):
        del self[key]
        
 
class CookieDict(EasyAccessDict):

    '''cookies字典。'''

    pass


class SessionDict(dict):

    '''session字典。'''

    def __init__(self, sid=None):
        self._sid=sid
        dict.__init__(self)
    
    def _get_sid(self):
        return self._sid
    
    def _set_sid(self, sid):
        self._sid=str(sid)
        
    sid=property(_get_sid, _set_sid)


class BaseMultiDict(MutableMapping):

    '''基本的多值字典,获取时返回最后一个添加的值。'''

    def __init__(self, mapping=None):
        self.__dict__['_dict']={}
        if mapping:
            self.update(mapping)

    def add_values(self, key, *values):
        if not key in self:
            self._dict[key]=[]
        self._dict[key].extend(values)
    
    def set_values(self, key, *values):
        self._dict[key]=[]
        self._dict[key].extend(values)
    
    def __getitem__(self, key):
        return self._dict[key][-1]

    def __setitem__(self, key, value):
        self._dict.setdefault(key, []).append(value)

    def __delitem__(self, key):
        del self._dict[key]

    def __iter__(self):
        return (key for key in self._dict.keys())

    def __len__(self):
        return len(self._dict)

    def update(self, mapping):
        if isinstance(mapping, BaseMultiDict):
            mapping=mapping._dict
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                if is_iterable(value):
                    self.add_values(key, *value)
                else:
                    self[key]=value
        elif is_iterable(mapping):
            for key, value in mapping:
                self[key]=value
        else:
            raise TypeError('Expect a dict-like object or iterable containing key-value pairs, %s got.'
                            %type(mapping))

    def copy(self):
        return self.__class__(self)

    def get(self, key, index=-1, default=None):
        try:
            return self._dict[key][index]
        except (IndexError, KeyError):
            return default

    def get_list(self, key, default=None):
        return self._dict.get(key, default)
    
    def pop(self, key, index=-1):
        return self._dict.pop(key)[index]
    
    def pop_list(self, key):
        return self._dict.pop(key)

    def items_all(self):
        return ((key, value) for key, values in self._dict.items() for value in values)
    
    def popitem_all(self):
        return self._dict.popitem()
    
    def __str__(self):
        return self._dict.__str__()
    

class MultiDict(BaseMultiDict, EasyAccessMixin):
    pass
    
 
class FormDict(MultiDict):

    '''表单字典,只读。'''
    
    _default_encoding='utf-8'
    
    def __init__(self, mapping=None):
        self.__dict__['_dict']={}
        if mapping is not None:
            if not isinstance(mapping, BaseMultiDict):
                raise TypeError('Expect a BaseMultiDict object, %s got.' 
                                %type(mapping))
            else:
                self.__dict__['_raw_dict']=mapping
                #FormDict为只读，要通过父类update。
                MultiDict.update(self, mapping)
        self.__dict__['_encoding']=None
    
    def get_raw_dict(self):
        return self.__dict__['_raw_dict']
    
    def get_encoding(self):
        encoding=self.__dict__['_encoding'] or \
            self.__class__.__dict__['_default_encoding']
        return encoding

    def set_encoding(self, encoding):
        encoding=encoding if isinstance(encoding, str) else str(encoding)
        self.__dict__['_encoding']=encoding

    def _get_it_right(self, value):
        encoding=self.get_encoding()
        value=environ_value_to_unicode(value, encoding)
        return value

    def __getitem__(self, key):
        return self._get_it_right(
            MultiDict.__getitem__(self, key))

    def __setitem__(self, key, value):
        raise TypeError('FormDict is read-only.')

    def __delitem__(self, key):
        raise TypeError('FormDict is read-only.')

    def update(self, mapping=None):
        raise TypeError('FormDict is read-only.')

    def get(self, key, index=-1, default=None):
        return self._get_it_right(
            MultiDict.get(self, key=key, index=index, default=default))
    
    def get_list(self, key, default=None):
        _values_list=self._dict.get(key, default)
        if _values_list:
            values_list=[self._get_it_right(value) for value in _values_list]
            return values_list 
        return default
    
    def pop(self, key, index=-1):
        return self._get_it_right(
            MultiDict.pop(self, key=key, index=index))
    
    def pop_list(self, key):
        _values_list=self._dict.pop(key)
        value_list=[self._get_it_right(value) for value in _values_list]
        return value_list
        
    def items_all(self):
        _items_all=MultiDict.items_all(self)
        return ((key, self._get_it_right(value)) 
                for key, value in _items_all)


class BaseCaseInsensitiveDict(MutableMapping):

    '''基本的大小写不敏感的字典。'''

    def __init__(self, *args, **kwargs):
        if len(args)>1:
            raise TypeError('%s take at most 1 positonal argument, %d got.') %(
                self.__class__.__name__, len(args))
        self.__dict__['_dict']={}
        self.update(*args, **kwargs)        
    
    def __getitem__(self, key):
        return self._dict[key.lower()][-1]
    
    def __setitem__(self, key, value):
        self._dict[key.lower()]=(key, value)
    
    def __delitem__(self, key):
        del self._dict[key.lower()]
    
    def __len__(self):
        return len(self._dict)
    
    def __iter__(self):
        return (raw_key for raw_key, _ in self._dict.values())
    
    def __str__(self):
        return self._dict.__str__()
    
    def copy(self):
        return self.__class__(self._dict.values())    
    
    
class CaseInsensitiveDict(BaseCaseInsensitiveDict, EasyAccessMixin):
    pass


class RequestHeader(CaseInsensitiveDict):

    '''请求header字典，只读。'''

    def __init__(self, environ=None):
        if not environ is None:
            self.initialize(environ)
        else:
            self.__dict__['_dict']={}

    def initialize(self, environ=None):
        if not isinstance(environ, dict):
            raise TypeError('WSGI environ must be a dictionary, %s got.'
                            %type(environ))
        else:
            self.__dict__['_dict']={}
            for key, value in environ.items():
                if key.startswith('HTTP_'): 
                    key=self._normalize_key(key)
                    CaseInsensitiveDict.__setitem__(self, key, value)

    def _normalize_key(self, key):
        key=key.split('HTTP_')[-1].replace('_', '-').title()
        return key

    def __getitem__(self, key):
        key=self._normalize_key(key)
        return environ_value_to_unicode(
            CaseInsensitiveDict.__getitem__(self, key), encoding='utf-8')

    def __setitem__(self, key, value):
        raise TypeError('RequestHeader is read-only.')

    def __delitem__(self, key):
        raise TypeError('RequestHeader is read-only.')
    
    def __str__(self):
        return self._dict.__str__()
    
    
class ResponseHeader(CaseInsensitiveDict):

    '''设置响应header的字典。'''
    
    def __getitem__(self, key):
        key=self._normalize_key(key)
        return CaseInsensitiveDict.__getitem__(self, key)

    def __setitem__(self, key, value):
        key=self._normalize_key(key)
        value=value if isinstance(value, str) else str(value)
        CaseInsensitiveDict.__setitem__(self, key, value)

    def __delitem__(self, key):
        key=self._normalize_key(key)
        CaseInsensitiveDict.__delitem__(self, key)
        
    def _normalize_key(self, key):
        return key.replace('_', '-').title()    


class ConfigDict(CaseInsensitiveDict):

    '''config字典。'''

    _file_dir=[
        'STATIC_FILE_DIR',
        'TEMPLATE_FILE_DIR',
        'DATABASE_FILE',
        'SESSION_DIR'
    ]
    
    def load_from_dict(self, config_dict):
        for key, value in config_dict.items():
            self[key]=value

    def load_from_module(self, config_obj):
        '''import config_module
           
           d=ConfigDict()
           d.load_from_module(config_module)
           '''
        
        config=((key, getattr(config_obj, key)) 
                for key in dir(config_obj) if key.isupper())
        self.update(config)

    def load_from_file(self, config_file):
        '''
         d=ConfigDict()
         d.load_from_file('path/to/config_file.py)
         '''
        
        config_file_name=os.path.basename(
            os.path.normpath(config_file)).split('.')[0]
        config_file=SourceFileLoader(config_file_name, config_file).load_module()
        config=[(key, getattr(config_file, key))
                for key in dir(config_file) if key.isupper()]
        self.update(config)

    def load_from_str_module(self, config_module):
        '''
         d=ConfigDict()
         d.load_from_str_module('package.config_module')
         '''
        
        config_module=import_module(config_module)
        config=((key, getattr(config_module, key))
                for key in dir(config_module) if key.isupper())
        self.update(config)    
        
    def __setitem__(self, key, value):
        #设置路径时可以是相对于app实例的相对路径。
        key=key.upper()
        if key in self._file_dir:
            value=value if isinstance(value, str) else str(value)
            value=os.path.join(
                os.path.abspath(os.path.join(self['APP_DIR'], value)), '')
        CaseInsensitiveDict.__setitem__(self, key, value)
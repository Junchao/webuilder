import re

from urllib.parse import urlencode

from .helpers import load_obj, func_has_args, make_list


_SUPPORTED_METHODS=[
    'GET',
    'POST',
    'PUT',
    'DELETE',
    'HEAD'
]


#一共4个组，分别是static_part, name, type, pattern.
_PATH_PATTERN=re.compile(
    r'(?:'
    r'([^<]*)'
    r'(?:<([A-Za-z_][A-Za-z0-9_]*)'
    r'(?::(filter|re)'
    r':([^>]+))?>)'
    r')',
    re.VERBOSE
)


#动态部分的默认pattern
_DEFAULT_PATTERN=r'[^/]+'


_SUPPORTED_FILTERS={
    'int': r'\d+',
    'float': r'\d+\.\d+',
    'alpha': r'[A-Za-z]+',
    'word': r'\w+',
    'segment': r'[^/]+'
}


def add_filter(self, filter_name, pattern):
    pattern=pattern if isinstance(pattern, str) else str(pattern)
    _SUPPORTED_FILTERS[filter_name]=pattern


class Router:

    '''路由类'''

    def __init__(self):
        self.static_mappings={}
        self.dynamic_mappings={}      
        self.builders={}
    
    def add_mapping(self, path, methods, view_func=None):
        def decorator(view_func):
            if isinstance(view_func, str):
                view_func=load_obj(view_func)
            if not func_has_args(view_func, 'request'):
                raise TypeError('View function must take 1 positional argument request.')
            for method in make_list(methods):
                method=method.upper()
                if not method in _SUPPORTED_METHODS:
                    raise ValueError('Unsupported method %s.' %method)
                self._process_mapping(path, method, view_func)
            return view_func
        
        return decorator(view_func) if view_func else decorator
    
    def add_mappings(self, *mappings, **prefix):
        if prefix:
            try:
                _prefix=prefix.pop('prefix')
            except KeyError as e:
                raise TypeError('Keyword argument can only be prefix.') from e
            else:
                if prefix:
                    raise TypeError('Take at most 1 keyword argument prefix per mapping, %d got.' 
                                    %(len(prefix)+1))
        else:
            _prefix=''

        for mapping in mappings:
            if len(mapping)<2 or len(mapping)>3:
                raise TypeError('May have 2 or 3 items per mapping, %d got.' 
                                 %len(mapping))
            else:
                if len(mapping)==2:
                    self.add_mapping(_prefix+mapping[0], 'GET', mapping[-1])
                elif len(mapping)==3:
                    self.add_mapping(_prefix+mapping[0], mapping[1], mapping[-1])
    
    def _parse_path(self, path):
        pos=0
        for match_result in _PATH_PATTERN.finditer(path):
            group=match_result.groups()
            if group[0]:
                yield group[0], None, None, None
            yield None, group[1], group[2] or None, group[3] or None
            pos=match_result.end()
        if pos<len(path):
            yield path[pos:], None, None, None    
            
    def _process_mapping(self, path, method, view_func):
        path_pattern=''
        is_static=True
        builder=[]
        
        for _static_part,  _dynamic_part, _filter_or_re , _pattern in self._parse_path(path):
            _is_static=True
            if _static_part:
                path_pattern+=re.escape(_static_part)
                builder.append((_static_part, _is_static))
            elif _dynamic_part:
                is_static=_is_static=False
                if _filter_or_re:
                    if _filter_or_re=='filter':
                        try:
                            _pattern=_SUPPORTED_FILTERS[_pattern]
                        except KeyError as e:
                            raise ValueError('No such filter %s' %_pattern) from e
                    elif _filter_or_re=='re':
                        _pattern=_pattern
                else:
                    _pattern=_DEFAULT_PATTERN
                path_pattern+='(?P<%s>%s)' %(_dynamic_part, _pattern)
                builder.append((_dynamic_part, _is_static))

        self.builders[view_func.__name__]=builder

        if is_static:
            self.static_mappings.setdefault(method, {})
            self.static_mappings[method][path]=(view_func, None)
        else:
            path_pattern=re.compile('^(%s)$' %path_pattern)
            args=lambda url: path_pattern.match(url).groupdict()
            self.dynamic_mappings.setdefault(method, {})
            self.dynamic_mappings[method][path_pattern]=(view_func, args)        
    
    def get(self, path):
        return self.add_mapping(path, methods='GET')

    def post(self, path):
        return self.add_mapping(path, methods='POST')
    
    def put(self, path):
        raise NotImplementedError('Working on it...')
    
    def delete(self, path):
        raise NotImplementedError('Working on it...')
    
    def expose(self, path):
        return self.add_mapping(path, methods=['GET', 'POST'])
            
    def match(self, method, url):
        if method in self.static_mappings:
            if url in self.static_mappings[method]:
                view_func, _=self.static_mappings[method][url]
                return view_func, {}
        elif method in self.dynamic_mappings:
            for path_pattern in self.dynamic_mappings[method]:
                if path_pattern.match(url):
                    view_func, args=self.dynamic_mappings[method][path_pattern]
                    return view_func, args(url)
        return None
    
    def url_for(self, view_func_name, **query):
        try:
            builder=self.builders[view_func_name]
        except KeyError as e:
            raise ValueError('No such mapping %s' %name) from e
        else:
            url=''
            for url_parts, is_static in builder:
                if is_static:
                    url+=url_parts
                else:
                    try:
                        url+=str(query.pop(url_parts))
                    except KeyError as e:
                        raise TypeError('Missing argument %s to build url.' %url_parts) from e
        
        #如果query还有剩余，作为查询部分(?后面)
        if query:
            url+='?'+urlencode(query)
        return url
    
    def combine(self, *routers):
        for router in routers:
            self.static_mappings.update(router.static_mappings)
            self.dynamic_mappings.update(router.dynamic_mappings)
            self.builders.update(router.builders)
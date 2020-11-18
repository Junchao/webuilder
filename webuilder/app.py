from werkzeug.debug import DebuggedApplication

from .configuration import config
from .datastructures import AppStack
from .request import Request
from .router import Router
from .helpers import get_module_dir, make_static_file_router
from .exceptions import HTTPError
from .errors import NotFound, InternalServerError


app_stack=AppStack()


class App:
    
    '''WSGI Application Callable'''
    
    def __init__(self, app_module_name, *routers):
        self.routers=list(routers)
        self.error_handler=None
        
        _app_dir=get_module_dir(app_module_name)
        config['APP_DIR']=_app_dir      
        
        if config['SERVE_STATIC_FILE']:
            _static_file_router=make_static_file_router()
            self.routers.append(_static_file_router)
        
        app_stack.push(self)
    
    def add_routers(self, *routers):
        self.routers.extend(routers)
    
    def add_error_handler(self, handler):
        self.error_handler=handler
    
    def get_view_func(self, method, path):
        for router in self.routers:
            result=router.match(method, path)
            if result:
                return result
        raise NotFound
    
    def _handle_request(self, request):
        try:
            view_func, args=self.get_view_func(request.method, request.path)
        except NotFound as e:
            if self.error_handler:
                response=self.error_handler.handle_error(request, e)
            else:
                response=e.create_response()
            return response
        
        try:
            response=view_func(request=request, **args)
        except HTTPError as e:
            if self.error_handler:
                response=self.error_handler.handle_error(request, e)
            else:
                response=e.create_response()
        
        return response
    
    def _wsgiapp(self, environ, start_response):
        request=Request(environ)
        try:
            response=self._handle_request(request)
            start_response(response.status, response.headerlist)
            return response.get_body()
        except KeyboardInterrupt:
            pass
        except Exception:
            if config['DEBUG']:
                raise
            else:
                internal_server_error=InternalServerError()
                if self.error_handler:
                    try:
                        response=self.error_handler.handle_error(
                            request, internal_server_error)
                    except Exception:
                        #如果自定义处理500的handler也出错，就用默认500页面。
                        response=InternalServerError().create_response()
                else:
                    response=internal_server_error.create_response()  
                start_response(response.status, response.headerlist)
                return response.get_body()                
                        
    def __call__(self, environ, start_response):
        app=DebuggedApplication(app=self._wsgiapp)
        return app(environ, start_response)
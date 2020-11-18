from .configuration import config


class BaseServer:

    '''所有服务器类的父类。'''

    def __init__(self):
        pass

    def run(self, app, host='127.0.0.1', port=8080):
        raise NotImplementedError


try:
    from waitress import serve

    class WaitressServer(BaseServer):

        def run(self, app, host='127.0.0.1', port=8080):
            serve(app=app, host=host, port=port)          

except ImportError:
    pass


try:
    import cherrypy

    class CherryPyServer(BaseServer):

        def run(self, app, host='127.0.0.1', port=8080):
            import cherrypy

            cherrypy.tree.graft(app, '/')
            cherrypy.server.unsubscribe()
            server=cherrypy._cpserver.Server()

            server.socket_host=host
            server.socket_port=port
            server.subscribe()

            cherrypy.engine.start()
            cherrypy.engine.block()         

except ImportError:
    pass


class WSGIRefServer(BaseServer):

    def run(self, app, host='127.0.0.1', port=8080):
        from wsgiref.simple_server import make_server
        server=make_server(app=app, host=host, port=port)
        print('Running on %s:%d' %(host, port))
        server.serve_forever()          


_SUPPORTED_SERVER={
    'waitress_server': WaitressServer,
    'cherrypy_server': CherryPyServer,
    'wsgiref_server': WSGIRefServer
}


def run(app, host='127.0.0.1', port=8080):
    try:
        server_class=_SUPPORTED_SERVER[
            config['DEV_SERVER']]
    except KeyError as e:
        raise KeyError('Unsupported server %s' 
                       %config['DEV_SERVER']) from e

    try:
        server=server_class()
        server.run(app, host, port)
    except KeyboardInterrupt:
        pass
    except (SystemExit, MemoryError):
        raise    
import sqlite3

from functools import wraps

from .configuration import config
from .session import get_session_cls
from .exceptions import HTTPError


def session(func):
    try:
        session_store=config['SESSION_STORE']
        session_cls=get_session_cls(session_store)
    except KeyError as e:
        raise ValueError('Unsupported session type %s.' %session_store) from e
    
    try:
        session_dir=config['SESSION_DIR']
    except KeyError:
        config['SESSION_DIR']='sessions'
        session_dir=config['SESSION_DIR']        

    session_manager=session_cls(session_dir)
    
    @wraps
    def wrapper(request, **kwargs):
        try:
            sid=request.cookie['SESSIONID']
        except KeyError:
            sid=None
         
        if sid:  
            session=session_manager.get_session(sid)
        else:
            session=session_manager.create_new_session()
        kwargs['session']=session
        
        try:
            response=func(request=request, **kwargs)
        except HTTPError as e:
            session_manager.save_session(session)
            if not sid:
                e.set_cookie('SESSIONID', session.sid) 
            raise
        except Exception:
            raise
        else:
            session_manager.save_session(session)
            if not sid:
                response.set_cookie('SESSIONID', session.sid)
            return response
                
    return wrapper


def sqlite_db(func):
    try:
        db_file=config['DATABASE_FILE'].rstrip('/')
    except KeyError as e:
        raise KeyError('No database file found.') from e
        
    @wraps
    def wrapper(request, **kwargs):
        db=sqlite3.connect(db_file) 
        kwargs['db']=db
        try:
            response=func(request=request, **kwargs)
            return response
        except Exception:
            raise
        finally:
            db.close()
            
    return wrapper
    
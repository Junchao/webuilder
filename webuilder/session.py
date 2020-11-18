import os
import pickle
import uuid

from .datastructures import SessionDict


class BaseSession:

    '''所有session的父类'''

    def __init__(self, session_dir):
        self.session_dir=session_dir
    
    def _make_sid(self):
        for i in range(100):
            sid=str(uuid.uuid4())
            try:
                _=self._load_session(sid)
            except Exception:
                return sid
    
    def _load_session(self, sid):
        raise NotImplementedError
    
    def save_session(self, session, session_dir=None):
        raise NotImplementedError            
    
    def create_new_session(self):
        sid=self._make_sid()
        return SessionDict(sid)        
    
    def get_session(self, sid):
        try:
            session=self._load_session(sid)
            return session
        except Exception:
            return SessionDict(sid)


class FileSystemSession(BaseSession):

    '''基于文件系统存储的session'''

    def _load_session(self, sid):
        file_path=os.path.join(self.session_dir, str(sid))
        with open(file_path, 'rb') as f:
            session=pickle.load(f)
            return session

    def save_session(self, session):
        file_path=os.path.join(self.session_dir, session.sid)
        with open(file_path, 'wb') as f:
            pickle.dump(session, f)


class CookiesSession(BaseSession):
    pass


_SUPPORTED_SESSION={
    'filesystem': FileSystemSession,
    'cookies': CookiesSession
}


def get_session_cls(session_store):
    return _SUPPORTED_SESSION[session_store]
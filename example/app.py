'''
example代码基于flask官方文档的例子，略作修改。
代码比较凌乱，凑合看......
'''


import sqlite3

from webuilder.configuration import config
from webuilder.app import App
from webuilder.router import Router
from webuilder.response import Response
from webuilder.errors import Redirect, Unauthorized, ErrorHandler
from webuilder.tools import sqlite_db, session
from webuilder.serve import run


config['DATABASE_FILE']='/path/to/db_file'
config['SESSION_DIR']='/path/to/session/dir'


#建表
conn = sqlite3.connect(config['DATABASE_FILE'].rstrip('/'))
conn.execute('''create table entries (
id integer primary key autoincrement,
title text not null,
text text not null
);
''')
conn.close()


#添加自定义错误处理函数
def handle_404(request):
        return Response(body='<h1>Sorry, 你要找的页面不知道哪去了</h1>')

error_handler=ErrorHandler()
error_handler.add_handler(404, handle_404)


#路由
router=Router()

@router.get('/')
@sqlite_db #自动完成连接和关闭数据库（好鸡肋的感觉）
@session
def show_entries(request, db, session):
        if session.get('logged_in', ''):         
                cur=db.execute('select title, text from entries order by id desc')
                entries = [dict(title=row[0], text=row[1]) for row in cur.fetchall()]
                return Response('show_entries.html', entries=entries)  
        raise Redirect('/login')


@router.post('/add')
@session
@sqlite_db
def add_entry(request, session, db):
        if not session.get('logged_in'):
                raise Redirect('/login')
        db.execute('insert into entries (title, text) values (?, ?)',
                     [request.form['title'], request.form['text']])
        db.commit()
        raise Redirect('/')


@router.expose('/login')
@session
def login(request, session):
        error=None
        if request.method == 'POST':
                if request.POST['username'] !='Jack':
                        error = 'Invalid username'
                else:
                        session['logged_in'] = True
                        raise Redirect('/')
        return Response('login.html', error=error)


@router.get('/logout')
@session
def logout(request, session):
        session.pop('logged_in', None)
        raise Redirect('/')

 
app=App('__name__', router) #或者app.add_routers(router)
app.add_error_handler(error_handler)


run(app)


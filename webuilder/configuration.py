import os

from .datastructures import ConfigDict


config=ConfigDict()


#默认配置
config['DEBUG']=True
config['SERVE_STATIC_FILE']=True
config['DEV_SERVER']='wsgiref_server'
config['APP_DIR']=os.path.join(os.getcwd(), '')
config['TEMPLATE_ENGINE']='jinja2'
config['SESSION_STORE']='filesystem'
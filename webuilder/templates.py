import os

import jinja2


class BaseTemplate:

    '''所有模板类的父类'''

    def __init__(self, template_dir, template_file, **template_args):
        self.template_dir=os.path.abspath(template_dir)
        self.template_file=str(template_file)
        self.template_args=template_args
    
    def __call__(self):
        raise NotImplementedError


class Jinja2Template(BaseTemplate):
    
    def __call__(self):
        environment=jinja2.Environment(loader=jinja2.FileSystemLoader(self.template_dir))
        return environment.get_template(self.template_file).render(**self.template_args)


try:
    import mako.template as mako
    
    class MakoTemplate(BaseTemplate):
        
        def __call__(self):
            template_path=os.path.join(self.template_dir, self.template_file)
            template=mako.Template(filename=template_path)
            return template.render(**self.template_args)

except ImportError:
    pass


#如果没有mako会出错吧...啊...懒得改了
_SUPPORTED_TEMPLATE_ENGINE={
    'jinja2': Jinja2Template,
    'mako': MakoTemplate
}


def get_template_cls(template_name):
    return _SUPPORTED_TEMPLATE_ENGINE[template_name]
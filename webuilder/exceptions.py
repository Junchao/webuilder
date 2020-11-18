from. response import BaseResponse


class WebuilderException(Exception):
    pass


class HTTPError(WebuilderException, BaseResponse):

    '''所有HTTP Error的父类'''
        
    _default_status='Overwrite to custom default HTTP Status Code'
    _default_body='Overwrite to custom default body'
    
    def __init__(self, template_file=None, body=None, **template_args):
        WebuilderException.__init__(self)
        BaseResponse.__init__(self, template_file=template_file, body=body, **template_args)
    
    def create_response(self):
        response=BaseResponse.copy(self)
        return response
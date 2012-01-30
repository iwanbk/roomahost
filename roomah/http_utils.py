from BaseHTTPServer import BaseHTTPRequestHandler
from StringIO import StringIO

class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

    def send_error(self, code, message):
        self.error_code = code
        self.error_message = message

def get_http_req_header(request):
    '''Get HTTP Request headers.'''
    http_req = HTTPRequest(request)
    
    try:
        return http_req.headers
    except AttributeError:
        print "FATAL.ERR, headers not found. req = ", request
        return None

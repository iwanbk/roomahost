"""
1. type
2. header len (fixed = 5)
3. 
"""
MIN_HEADER_LEN = 5

TYPE_AUTH_REQ = 1
TYPE_AUTH_RSP = 2
TYPE_DATA_REQ = 3
TYPE_DATA_RSP = 4
'''
Auth REQ packet
header
- type (1)
- user len (1)
- pass len (1)

payload
- user (user len)
- pass (pass len)
'''

'''
AUTH RSP Packet
header
- type

payload
- val (AUTH_RSP_OK, AUTH_RSP_FAILED)
'''
AUTH_RSP_OK = 1
AUTH_RSP_FAILED = 2

'''
DATA REQ packet
header
- type
- ses id

payload
- request
'''

'''
DATA RSP packet
header
- type
- ses id
- EOF (1 jika eof)

payload
- response
'''

class Packet:
    def __init__(self, type = None, payload = None):
        self.type = type
        self.payload = payload
    
    def get_type(self):
        return self.payload[0]
        
    def data_rsp_build(self, payload, ses_id, is_eof = 0):
        self.payload = bytearray(MIN_HEADER_LEN)
        self.payload += payload
        self.payload[0] = TYPE_DATA_RSP
        self.payload[1] = ses_id
        self.payload[2] = is_eof
    
    def data_rsp_get_data(self):
        return self.payload[MIN_HEADER_LEN:]
    
    def data_rsp_get_sesid(self):
        return self.payload[1]
        
    def data_rsp_cek(self):
        return self.payload[0] == TYPE_DATA_RSP
        
    def data_req_build(self, payload, ses_id):
        '''Build DATA REQ packet.'''
        self.payload = bytearray(MIN_HEADER_LEN)
        self.payload += payload
        self.payload[0] = TYPE_DATA_REQ
        self.payload[1] = ses_id
    
    def data_req_get_sesid(self):
        return self.payload[1]
    
    def data_req_cek(self):
        return self.payload[0] == TYPE_DATA_REQ
    
    def data_req_get_data(self):
        return self.payload[MIN_HEADER_LEN:]
    
    def auth_req_cek(self):
        if self.type != TYPE_AUTH_REQ:
            return False
        self.type = TYPE_AUTH_REQ
        return True
    
    def auth_req_build(self, user, password):
        pack_len = 3 + len(user) + len(password)
        self.payload = bytearray(MIN_HEADER_LEN) + bytearray(user) + bytearray(password)
        self.payload[0] = self.type
        self.payload[1] = len(user)
        self.payload[2] = len(password)
    
    def auth_req_get_userpassword(self):
        user_len = self.payload[1]
        user = self.payload[MIN_HEADER_LEN : MIN_HEADER_LEN + user_len]
        
        pass_len = self.payload[2]
        password = self.payload[MIN_HEADER_LEN + user_len : MIN_HEADER_LEN + user_len + pass_len]
        return user, password
    
    def auth_rsp_cek(self):
        '''Cek apakah ini packet auth rsp.'''
        return self.payload[0] == TYPE_AUTH_RSP and len(self.payload) == MIN_HEADER_LEN + 1
    
    def auth_rsp_build(self, val):
        self.type = TYPE_AUTH_RSP
        self.payload = bytearray(MIN_HEADER_LEN + 1)
        self.payload[0] = TYPE_AUTH_RSP
        self.payload[MIN_HEADER_LEN] = val
    
    def auth_rsp_get_val(self):
        return self.payload[MIN_HEADER_LEN]
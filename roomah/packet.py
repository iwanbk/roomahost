import sys

import mysock

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
    
class DataReq:
    '''
    DATA REQ packet
    header
    - (0) type
    - (1) subtype
          undefined = 0
    - (2) ses id
    - (3,4) len
    
    payload
    - request
    '''
    def __init__(self, payload = None):
        self.type = TYPE_DATA_REQ
        self.payload = payload
    
    def build(self, data, ses_id):
        '''Build DATA REQ packet.'''
        self.payload = bytearray(MIN_HEADER_LEN)
        self.payload += data
        self.payload[0] = TYPE_DATA_REQ
        self.payload[2] = ses_id
        
        data_len = len(data)
        self.payload[3] = data_len >> 8
        self.payload[4] = data_len & 0xff
    
    def get_sesid(self):
        return self.payload[2]
    
    def cek_valid(self):
        return self.payload[0] == TYPE_DATA_REQ
    
    def get_data(self):
        return self.payload[MIN_HEADER_LEN:]
        
    def get_len(self):
        return (self.payload[3] << 8) | self.payload[4]

class DataRsp:
    '''
    DATA RSP packet
    header
    - (0) type
    - (1) subtype:
          undefined = 0
          EOF = 1
    - (2) ses id
    - (3,4) len
    payload
    - response
    '''
    DATA_RSP_TYPE_EOF = 1
    def __init__(self, payload = None):
        self.type = TYPE_DATA_RSP
        self.payload = payload
    
    def build(self, data, ses_id, sub_type = 0):
        self.payload = bytearray(MIN_HEADER_LEN)
        self.payload += data
        self.payload[0] = TYPE_DATA_RSP
        self.payload[1] = sub_type
        self.payload[2] = ses_id
        data_len = len(data)
        self.payload[3] = data_len >> 8
        self.payload[4] = data_len & 0xff
    
    def get_data(self):
        return self.payload[MIN_HEADER_LEN:]
    
    def get_sesid(self):
        return self.payload[2]
    
    def set_eof(self):
        self.payload[1] = DataRsp.DATA_RSP_TYPE_EOF
        
    def is_eof(self):
        return self.payload[1] == DataRsp.DATA_RSP_TYPE_EOF
    
    def get_len(self):
        return (self.payload[3] << 8) | self.payload[4]
        
    def cek_valid(self):
        return self.payload[0] == TYPE_DATA_RSP

class Packet:
    def __init__(self, type = None, payload = None):
        self.type = type
        self.payload = payload
    
    def get_type(self):
        return self.payload[0]
        
    
    def auth_req_cek(self):
        if self.payload[0] != TYPE_AUTH_REQ:
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


def print_header(payload):
    print "====== header ======="
    print "[0]", payload[0]
    print "[1]", payload[1]
    print "[2]", payload[2]
    print "[3]", payload[3]
    print "[4]", payload[4]

def get_len_from_header(header):
    '''Get packet len from given packet header.'''
    return (header[3] << 8) | header[4]

def get_all_data_pkt(sock):
    '''get complete Data packet.'''
    #read the header
    ba, err = mysock.recv_safe(sock, MIN_HEADER_LEN)
    
    if ba == None:
        '''something error happened.'''
        print "null BA"
        return None, None
    
    if err != None:
        print "FATAL ERROR.435."
        sys.exit(-1)
    if len(ba) != 5:
        print "len_ba = ", len(ba)
        print "FATAL ERROR.55"
        sys.exit(-1)
    
    pkt_len = get_len_from_header(ba)
    #print "need to recv ", pkt_len, " bytes"
    pkt = ba
    
    if pkt_len > 0:
        buf, err = mysock.recv_safe(sock, pkt_len)
        if buf == None:
            print "NULL ba"
            return None, None
        #print "---> get ", len(buf), " bytes"
        pkt += buf
    
    return pkt, None

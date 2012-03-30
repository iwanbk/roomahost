import sys
import hashlib

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
TYPE_PING_REQ = 5
TYPE_PING_RSP = 6
TYPE_CTRL = 7
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

class AuthReq:
    def __init__(self, payload = None):
        self.payload = payload
    
    def cek_valid(self):
        return self.payload[0] == TYPE_AUTH_REQ
    
    def build(self, user, password):
        pass_hash = hashlib.sha1(password).hexdigest()
        self.payload = bytearray(MIN_HEADER_LEN) + bytearray(user) + bytearray(pass_hash)
        self.payload[0] = TYPE_AUTH_REQ
        self.payload[1] = len(user)
        self.payload[2] = len(pass_hash)
    
    def get_userpassword(self):
        user_len = self.payload[1]
        user = self.payload[MIN_HEADER_LEN : MIN_HEADER_LEN + user_len]
        
        pass_len = self.payload[2]
        password = self.payload[MIN_HEADER_LEN + user_len : MIN_HEADER_LEN + user_len + pass_len]
        return user, password
'''
AUTH RSP Packet
header
- type

payload
- val (AUTH_RSP_OK, AUTH_RSP_FAILED)
'''
AUTH_RSP_OK = 1
AUTH_RSP_FAILED = 2

class AuthRsp:
    def __init__(self, payload = None):
        self.payload = payload
    
    def build(self, val):
        self.payload = bytearray(MIN_HEADER_LEN + 1)
        self.payload[0] = TYPE_AUTH_RSP
        self.payload[MIN_HEADER_LEN] = val
        
    def cek(self):
        '''Cek apakah ini packet auth rsp.'''
        return self.payload[0] == TYPE_AUTH_RSP and len(self.payload) == MIN_HEADER_LEN + 1
    
    def get_val(self):
        return self.payload[MIN_HEADER_LEN]
    
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

class Ping:
    '''
    Ping Packet:
    header:
    - (0) type (REQ/RSP)
    - (1) 0
    - (2) 0
    - (3,4) len (0)
    
    payload/data
    No data
    '''
    def __init__(self):
        self.payload = bytearray(MIN_HEADER_LEN)
        #set len = 0
        self.payload[3] = 0
        self.payload[4] = 0
    
    def get_len(self):
        get_len_from_header(self.payload)

class PingReq(Ping):
    def __init__(self):
        Ping.__init__(self)
        self.payload[0] = TYPE_PING_REQ
    
    def cek_valid(self):
        return self.payload[0] == TYPE_PING_REQ

class PingRsp(Ping):
    def __init__(self):
        Ping.__init__(self)
        self.payload[0] = TYPE_PING_RSP
    
    def cek_valid(self):
        return self.payload[0] == TYPE_PING_RSP

class CtrlPkt():
    '''
    Header
    (0) type
    (1) subtype
    
    Data
    None
    '''
    T_PEER_DEAD = 1
    def __init__(self, payload = None):
        self.payload = payload
    
    def get_type(self):
        return self.payload[1]
        
    def cek_valid(self):
        if self.payload != None:
            return (self.payload[0] == TYPE_CTRL)
            
        return True
    ####### peer dead ##########
    def build_peer_dead(self, ses_id):
        payload = bytearray(5)
        payload[0] = TYPE_CTRL
        payload[1] = self.T_PEER_DEAD
        payload[2] = ses_id
        
        self.payload = payload
    
    def peer_dead_ses_id(self):
        return self.payload[2]
        
class Packet:
    def __init__(self, type = None, payload = None):
        self.type = type
        self.payload = payload
    
    def get_type(self):
        return self.payload[0]

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
    
    if ba == None or err != None:
        '''something error happened.'''
        print "null BA"
        return None, None

    if len(ba) != MIN_HEADER_LEN:
        print "FATAL ERROR.len(ba) = ", len(ba)
        return None, None
    
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

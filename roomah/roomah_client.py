"""
Client untuk roomahost
"""
import sys
import socket
import select
import time
import datetime

import packet
import mysock

SERV_BUF_LEN = 1024
HOST_BUF_LEN = SERV_BUF_LEN - packet.MIN_HEADER_LEN

host_conns_dict = {}
rsp_list = []

class HostConn:
    '''Connection to host.'''
    def __init__(self, ses_id):
        self.sock = None
        self.ses_id = ses_id
        self.ended = False
        self.rsp_list = []
    
    def reset(self):
        '''reset semua value (set None).'''
        try:
            self.sock.close()
        except Exception:
            pass
        
        self.sock = None
        self.rsp_list = []

class HostRsp:
    '''Response from host.'''
    def __init__(self, h_conn, payload):
        self.conn = h_conn
        self.payload = payload
        
        
def clean_host_conn():
    '''Clean HostConn untuk client ini.
    
    HostConn yang didelete adalah yang telah di mark ended
    dan rsp_list nya sudah kosong
    '''
    to_del = []
    for h_conn in host_conns_dict.itervalues():
        if h_conn.ended == True and len(h_conn.rsp_list) == 0:
            to_del.append(h_conn)
    
    for h_conn in to_del:
        del_host_conn(h_conn.ses_id, h_conn)

def get_host_conn_by_sock(sock):
    '''Get HostConn object dari sebuah socket ke host.'''
    if sock == None:
        return None
    
    for h_conn in host_conns_dict.itervalues():
        if h_conn.sock == sock:
            return h_conn
    
    return None

def del_host_conn(ses_id, h_conn = None):
    '''Del HostConn by ses_id.'''
    conn = h_conn
    if conn == None:
        try:
            conn = host_conns_dict[ses_id]
        except KeyError:
            print "key_error"
            #sys.exit(-1)
            return
    print "del host conn"    
    conn.reset()
    del host_conns_dict[ses_id]

def forward_incoming_req_pkt(ba, ba_len, host_host, host_port):
    '''Forward incoming req packet to host.'''
    req = packet.DataReq(ba)
    if req.cek_valid() == False:
        print "bukan DATA REQ"
        print "FATAL ERROR"
        #sys.exit(-1)
        return
    
    ses_id = req.get_sesid()
    req_data = req.get_data()
    #print req_data
    
    h_conn = HostConn(ses_id)
    host_conns_dict[ses_id] = h_conn
    
    #forward ke host
    h_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    h_conn.sock = h_sock
    
    ret, err = mysock.connect(h_sock, (host_host, host_port))
    written, err = mysock.send_all(h_sock, req_data)
    if err != None:
        print "error forward"
        del host_conns_dict[ses_id]
        sys.exit(-1)
    
    if written != len(req_data):
        print "PARTIAL FORWARD to host"
        print "FATAL UNHANDLED COND"
        sys.exit(-1)
        
def accept_host_rsp(h_sock):
    '''accept host response.
    enqueue it to rsp_list.
    '''
    #get HostConn object
    h_conn = get_host_conn_by_sock(h_sock)
    if h_conn == None:
        print "can't get h_conn by sock"
        print "FATAL UNHANDLED CONDITION"
        sys.exit(-1)
        
    #receive the response
    ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
    if err != None:
        print "FATAL ERROR. error recv resp from host"
        sys.exit(-1)
    
    if len(ba) == 0:
        #print "closing the socket.."
        h_sock.close()
        h_conn.ended = True
    
    #experimental
    h_conn.rsp_list.append(ba)

        
def _send_rsp_pkt_to_server(rsp_pkt, server_sock):
    '''Send response packet to server.'''
    print "#"
    written, err = mysock.send_all(server_sock, rsp_pkt.payload)
    if err != None:
        print "error sending packet to server"
        sys.exit(-1)
    
    if written != len(rsp_pkt.payload):
        print "partial write to server"
        sys.exit(-1)

def forward_host_rsp(server_sock):
    '''Forward Host response ke server.'''
    for h_conn in host_conns_dict.itervalues():
        if len(h_conn.rsp_list) > 0:
            ba = h_conn.rsp_list.pop(0)
            rsp_pkt = packet.DataRsp()
            rsp_pkt.build(ba, h_conn.ses_id)
    
            if len(ba) == 0:
                rsp_pkt.set_eof()
            
            _send_rsp_pkt_to_server(rsp_pkt, server_sock)
            
            if rsp_pkt.is_eof():
                h_conn.ended = True

        
class Client:
    '''Client class.'''
    PING_REQ_PERIOD = 120
    PING_RSP_WAIT_TIME = PING_REQ_PERIOD / 2
    
    def __init__(self, server_sock):
        self.last_ping = time.time()
        self.server_sock = server_sock
        self.to_server_pkt = []
        self.wait_ping_rsp = False
    
    def cek_ping_req(self):
        '''Cek waktu terakhir melakukan ping
        dan enqueue ping packet kalo sudah waktunya melakukan ping lagi.'''
        if time.time() - self.last_ping >= Client.PING_REQ_PERIOD:
            preq = packet.PingReq()
            self.to_server_pkt.append(preq)
    
    def cek_ping_rsp(self):
        '''Cek ping response.
        
        Return false jika ping rsp belum datang dan melebihi timeout.
        '''
        if not self.wait_ping_rsp:
            return True
        
        if time.time() - self.last_ping > Client.PING_RSP_WAIT_TIME:
            return False
        
        return True
    
    def handle_ping_rsp(self, ba):
        '''Handle PING-RSP.'''
        self.wait_ping_rsp = False
        self.last_ping = time.time()
    
    def handle_ctrl_pkt(self, ba):
        pkt = packet.CtrlPkt(ba)
        if pkt.cek_valid() == False:
            return False
        
        type = pkt.get_type()
        if type == pkt.T_PEER_DEAD:
            ses_id = pkt.peer_dead_ses_id()
            self.handle_peer_dead(ses_id)
        else:
            print "Unknown control packet"
            sys.exit(-1)
        
    def handle_peer_dead(self, ses_id):
        print "handle_peer_dead. 675999987"
        del_host_conn(ses_id)
        
    def send_to_server_pkt(self):
        '''Send packet di queue ke server.'''
        if len(self.to_server_pkt) == 0:
            return True
        
        pkt = self.to_server_pkt.pop(0)
        
        written, err = mysock.send_all(self.server_sock, pkt.payload)
        if (err != None) or (written != len(pkt.payload)):
            print "err sending pkt to server"
            return False
        
        if pkt.payload[0] == packet.TYPE_PING_REQ:
            self.last_ping = time.time()
            self.wait_ping_rsp = True
            print "[PING-REQ]", datetime.datetime.now()
        
        return True

def do_auth(user, password, server_sock):
    auth_req = packet.AuthReq()
    auth_req.build(user, password)
    
    written, err = mysock.send(server_sock, auth_req.payload)
    if err != None or written < len(auth_req.payload):
        print "can't send auth req to server.err = ", err
        return False
    
    ba, err = mysock.recv(server_sock, 1024)
    if err != None:
        print "failed to get auth reply"
        return False
    
    rsp = packet.AuthRsp(ba)
    if rsp.get_val() != packet.AUTH_RSP_OK:
        print "AUTH_RSP_FAILED"
        return False
    return True
    
def client_loop(server, port, user, passwd, host_host, host_port):
    #connect to server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mysock.setkeepalives(server_sock)
    ret, err = mysock.connect(server_sock, (server, port))
    
    if err != None:
        print "can't connect to server"
        sys.exit(-1)
    
    if do_auth(user, passwd, server_sock) == False:
        print "Auth failed"
        sys.exit(1)
        
    print "AUTH OK"
    #server_sock.setblocking(0)
    
    client = Client(server_sock)
    
    #start looping
    while True:
        #cek last_ping
        client.cek_ping_req()
        
        #select untuk server sock
        to_read, to_write, _ = select.select([server_sock],
            [server_sock], [], 0.1)
        
        if len(to_read) > 0:
            #read sock
            ba, err = packet.get_all_data_pkt(server_sock)
            if ba is None or err != None:
                print "Error : Connection to server"
                break
            
            if ba[0] == packet.TYPE_DATA_REQ:
                forward_incoming_req_pkt(ba, len(ba), host_host, host_port)
                
            elif ba[0] == packet.TYPE_PING_RSP:
                print "PING-RSP ", datetime.datetime.now()
                client.handle_ping_rsp(ba)
            
            elif ba[0] == packet.TYPE_CTRL:
                print "CTRL Packet. subtype = ", ba[1]
                client.handle_ctrl_pkt(ba)
            else:
                print "Unknown packet.type = ", ba[0]
                sys.exit(-1)
        
        if len(to_write) > 0:
            forward_host_rsp(server_sock)
            if client.send_to_server_pkt() == False:
                break
           
        clean_host_conn()
        
        #select() untuk host sock
        rlist = []
        for h_conn in host_conns_dict.itervalues():
            if h_conn.sock != None and h_conn.ended == False:
                rlist.append(h_conn.sock)
                
        h_read, _, _ = select.select(rlist, [], [], 0.1)
        
        if len(h_read) > 0:
            for s in h_read:
                accept_host_rsp(s)
        
        #cek ping rsp
        if client.cek_ping_rsp() == False:
            print "PING-RSP timeout"
            break
                
    print "Client exited..."
    
        
if __name__ == '__main__':
    server = sys.argv[1]
    port = 3939
    user = sys.argv[2]
    passwd = sys.argv[3]
    host_host = sys.argv[4]
    host_port = int(sys.argv[5])
    
    client_loop(server, port, user, passwd, host_host, host_port)
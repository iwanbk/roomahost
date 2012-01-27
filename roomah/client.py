import sys
import socket
import select

import packet
import mysock

SERV_BUF_LEN = 1024
HOST_BUF_LEN = SERV_BUF_LEN - packet.MIN_HEADER_LEN

host_conns_dict = {}
rsp_list = []

class HostConn:
    def __init__(self, ses_id):
        self.sock = None
        self.ses_id = ses_id
        self.ended = False

class HostRsp:
    def __init__(self, h_conn, payload):
        self.conn = h_conn
        self.payload = payload
        
def get_host_conn_by_sock(sock):
    if sock == None:
        return None
    
    for k,v in host_conns_dict.iteritems():
        h_conn = v
        if h_conn.sock == sock:
            return h_conn
    
    return None
def del_host_conn(ses_id, h_conn):
    print "del host con.ses_id=", ses_id
    #h_conn.sock.close()
    h_conn.sock = None
    del host_conns_dict[ses_id]

def get_req_pkt(sock):
    '''get complete Data RSP packet.'''
    #read the header
    ba_len, ba, err = mysock.recv(sock, 5)
    if err != None:
        print "FATAL ERROR.435."
        sys.exit(-1)
    if ba_len != 5:
        print "FATAL ERROR.55"
        sys.exit(-1)
    
    req_len = packet.get_len_from_header(ba)
    print "need to recv ", req_len, " bytes"
    pkt = ba
    
    if req_len > 0:
        buf, err = mysock.recv_safe(sock, req_len)
        print "---> get ", len(buf), " bytes"
        pkt += buf
    
    return pkt

def forward_incoming_req_pkt(ba, ba_len):
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
    written, err = mysock.send(h_sock, req_data)
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
    h_conn = get_host_conn_by_sock(h_sock)
    if h_conn == None:
        print "can't get h_conn by sock"
        print "FATAL UNHANDLED CONDITION"
        sys.exi(-1)
        
    ba_len, ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
    if err != None:
        print "FATAL ERROR. error recv resp from host"
        sys.exit(-1)
    
    print "recved host responses.ses_id = ", h_conn.ses_id, ".len = ", ba_len
    if ba_len == 0:
        print "closing the socket.."
        h_sock.close()
        h_conn.ended = True
    
    h_rsp = HostRsp(h_conn, ba)
    rsp_list.append(h_rsp)

def forward_host_rsp(server_sock):
    '''Forward host response to server.'''
    if len(rsp_list) == 0:
        return

    h_rsp = rsp_list.pop(0)
    h_conn = h_rsp.conn
    
    rsp_pkt = packet.DataRsp()
    
    rsp_pkt.build(h_rsp.payload, h_rsp.conn.ses_id)
    
    if len(h_rsp.payload) == 0:
        print "EOF for ses_id = ", h_rsp.conn.ses_id
        rsp_pkt.set_eof()
        
    written, err = mysock.send(server_sock, rsp_pkt.payload)
    if err != None:
        print "error sending packet to server"
        sys.exit(-1)
    
    #print "[", h_conn.ses_id, "]written = ", written, ".len(payload) = ", len(rsp_pkt.payload)
        
    if written != len(rsp_pkt.payload):
        print "partial write to server"
        sys.exit(-1)
    
    if len(h_rsp.payload) == 0:
        del_host_conn(h_conn.ses_id, h_conn)
    
    print "forward exited...written = ", written
        
if __name__ == '__main__':
    server = sys.argv[1]
    port = int(sys.argv[2])
    user = sys.argv[3]
    passwd = sys.argv[4]
    host_host = sys.argv[5]
    host_port = int(sys.argv[6])
    
    sock_dict = {}
    
    #connect to server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mysock.setkeepalives(server_sock)
    ret, err = mysock.connect(server_sock, (server, port))
    
    if err != None:
        print "can't connect to server"
        sys.exit(-1)
    
    #send auth req
    pkt = packet.Packet(packet.TYPE_AUTH_REQ)
    pkt.auth_req_build(user, passwd)
    written, err = mysock.send(server_sock, pkt.payload)
    if err != None:
        print "can't send auth req to client"
        print "err = ", err
    
    print "pkt len = ", len(pkt.payload)
    print "sent len = ", written
    
    recvd, ba, err = mysock.recv(server_sock, 1024)
    if err != None:
        print "failed to get auth reply"
        sys.exit(-1)
    
    rsp = packet.Packet()
    rsp.payload = ba
    if rsp.auth_rsp_cek() == False:
        print "bukan auth rsp"
        sys.exit(-1)
    
    if rsp.auth_rsp_get_val() != packet.AUTH_RSP_OK:
        print "auth failed"
        sys.exit(-1)
    
    print "AUTH OK"
    #server_sock.setblocking(0)
    
    #start looping
    while True:
        #print "main loop"
        #select untuk server sock
        to_read, to_write, to_exc = select.select([server_sock], [server_sock], [], 0.1)
        
        if len(to_read) > 0:
            #read sock
            ba = get_req_pkt(server_sock)
            forward_incoming_req_pkt(ba, len(ba))
        
        if len(to_write) > 0:
            forward_host_rsp(server_sock)
        
        #select untuk host sock
        rlist = []
        for k,v in host_conns_dict.iteritems():
            h_conn = v
            if h_conn.sock != None and h_conn.ended == False:
                rlist.append(h_conn.sock)
                
        h_read, h_write, h_exc = select.select(rlist, [], [], 0.1)
        
        if len(h_read) > 0:
            for s in h_read:
                accept_host_rsp(s)
                
    print "###########"
    
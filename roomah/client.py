import sys
import socket
import select

import packet
import mysock

SERV_BUF_LEN = 1024
HOST_BUF_LEN = SERV_BUF_LEN - packet.MIN_HEADER_LEN

host_conns_dict = {}
class HostConn:
    def __init__(self, ses_id):
        self.sock = None
        self.ses_id = ses_id

def get_host_conn_by_sock(sock):
    if sock == None:
        return None
    
    for k,v in host_conns_dict.iteritems():
        h_conn = v
        if h_conn.sock == sock:
            return h_conn
    
    return None
def forward_incoming_req_pkt(ba, ba_len):
    req = packet.DataReq(ba)
    if req.cek_valid() == False:
        print "bukan DATA REQ"
        print "FATAL ERROR"
        sys.exit(-1)
    
    ses_id = req.get_sesid()
    req_data = req.get_data()
    print req_data
    
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
        
def forward_incoming_host_rsp(h_sock, server_sock):
    h_conn = get_host_conn_by_sock(h_sock)
    if h_conn == None:
        print "can't get h_conn by sock"
        print "FATAL UNHANDLED CONDITION"
        sys.exi(-1)
        
    ba_len, ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
    count = 0
    while err == None:
        rsp_pkt = packet.DataRsp()
        
        print "build rsp pkt.ses_id =", h_conn.ses_id
        
        rsp_pkt.build(ba, h_conn.ses_id)
        if ba_len == 0:
            rsp_pkt.set_eof()
            
        written, err = mysock.send(server_sock, rsp_pkt.payload)
        if err != None:
            print "error sending packet to server"
            sys.exit(-1)
        
        if written != len(rsp_pkt.payload):
            print "partial write to server"
            sys.exit(-1)
        
        print "written = ", written
        
        if ba_len == 0:
            print "EOF.exit"
            break
        
        count += 1
        if count == 5:
            break
        ba_len, ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
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
    
    #start looping
    while True:
        #select untuk server sock
        to_read, to_write, to_exc = select.select([server_sock], [], [], 0.1)
        if len(to_read) > 0:
            #read sock
            ba_len, ba, err = mysock.recv(server_sock, 1024)
            if err != None:
                print "error receiving data packet"
                sys.exit(-1)
            if ba_len == 0:
                print "server closed the connection"
                print "FATAL UNHANDLED Condition"
                sys.exit(-1)
                
            forward_incoming_req_pkt(ba, ba_len)
        
        if len(to_write) > 0:
            pass
        
        #select untuk host sock
        rlist = []
        for k,v in host_conns_dict.iteritems():
            h_conn = v
            rlist.append(h_conn.sock)
        h_read, h_write, h_exc = select.select(rlist, [], [], 0.1)
        if len(h_read) > 0:
            for s in h_read:
                forward_incoming_host_rsp(s, server_sock)
                
    print "###########"
    
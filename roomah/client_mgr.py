import sys

import packet
import mysock

BUF_LEN = 1024

class ReqPkt:
    def __init__(self, peer, payload):
        self.peer = peer
        self.payload = payload
        
class Peer:
    def __init__(self, sock, ses_id):
        self.sock = sock
        self.ses_id = ses_id
class Client:
    def __init__(self, user, sock):
        self.ses_id = 1
        self.user = user
        self.sock = sock
        self.req_pkt = []
        self.rsp_pkt = []
        self.peers = {}
    
    def add_peer(self, sock):
        ses_id = self._gen_ses_id()
        peer = Peer(sock, ses_id)
        self.peers[ses_id] = peer
        
        return peer
    
    def _gen_ses_id(self):
        ses_id = self.ses_id
        self.ses_id += 1
        return ses_id
    
    def add_req_pkt(self, req_pkt):
        self.req_pkt.append(req_pkt)
    
    def req_pkt_fwd(self, n):
        req = self.req_pkt.pop(0)
        req_pkt = packet.Packet()
        req_pkt.data_req_build(req.payload, req.peer.ses_id)
        written, err = mysock.send(self.sock, req_pkt.payload)
        if err != None:
            print "can't fwd packet to client"
            print "FATAL ERROR"
            sys.exit(-1)
        
        if written != len(req_pkt.payload):
            print "partial forward to client"
            print "FATAL ERROR"
            sys.exit(-1)
    
    def recv_rsp_pkt(self):
        ba_len, ba, err = mysock.recv(self.sock, BUF_LEN)
        if err != None:
            print "client.recv_rsp_pkt err sock"
            print "FATAL ERROR"
            sys.exit(-1)
        
        rsp = packet.Packet(packet.TYPE_DATA_RSP, ba)
        ses_id = rsp.data_rsp_get_sesid()
        print "recv_rsp_pkt.ba_len = ", ba_len, ".ses_id = ", ses_id, ".payload len = ", len(rsp.payload)
        peer = self.peers[ses_id]
        #forward
        self.rsp_pkt_fwd(peer, rsp)
        
    def rsp_pkt_fwd(self, peer, rsp_pkt):
        data = rsp_pkt.data_rsp_get_data()
        print "data_len = ", len(data)
        written, err = mysock.send(peer.sock, data)
        if err != None:
            print "client.rsp_pkt_fwd err"
            print "FATAL ERROR"
            sys.exit(-1)
            
        if written != len(rsp_pkt.data_rsp_get_data()):
            print "client.rsp_pkt_fwd partial "
            print "FATAL ERROR"
            sys.exit(-1)
        
class ClientMgr:
    def __init__(self):
        self.clients = {}
    
    def add_client(self, user, sock):
        client = Client(user, sock)
        self.clients[str(user)] = client
        return client
    
    def get_client(self, user_str):
        return self.clients[user_str]
    
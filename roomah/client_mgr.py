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
        self.ended = False
        
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
    
    def del_peer(self, ses_id):
        del self.peers[ses_id]
    
    def marked_peer_ended(self, ses_id):
        peer = self.peers[ses_id]
        peer.ended = True
    
    def get_peer_by_sock(self, sock):
        if sock == None:
            print "cant' search None sock"
            print "FATAL ERROR"
            sys.exit(-1)
        
        for k,v in self.peers.iteritems():
            peer = v
            if peer.sock == sock:
                return peer
        return None
    
    def _inc_ses_id(self, ses_id):
        if ses_id == 255:
            return 1
        else:
            return ses_id + 1
        
    def _gen_ses_id(self):
        start_id = self.ses_id
        
        ses_id = start_id
        
        while ses_id in self.peers.keys():
            ses_id = self._inc_ses_id(ses_id)
            if ses_id == start_id:
                return 0
            
        self.ses_id = self._inc_ses_id(ses_id)
        
        return ses_id
    
    def add_req_pkt(self, req_pkt):
        self.req_pkt.append(req_pkt)
    
    def req_pkt_fwd(self, n):
        req = self.req_pkt.pop(0)
        
        req_pkt = packet.DataReq()
        req_pkt.build(req.payload, req.peer.ses_id)
        
        written, err = mysock.send(self.sock, req_pkt.payload)
        if err != None:
            print "can't fwd packet to client"
            print "FATAL ERROR"
            sys.exit(-1)
        
        if written != len(req_pkt.payload):
            print "partial forward to client"
            print "FATAL ERROR"
            sys.exit(-1)
        
        #print "forwarding pkt to client.len = ", len(req_pkt.payload), ".written = ", written
    
    def procsess_rsp_pkt(self, ba, ba_len):
        #preliminary cek
        if ba_len < packet.MIN_HEADER_LEN:
            print "packet too small. discard"
            return
        
        rsp = packet.DataRsp(ba)
        ses_id = rsp.get_sesid()
        
        if rsp.cek_valid() == False:
            print "bukan DATA RSP"
            packet.print_header(rsp.payload)
            #sys.exit(-1)
            return
            
        #print "process_rsp_pkt.ses_id = ", ses_id, ".ba_len = ", ba_len
        
        peer = self.peers[ses_id]
        
        #forward
        self.rsp_pkt_fwd(peer, rsp)
        
        if rsp.is_eof() == True:
            print "EOF.deleting peer for ses_id = ", ses_id
            self.del_peer(ses_id)
        
    def rsp_pkt_fwd(self, peer, rsp_pkt):
        '''Forward RSP pkt to peer.'''
        data = rsp_pkt.get_data()
        
        written, err = mysock.send(peer.sock, data)
        if err != None:
            print "client.rsp_pkt_fwd err"
            print "FATAL ERROR"
            sys.exit(-1)
            
        if written != len(data):
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
    
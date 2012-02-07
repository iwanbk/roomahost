import sys

import gevent

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
        self.rsp_list = []
        self.in_mq = gevent.queue.Queue(10)
    
    def close(self):
        if self.ended == False or len(self.rsp_list) > 0:
            return False
        self.sock.close()
        return True
        
    def enq_rsp(self, payload):
        self.rsp_list.insert(0, payload)
    
    def forward_rsp_pkt(self):
        '''Forward RSP pkt to peer.'''
        if len(self.rsp_list) == 0:
            return 0
        
        rsp = self.rsp_list.pop(0)
        data = rsp.get_data()
        
        written, err = mysock.send(self.sock, data)
        if err != None:
            print "client.rsp_pkt_fwd err"
        
        if written < 0:
            print "FATAL ERROR.written < 0"
            sys.exit(-1)
            
        if written != len(data):
            print "peer.forward_rsp_pkt partial "
            self.enq_rsp(data[written])
        
        if rsp.is_eof() == True:
            self.ended = True
            
        return written
        
class Client:
    MT_PEER_ADD_REQ = 1
    MT_PEER_ADD_RSP = 2
    MT_PEER_DEL_REQ = 3
    MT_PEER_DEL_RSP = 4
    MT_REQPKT_ADD_REQ = 5
    MT_REQPKT_ADD_RSP = 6

    def __init__(self, user, sock):
        self.ses_id = 1
        self.user = user
        self.sock = sock
        self.req_pkt = []
        self.wait_ping_rsp = False
        self.peers = {}
        self.in_mq = gevent.queue.Queue(10)
    
    def _add_peer(self, sock):
        ses_id = self._gen_ses_id()
        if ses_id == None:
            return None
        peer = Peer(sock, ses_id)
        self.peers[ses_id] = peer
        
        return peer
    
    def _del_peer(self, ses_id):
        del self.peers[ses_id]
    
    def process_msg(self):
        try:
            msg = self.in_mq.get_nowait()
        except gevent.queue.Empty:
            return
        
        if msg['mt'] == self.MT_PEER_ADD_REQ:
            sock = msg['sock']
            q = msg['q']
            peer = self._add_peer(sock)
            rsp = {}
            rsp['mt'] = self.MT_PEER_ADD_RSP
            rsp['peer'] = peer
            try:
                q.put(rsp)
            except gevent.queue.Full:
                pass
        elif msg['mt'] == self.MT_PEER_DEL_REQ:
            ses_id = msg['ses_id']
            self._del_peer(ses_id)
            
        elif msg['mt'] == self.MT_REQPKT_ADD_REQ:
            req_pkt = msg['req_pkt']
            self._add_req_pkt(req_pkt)
        else:
            print "Client.process_msg.unknown_message"
            
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
    
    def _add_req_pkt(self, req_pkt):
        '''add req pkt from to client's req_pkt list'''
        self.req_pkt.append(req_pkt)
    
    def req_pkt_fwd(self, n):
        '''Forward request packet to client.'''
        if len(self.req_pkt) == 0:
            return
        
        req = self.req_pkt.pop(0)
        
        req_pkt = packet.DataReq()
        req_pkt.build(req.payload, req.peer.ses_id)
        
        written, err = mysock.send_all(self.sock, req_pkt.payload)
        
        if written != len(req_pkt.payload) or err != None:
            print "failed to send req pkt to client"
            return False
    
    def ping_rsp_send(self):
        '''Send PING-RSP to client.'''
        if self.wait_ping_rsp == False:
            return True
        
        p_rsp = packet.PingRsp()
        
        written, err = mysock.send_all(self.sock, p_rsp.payload)
        
        if err != None or (len(p_rsp.payload) != written):
            print "error sending PING-RSP to ", client.user
            return False
        
        self.wait_ping_rsp = False
        
    def procsess_rsp_pkt(self, ba, ba_len):
        #preliminary cek
        if ba_len < packet.MIN_HEADER_LEN:
            print "FATAL:packet too small. discard"
            sys.exit(-1)
        
        rsp = packet.DataRsp(ba)
        ses_id = rsp.get_sesid()
        
        if rsp.cek_valid() == False:
            print "FATAL : bukan DATA RSP"
            packet.print_header(rsp.payload)
            sys.exit(-1)
            
        #print "process_rsp_pkt.ses_id = ", ses_id, ".ba_len = ", ba_len
        
        if ses_id not in self.peers:
            '''ses_id sudah tidak ada.discard packet.'''
            return
        
        peer = self.peers[ses_id]
        
        #forward
        peer.rsp_list.append(rsp)

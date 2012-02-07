import sys

import gevent

import packet
import mysock

class Peer:
    MT_ADD_RSP_PKT = 1
    
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
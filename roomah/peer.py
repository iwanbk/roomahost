"""
Peer module
"""
import select

import gevent
from gevent.server import StreamServer

import mysock
import client
import http_utils
from client_mgr import ClientMgr

BASE_DOMAIN = ""
CM = None
BUF_LEN = 1024

class Peer:
    """
    Class yang merepresentasikan satu Peer
    Peer adalah sebuah koneksi dari pengakses (misal : browser)
    """
    RSP_FORWARD_NUM = 5
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
    
    def _do_forward_rsp_pkt(self):
        '''Forward RSP pkt to peer.'''
        if len(self.rsp_list) == 0:
            return 0
        
        rsp = self.rsp_list.pop(0)
        data = rsp.get_data()
        
        written, err = mysock.send(self.sock, data)
        if err != None:
            print "client.rsp_pkt_fwd err"
            return -1
        
        if written < 0:
            print "FATAL ERROR.written < 0"
            return -1
            
        if written != len(data):
            print "peer.forward_rsp_pkt partial "
            self.enq_rsp(data[written])
        
        if rsp.is_eof() == True:
            self.ended = True
            
        return written
    
    def forward_rsp_pkt(self):
        for _ in xrange(0, self.RSP_FORWARD_NUM):
            written = self._do_forward_rsp_pkt()
            if written <= 0:
                break

def user_not_found_str(user):
    html = "HTTP/1.1\n\
Server: nginx/1.1.11\n\
Content-Type: text/html\n\
Content-Length: 173\n\
Connection: close\n\
\r\n\
"
    html += user + " ga ketemu"
    return html

def get_subdom(req, base_domain=BASE_DOMAIN):
    header = http_utils.get_http_req_header(req)
        
    host = header['Host']
    idx = host.find("." + base_domain)
    if idx < 0:
        return None
    else:
        return host[:idx]

def get_client_mq(CM, subdom):
    q = gevent.queue.Queue(1)
    msg = {}
    msg['mt'] = ClientMgr.MT_CLIENT_GET_REQ
    msg['user_str'] = subdom
    msg['q'] = q
    
    CM.in_mq.put(msg)
    
    rsp = q.get()
    client_mq = rsp['client_mq']
    return client_mq
    
def _add_peer_to_client(client_mq, sock):
    peer = Peer(sock, None)
    
    q = gevent.queue.Queue(1)
    msg = {}
    msg['mt'] = client.Client.MT_PEER_ADD_REQ
    msg['in_mq'] = peer.in_mq
    msg['q'] = q
    client_mq.put(msg)
    
    rsp = q.get()
    
    ses_id = rsp['ses_id']
    
    peer.ses_id = ses_id
    
    return peer

def _peer_add_reqpkt_to_client(client_mq, req_pkt):
    msg = {}
    msg['mt'] = client.Client.MT_REQPKT_ADD_REQ
    msg['req_pkt'] = req_pkt
    client_mq.put(msg)

def _peer_del_from_client(client_mq, peer):
    msg = {}
    msg['mt'] = client.Client.MT_PEER_DEL_REQ
    msg['ses_id'] = peer.ses_id
    client_mq.put(msg)
    
def handle_peer(sock, addr):
    #print "##### peer baru ############"
    #print "sock = ", sock
    #print "addr = ", addr
    
    ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "recv error"
        return
    
    if len(ba) == 0:
        print "new-closed socket?"
        return
    
    subdom = get_subdom(ba, BASE_DOMAIN)
    
    if subdom is None:
        print "subdom not found"
        sock.close()
        return
    
    client_mq = get_client_mq(CM, subdom)
    
    if client_mq == None:
        print "send user error"
        str_err = user_not_found_str(subdom)
        mysock.send_all(sock, str_err)
        return
    
    peer = _add_peer_to_client(client_mq, sock)
    
    if peer == None:
        print "can't add peer. MAX_CONN REACHED?"
        return
    
    #print "peer baru.ses_id =", peer.ses_id
    req_pkt = client.ReqPkt(peer, ba)
    _peer_add_reqpkt_to_client(client_mq, req_pkt)
    
    while True:
        wlist = []
        
        try:
            for _ in xrange(0, Peer.RSP_FORWARD_NUM):
                msg = peer.in_mq.get_nowait()
                rsp = msg['pkt']
                peer.rsp_list.append(rsp)
        except gevent.queue.Empty:
            pass
        
        if len(peer.rsp_list) > 0:
            wlist.append(sock)
            
        rsocks, wsocks, _ = select.select([sock], wlist , [], 0.1)
        
        if len(rsocks) > 0:
            #TODO : buat fungsi sendiri . seperti peer.forward_rsp_pkt, di-loop
            ba, err = mysock.recv(sock, BUF_LEN)
            if len(ba) == 0:
                #peer close the socket
                peer.close()
                _peer_del_from_client(client_mq, peer)
                break    
            elif len(ba) > 0:
                req_pkt = client.ReqPkt(peer, ba)
                _peer_add_reqpkt_to_client(client_mq, req_pkt)
        
        if len(wsocks) > 0:
            peer.forward_rsp_pkt()
        
        if peer.ended == True and len(peer.rsp_list) == 0:
            peer.close()
            _peer_del_from_client(client_mq, peer)
            break
        
        gevent.sleep(0)
        
def peer_server(port):
    server = StreamServer(('0.0.0.0', port), handle_peer)
    print 'Starting peer server on port ', port
    print 'BASE_DOMAIN = ', BASE_DOMAIN
    server.serve_forever()

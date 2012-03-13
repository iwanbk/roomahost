"""
Peer module
"""
import select

import gevent
from gevent.server import StreamServer
import jsonrpclib

import mysock
import client
import http_utils
import rhconf
from client_mgr import ClientMgr

BASE_DOMAIN = ""
CM = None
BUF_LEN = 1024

def report_usage(username, trf_req, trf_rsp):
    '''Report data transfer usage.'''
    stat_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = stat_server.usage_add(username, trf_req, trf_rsp)
    return res

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
        
        #Transferred RSP packet, in bytes
        self.trf_rsp = 0
        
        #transferred Req packets, in bytes
        self.trf_req = 0
    
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
            self.trf_rsp += written

def user_not_found_str(user):
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Content-Length: 173\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big><b>" + user + " </b> sedang tidak online</big></center>"
    html += "</body></html>"
    return html

def _get_client_own_domain(host):
    '''Get client name yang memiliki own-domain.'''
    import jsonrpclib
    server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = server.rh_domain_client(host)
    return res

def get_client_name(req, base_domain = BASE_DOMAIN):
    '''Get client name dari HTTP Request header.'''
    header = http_utils.get_http_req_header(req)
    
    if header == None:
        return None
    try:
        host = header['Host']
        idx = host.find("." + base_domain)
        if idx < 0:
            return _get_client_own_domain(host)
        else:
            return host[:idx]
    except AttributeError:
        return None

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
    
    #get request
    ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "recv error"
        return
    
    if len(ba) == 0:
        print "new-closed socket?"
        return
    
    #get client name
    client_name = get_client_name(ba, BASE_DOMAIN)
    
    if client_name is None:
        print "client name not found"
        sock.close()
        return
    
    client_mq = get_client_mq(CM, client_name)
    
    if client_mq == None:
        print "Send 'client not online' message to peer. Client = ", client_name
        str_err = user_not_found_str(client_name)
        mysock.send_all(sock, str_err)
        return
    
    #register peer to client
    peer = _add_peer_to_client(client_mq, sock)
    
    if peer == None:
        print "can't add peer. MAX_CONN REACHED?"
        return
    
    #print "peer baru.ses_id =", peer.ses_id
    
    #forward request packet to client
    req_pkt = client.ReqPkt(peer, ba)
    _peer_add_reqpkt_to_client(client_mq, req_pkt)
    peer.trf_req += len(req_pkt.payload)
    
    while True:
        wlist = []
        
        #fetch RSP Pkt
        try:
            for _ in xrange(0, Peer.RSP_FORWARD_NUM):
                msg = peer.in_mq.get_nowait()
                rsp = msg['pkt']
                peer.rsp_list.append(rsp)
        except gevent.queue.Empty:
            pass
        
        #select() sock utk write jika ada RSP-pkt
        if len(peer.rsp_list) > 0:
            wlist.append(sock)
            
        rsocks, wsocks, _ = select.select([sock], wlist , [], 0.1)
        
        #sock bisa di read
        if len(rsocks) > 0:
            #TODO : buat fungsi sendiri . seperti peer.forward_rsp_pkt, di-loop
            ba, err = mysock.recv(sock, BUF_LEN)
            if len(ba) == 0:
                #peer close the socket
                #print "peer ended"
                peer.close()
                _peer_del_from_client(client_mq, peer)
                break    
            elif len(ba) > 0:
                req_pkt = client.ReqPkt(peer, ba)
                _peer_add_reqpkt_to_client(client_mq, req_pkt)
                peer.trf_req += len(req_pkt.payload)
        
        if len(wsocks) > 0:
            peer.forward_rsp_pkt()
        
        if peer.ended == True and len(peer.rsp_list) == 0:
            peer.close()
            _peer_del_from_client(client_mq, peer)
            break
        
        gevent.sleep(0)
    
    #send usage to server
    report_usage(client_name, peer.trf_req, peer.trf_rsp)
        
def peer_server(port):
    server = StreamServer(('0.0.0.0', port), handle_peer)
    print 'Starting peer server on port ', port
    print 'BASE_DOMAIN = ', BASE_DOMAIN
    server.serve_forever()

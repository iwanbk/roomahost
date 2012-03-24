"""
Peer Daemon
Copyright 2012 Iwan Budi Kusnanto
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
    """Class that represents a Peer."""
    RSP_FORWARD_NUM = 5
    MT_ADD_RSP_PKT = 1
    
    def __init__(self, sock, addr, client_mq = None):
        self.sock = sock
        self.addr = addr
        self.ses_id = None
        self.ended = False
        self.rsp_list = []
        self.in_mq = gevent.queue.Queue(10)
        
        self.client_mq = client_mq
        
        #Transferred RSP packet, in bytes
        self.trf_rsp = 0
        
        #transferred Req packets, in bytes
        self.trf_req = 0
    
    def close(self):
        '''Close peer connection.'''
        if self.ended == False or len(self.rsp_list) > 0:
            return False
        self.sock.close()
        self._unreg()
        return True
    
    def _unreg(self):
        '''unreg the peer from client.'''
        msg = {}
        msg['mt'] = client.Client.MT_PEER_DEL_REQ
        msg['ses_id'] = self.ses_id
        self.client_mq.put(msg)
        
    def enq_rsp(self, payload):
        '''Enqueue response packet.'''
        self.rsp_list.insert(0, payload)
    
    def _do_forward_rsp_pkt(self):
        '''Forward response packet to peer.'''
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
        '''Forward response packet to peer.'''
        for _ in xrange(0, self.RSP_FORWARD_NUM):
            written = self._do_forward_rsp_pkt()
            if written <= 0:
                break
            self.trf_rsp += written

def user_not_found_str(user):
    '''User not found error message.'''
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Content-Length: 173\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big><b>" + user + " </b> is not online now</big></center>"
    html += "</body></html>"
    return html

def handle_client_not_found(client_name, sock):
    '''User not found handler.'''
    print "Send 'client not online' message to peer. Client = ", client_name
    str_err = user_not_found_str(client_name)
    mysock.send_all(sock, str_err)
    
def get_client_own_domain(host):
    '''Get client name yang memiliki own-domain.'''
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
            return get_client_own_domain(host)
        else:
            return host[:idx]
    except AttributeError:
        return None

def get_client_mq(subdom):
    '''get client Queue.
    The queue will be used to send request packet.
    '''
    temp_q = gevent.queue.Queue(1)
    msg = {}
    msg['mt'] = ClientMgr.MT_CLIENT_GET_REQ
    msg['user_str'] = subdom
    msg['q'] = temp_q
    
    CM.in_mq.put(msg)
    
    rsp = temp_q.get()
    client_mq = rsp['client_mq']
    return client_mq
    
def register_peer(peer):
    '''Register peer to client.'''
    temp_q = gevent.queue.Queue(1)
    msg = {}
    msg['mt'] = client.Client.MT_PEER_ADD_REQ
    msg['in_mq'] = peer.in_mq
    msg['q'] = temp_q
    peer.client_mq.put(msg)
    
    rsp = temp_q.get()
    
    return rsp['ses_id']
    
def forward_reqpkt_to_client(client_mq, ses_id, ba_req):
    '''Forward request packet to client.'''
    req_pkt = client.ReqPkt(ses_id, ba_req)
    msg = {}
    msg['mt'] = client.Client.MT_REQPKT_ADD_REQ
    msg['req_pkt'] = req_pkt
    client_mq.put(msg)

def handle_peer(sock, addr):
    '''Peer connection handler.'''
    #print "##### peer baru ############"
    #print "sock = ", sock
    #print "addr = ", addr
    
    #get request
    ba_req, err = mysock.recv(sock, BUF_LEN)
    if err != None or len(ba_req) == 0:
        return
    
    #get client name
    client_name = get_client_name(ba_req, BASE_DOMAIN)
    
    if client_name is None:
        print "client name not found"
        sock.close()
        return
    
    client_mq = get_client_mq(client_name)
    
    if client_mq == None:
        handle_client_not_found(client_name, sock)
        return
    
    #register peer to client
    peer = Peer(sock, addr, client_mq)
    peer.ses_id = register_peer(peer)
    
    if peer.ses_id == None:
        print "can't add peer. MAX_CONN REACHED?"
        peer.close()
        return
    
    #forward request packet to client
    forward_reqpkt_to_client(client_mq, peer.ses_id, ba_req)
    peer.trf_req += len(ba_req)
    
    while True:
        #fetch response packet
        try:
            for _ in xrange(0, Peer.RSP_FORWARD_NUM):
                msg = peer.in_mq.get_nowait()
                rsp = msg['pkt']
                peer.rsp_list.append(rsp)
        except gevent.queue.Empty:
            pass
        
        #select() sock utk write jika ada RSP-pkt
        wlist = []
        if len(peer.rsp_list) > 0:
            wlist.append(sock)
            
        rsocks, wsocks, _ = select.select([sock], wlist , [], 0.1)
        
        #rsocks can be read
        if len(rsocks) > 0:
            ba_req, err = mysock.recv(sock, BUF_LEN)
            if len(ba_req) == 0:
                peer.close()
                break    
            elif len(ba_req) > 0:
                forward_reqpkt_to_client(client_mq, peer.ses_id, ba_req)
                peer.trf_req += len(ba_req)
        
        if len(wsocks) > 0:
            peer.forward_rsp_pkt()
        
        if peer.ended == True and len(peer.rsp_list) == 0:
            peer.close()
            break
        
        gevent.sleep(0)
    
    #send usage to server
    report_usage(client_name, peer.trf_req, peer.trf_rsp)
        
def peer_server(port):
    '''Peer daemon startup function.'''
    server = StreamServer(('0.0.0.0', port), handle_peer)
    print 'Starting peer daemon on port ', port
    print 'BASE_DOMAIN = ', BASE_DOMAIN
    server.serve_forever()
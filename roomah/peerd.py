"""
Peer Daemon
Copyright 2012 Iwan Budi Kusnanto
"""
import select
import logging
import logging.handlers

import gevent
from gevent.server import StreamServer
import jsonrpclib

import mysock
import http_utils
import rhconf
import rhmsg
import authstat
import packet

BASE_DOMAIN = ""
CM = None
BUF_LEN = 1024

LOG_FILENAME = rhconf.LOG_FILE_PEERD
logging.basicConfig(level = rhconf.LOG_LEVEL_PEERD) 
LOG = logging.getLogger("peerd")
rotfile_handler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME,
    maxBytes = rhconf.LOG_MAXBYTE_PEERD,
    backupCount = 10
)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
rotfile_handler.setFormatter(formatter)
LOG.addHandler(rotfile_handler)
LOG.setLevel(rhconf.LOG_LEVEL_PEERD)

if rhconf.LOG_STDERR_PEERD:
    stderr_handler = logging.StreamHandler()
    LOG.addHandler(stderr_handler)

class Peer:
    """Class that represents a Peer."""
    RSP_FORWARD_NUM = 5
    
    def __init__(self, sock, addr, client_name, client_mq = None):
        self.sock = sock
        self.addr = addr
        self.client_name = client_name
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
        self.sock.close()
        self._unreg()
        self.rsp_list = []
        return True
    
    def _unreg(self):
        '''unreg the peer from client.'''
        msg = {}
        msg['mt'] = rhmsg.CL_DELPEER_REQ
        msg['ses_id'] = self.ses_id
        self.client_mq.put(msg)
        
    def enq_rsp(self, payload):
        '''Enqueue response packet.'''
        self.rsp_list.insert(0, payload)
    
    def _do_forward_rsp_pkt(self):
        '''Forward response packet to peer.'''
        if len(self.rsp_list) == 0:
            return True, 0
        
        rsp = self.rsp_list.pop(0)
        
        if rsp.payload[0] == packet.TYPE_DATA_RSP:
            return self._do_forward_data_pkt(rsp)
        elif rsp.payload[0] == packet.TYPE_CTRL:
            return self._handle_ctrl_pkt(rsp)
        else:
            LOG.info("unknown rsp packet type for client = %s" % self.client_name)
            return False, 0
        
    def _do_forward_data_pkt(self, rsp):
        """Forward DataRsp packet."""
        data = rsp.get_data()
        
        written, err = mysock.send(self.sock, data)
        if err != None:
            LOG.warning("_do_forward_data_pkt:can't forward data to peer. end this peer")
            self.ended = True
            return False, -1
        
        if written != len(data):
            LOG.warning("peer.forward_rsp_pkt partial %s:%s" % self.addr)
            self.enq_rsp(data[written])
        
        if rsp.is_eof() == True:
            self.ended = True
        
        return True, written
    
    def _handle_ctrl_pkt(self, rsp):
        """Handle Ctrl packet from client."""
        if rsp.is_local_down():
            handle_local_down(self.client_name, self.sock)
            return False, 0
        else:
            LOG.warning("unknown ctrl pkt type=", rsp.payload[1])
            return False, 0
        
    def forward_rsp_pkt(self):
        '''Forward response packet to peer.'''
        for _ in xrange(0, self.RSP_FORWARD_NUM):
            is_ok, written = self._do_forward_rsp_pkt()
            if not is_ok:
                return False
            if written <= 0:
                break
            self.trf_rsp += written
        
        return True

def user_offline_str(user):
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

def handle_client_offline(client_name, sock):
    '''User not found handler.'''
    LOG.info("Send 'client not online' message to peer. Client = %s " % client_name)
    str_err = user_offline_str(client_name)
    mysock.send_all(sock, str_err)

def local_down_str(client_name):
    '''User not found error message.'''
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Content-Length: 173\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big>Local web server of <b>" + client_name + " </b> is down now</big></center>"
    html += "</body></html>"
    return html

def handle_local_down(client_name, sock):
    LOG.info("Send 'local down' message to peer. Client = %s " % client_name)
    str_err = local_down_str(client_name)
    mysock.send_all(sock, str_err)
    
def get_client_name(req, base_domain = BASE_DOMAIN):
    '''Get client name dari HTTP Request header.'''
    header = http_utils.get_http_req_header(req)
    
    if header == None:
        return None
    try:
        host = header['Host']
        idx = host.find("." + base_domain)
        if idx < 0:
            return authstat.get_client_own_domain(host)
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
    msg['mt'] = rhmsg.CM_GETCLIENT_REQ
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
    msg['mt'] = rhmsg.CL_ADDPEER_REQ
    msg['in_mq'] = peer.in_mq
    msg['q'] = temp_q
    peer.client_mq.put(msg)
    
    rsp = temp_q.get()
    
    return rsp['ses_id']
    
def forward_reqpkt_to_client(client_mq, ses_id, ba_req):
    '''Forward request packet to client.'''
    req_pkt = rhmsg.HttpReq(ses_id, ba_req)
    msg = {}
    msg['mt'] = rhmsg.CL_ADD_REQPKT_REQ
    msg['req_pkt'] = req_pkt
    client_mq.put(msg)

def handle_peer(sock, addr):
    '''Peer connection handler.'''
    #LOG.debug("new_peer.addr = %s %s" % addr)
    
    #get request
    ba_req, err = mysock.recv(sock, BUF_LEN)
    if err != None or len(ba_req) == 0:
        return
    
    #get client name
    client_name = get_client_name(ba_req, BASE_DOMAIN)
    
    if client_name is None:
        LOG.warning("client name not found.aaddr = %s:%s" % addr)
        sock.close()
        return
    
    #check client status
    client_status = authstat.client_status(client_name) 
    if client_status != authstat.RH_STATUS_OK:
        LOG.info("Access denied. Client status for %s is %d." % (client_name, client_status))
        mysock.send_all(sock, authstat.client_status_msg(client_status, client_name))
        return
    
    #get pointer to client mq
    client_mq = get_client_mq(client_name)
    
    if client_mq == None:
        handle_client_offline(client_name, sock)
        return
    
    #register peer to client
    peer = Peer(sock, addr, client_name, client_mq)
    peer.ses_id = register_peer(peer)
    
    if peer.ses_id == None:
        LOG.error("can't add peer. MAX_CONN REACHED %s" % client_name)
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
                peer.ended = True
                break    
            elif len(ba_req) > 0:
                forward_reqpkt_to_client(client_mq, peer.ses_id, ba_req)
                peer.trf_req += len(ba_req)
        
        if len(wsocks) > 0:
            is_ok = peer.forward_rsp_pkt()
        
        if peer.ended == True:
            break
        
        gevent.sleep(0)
    
    peer.close()
    
    #send usage to server
    authstat.report_usage(client_name, peer.trf_req, peer.trf_rsp)
        
def peer_server(port):
    '''Peer daemon startup function.'''
    server = StreamServer(('0.0.0.0', port), handle_peer)
    print 'Starting peer daemon on port ', port
    print 'BASE_DOMAIN = ', BASE_DOMAIN
    server.serve_forever()
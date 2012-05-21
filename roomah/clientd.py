"""
Client Daemon
Copyright : Iwan Budi Kusnanto
"""
import select
import logging
import logging.handlers

import gevent
from gevent.server import StreamServer
import jsonrpclib

import packet
import mysock
import rhconf
import rhmsg

AUTH_RES_OK = 1
AUTH_RES_UNKNOWN_ERR = 0
AUTH_RES_PKT_ERR = -1

BUF_LEN = 1024
CM = None

LOG_FILENAME = rhconf.LOG_FILE_CLIENTD
logging.basicConfig(level=rhconf.LOG_LEVEL_CLIENTD)
LOG = logging.getLogger("clientd")
rotfile_handler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME,
    maxBytes=rhconf.LOG_MAXBYTE_CLIENTD,
    backupCount=10,
)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
rotfile_handler.setFormatter(formatter)
LOG.addHandler(rotfile_handler)
LOG.setLevel(rhconf.LOG_LEVEL_CLIENTD)

if rhconf.LOG_STDERR_CLIENTD:
    stderr_handler = logging.StreamHandler()
    LOG.addHandler(stderr_handler)


class Client:
    """Represent a client."""
    def __init__(self, user, sock, addr):
        self.ses_id = 1
        self.user = user
        self.addr = addr

        #socket for this user
        self.sock = sock
        
        #list of request packet from peer
        self.req_pkt = []
        
        #list of ctrt packet
        self.ctrl_pkt = []
        
        #true if this client is waiting for PING-RSP
        self.wait_ping_rsp = False
        
        #dict of peers mq
        self.peers_mq = {}
        
        #input mq
        self.in_mq = gevent.queue.Queue(10)
        
        #if dead
        self.dead = False
    
    def disconnect(self):
        """Disconnect this client."""
        if self.sock:
            print "closing the socket"
            self.sock.close()

    def _add_peer(self, in_mq):
        '''Add a peer to this client.'''
        ses_id = self._gen_ses_id()
        if ses_id < 0:
            return None
        self.peers_mq[ses_id] = in_mq
        
        return ses_id
    
    def _del_peer(self, ses_id):
        '''Del peer from this client.'''
        del self.peers_mq[ses_id]
    
    def _do_process_msg(self):
        '''process message.'''
        try:
            msg = self.in_mq.get_nowait()
        except gevent.queue.Empty:
            return 0
        
        if msg['mt'] == rhmsg.CL_ADDPEER_REQ:
            """Add peer request handler.
            Ses id will be set to None if there is no ses_id left."""
            q_rep = msg['q']
            ses_id = self._add_peer(msg['in_mq'])
            
            rsp = {}
            rsp['mt'] = rhmsg.CL_ADDPEER_RSP
            rsp['ses_id'] = ses_id
            try:
                q_rep.put(rsp)
            except gevent.queue.Full:
                pass
            
        elif msg['mt'] == rhmsg.CL_DELPEER_REQ:
            #print "[Client]del peer with ses_id=", msg['ses_id']
            ses_id = msg['ses_id']
            self._del_peer(ses_id)
            
        elif msg['mt'] == rhmsg.CL_ADD_REQPKT_REQ:
            self._add_req_pkt(msg['req_pkt'])
        else:
            LOG.error("Client.process_msg.unknown_message")
        
        return 1
    
    def process_msg(self):
        '''Process message to this client.'''
        for _ in xrange(0, 10):
            if self._do_process_msg() == 0:
                break
            
    def _inc_ses_id(self, ses_id):
        '''Increase session id.'''
        if ses_id == 255:
            return 1
        else:
            return ses_id + 1
    
    def _gen_ses_id(self):
        """Generate session id.
        return -1 if there is no ses_id left."""
        start_id = self.ses_id
        
        ses_id = start_id
        
        while ses_id in self.peers_mq.keys():
            ses_id = self._inc_ses_id(ses_id)
            if ses_id == start_id:
                return -1
            
        self.ses_id = self._inc_ses_id(ses_id)
        
        return ses_id
    
    def _add_req_pkt(self, req_pkt):
        '''add req pkt from to client's req_pkt list'''
        self.req_pkt.append(req_pkt)
    
    def req_pkt_fwd(self):
        '''Forward request packet to client.'''
        if len(self.req_pkt) == 0:
            return
        
        req = self.req_pkt.pop(0)
        
        req_pkt = packet.DataReq()
        req_pkt.build(req.payload, req.ses_id)
        
        written, err = mysock.send_all(self.sock, req_pkt.payload)
        
        if written != len(req_pkt.payload) or err != None:
            LOG.error("failed to send req pkt to client:%s" % self.user)
            self.dead = True
            return False
    
    def send_ctrl_pkt(self):
        '''send ctrl packet to client.'''
        if len(self.ctrl_pkt) == 0:
            return True
        
        LOG.debug("send ctrl pkt to client:%s" % self.user)
        
        pkt = self.ctrl_pkt.pop(0)
        written, err = mysock.send_all(self.sock, pkt.payload)
        if written != len(pkt.payload) or err != None:
            LOG.error("failed to send ctrl_pkt to:%s.type = %d" %
                      self.user, pkt.payload[1])
            self.dead = True
            return False
        return True
    
    def ping_rsp_send(self):
        '''Send PING-RSP to client.'''
        if self.wait_ping_rsp == False:
            return True
        
        p_rsp = packet.PingRsp()
        
        written, err = mysock.send_all(self.sock, p_rsp.payload)
        
        if err != None or (len(p_rsp.payload) != written):
            LOG.error("error sending PING-RSP to %s" % self.user)
            return False
        
        self.wait_ping_rsp = False
        
    def process_rsp_pkt(self, ba_rsp, rsp_len):
        '''Forwad response packet to peer.'''
        #len checking
        if rsp_len < packet.MIN_HEADER_LEN:
            LOG.error("FATAL:packet too small,discard.user = %s" % self.user)
            return
        
        if ba_rsp[0] == packet.TYPE_DATA_RSP:
            return self.process_datarsp_pkt(ba_rsp)
        elif ba_rsp[0] == packet.TYPE_CTRL:
            return self.process_ctrlrsp_pkt(ba_rsp)
        else:
            LOG.error("FATAL:unrecognized packet type = %s" % self.user)
            return
        
    def process_datarsp_pkt(self, ba_rsp):
        """Process Data Rsp Packet."""
        rsp = packet.DataRsp(ba_rsp)
        
        #get ses_id
        ses_id = rsp.get_sesid()
        
        if rsp.cek_valid() == False:
            LOG.error("FATAL :Not DATA-RSP.user = %s" % self.user)
            packet.print_header(rsp.payload)
            return False
        
        #get peer mq
        if ses_id not in self.peers_mq:
            """ses_id not found.
            - discard packet
            - kirim notifikasi ke client bahwa ses_id ini sudah dead."""
            LOG.debug("ses_id %d not found. peer already dead" % ses_id)
            peer_dead_pkt = packet.CtrlPkt()
            peer_dead_pkt.build_peer_dead(ses_id)
            self.ctrl_pkt.append(peer_dead_pkt)
            return
        
        peer_mq = self.peers_mq[ses_id]
        
        #send RSP-PKT to peer mq
        msg = {}
        msg['mt'] = rhmsg.PD_ADD_RSP_PKT
        msg['pkt'] = rsp
        
        peer_mq.put(msg)
    
    def process_ctrlrsp_pkt(self, ba_rsp):
        """Process Ctrl Rsp packet."""
        print "receive ctrl rsp"
        rsp = packet.CtrlPkt(ba_rsp)
        
        #get ses_id
        ses_id = rsp.get_ses_id()
        
        #get peer mq
        if ses_id not in self.peers_mq:
            """ses_id not found.
            - discard packet"""
            if rsp.is_local_down():
                """Client already closed the connection."""
                return
            else:
                """Send notification to client that this ses_id already died."""
                LOG.debug("ses_id %d not found. peer already dead" % ses_id)
                peer_dead_pkt = packet.CtrlPkt()
                peer_dead_pkt.build_peer_dead(ses_id)
                self.ctrl_pkt.append(peer_dead_pkt)
                return
        
        peer_mq = self.peers_mq[ses_id]
        
        #send RSP-PKT to peer mq
        msg = {}
        msg['mt'] = rhmsg.PD_ADD_RSP_PKT
        msg['pkt'] = rsp
        
        peer_mq.put(msg)

def client_auth_rpc(username, password):
    """Do client auth RPC call."""
    auth_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = auth_server.rh_auth(str(username), str(password))
    return res


def client_auth(sock, addr):
    """Authenticate the client."""
    ba_req, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        LOG.warning("can't recv auth req %s:%s" % addr)
        return None, AUTH_RES_UNKNOWN_ERR
    
    auth_req = packet.AuthReq(ba_req)
    if not auth_req.cek_valid():
        LOG.fatal("Bad AuthReq packet")
        return None, AUTH_RES_PKT_ERR
    
    auth_rsp = packet.AuthRsp()
    auth_res = AUTH_RES_OK
    
    user, password = auth_req.get_userpassword()
    if client_auth_rpc(user, password) != True:
        LOG.debug("auth rpc failed for user %s at %s" % (user, addr))
        auth_rsp.build(packet.AUTH_RSP_BAD_USERPASS)
        auth_res = AUTH_RES_UNKNOWN_ERR
    else:
        auth_rsp.build(packet.AUTH_RSP_OK)
        
    written, err = mysock.send_all(sock, auth_rsp.payload)
    if err != None or written < len(auth_rsp.payload):
        LOG.error("send auth reply failed.%s:%s" % addr)
        return user, AUTH_RES_UNKNOWN_ERR
    
    return user, auth_res


def unregister_client(client):
    """Unregister client from Client Manager."""
    msg = {}
    msg['mt'] = rhmsg.CM_DELCLIENT_REQ
    msg['user'] = client.user
    
    CM.in_mq.put(msg)

    
def register_client(user, in_mq):
    """Register client to Client Manager."""
    msg = {}
    msg['mt'] = rhmsg.CM_ADDCLIENT_REQ
    msg['user'] = user
    msg['in_mq'] = in_mq
    
    #send the message
    CM.in_mq.put(msg)
    
    #wait the reply
    return True

    
def handle_client(sock, addr):
    """Client handler."""
    LOG.debug("new client %s:%s" % addr)
    #client authentication
    user, auth_res = client_auth(sock, addr)
    if auth_res != AUTH_RES_OK:
        LOG.debug("AUTH failed.addr = %s:%s" % addr)
        return
    
    cli = Client(user, sock, addr)
    #register to client manager
    if register_client(cli.user, cli.in_mq) == False:
        LOG.fatal("REGISTER failed.user = %s" % cli.user)
        return
    
    while True:
        #process incoming messages
        cli.process_msg()
        
        #select() sock
        wlist = []
        if len(cli.req_pkt) > 0 or cli.wait_ping_rsp == True or     len(cli.ctrl_pkt) > 0:
            wlist.append(sock)
            
        rsocks, wsocks, _ = select.select([sock], wlist, [], 0.1)
        if len(rsocks) > 0:
            ba_pkt, err = packet.get_all_data_pkt(sock)
            if ba_pkt is None or err is not None:
                LOG.debug("read client sock err.exiting")
                break
            
            if ba_pkt[0] == packet.TYPE_DATA_RSP or ba_pkt[0] == packet.TYPE_CTRL:
                cli.process_rsp_pkt(ba_pkt, len(ba_pkt))
            elif ba_pkt[0] == packet.TYPE_PING_REQ:
                cli.wait_ping_rsp = True

        if len(wsocks) > 0:
            if cli.send_ctrl_pkt() == False:
                break
            #forward http request packet to client
            if cli.req_pkt_fwd() == False:
                break
            #send PING-RSP to client
            if cli.ping_rsp_send() == False:
                break

        gevent.sleep(0)
    
    unregister_client(cli)
    cli.disconnect()


def client_server(port):
    """Client daemon initialization function."""
    server = StreamServer(('0.0.0.0', port), handle_client)
    print 'Starting client server on port ', port
    server.serve_forever()

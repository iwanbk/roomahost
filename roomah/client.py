import sys
import select

import gevent
from gevent.server import StreamServer
import jsonrpclib

from peer import Peer
import packet
import mysock
import auth_rpcd
from client_mgr import ClientMgr

AUTH_RES_OK = 1
AUTH_RES_UNKNOWN_ERR = 0

auth_server = jsonrpclib.Server('http://localhost:4141')

BUF_LEN = 1024
CM = None

class ReqPkt:
    def __init__(self, peer, payload):
        self.peer = peer
        self.payload = payload
        
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
        self.peers_mq = {}
        self.in_mq = gevent.queue.Queue(10)
    
    def _add_peer(self, in_mq):
        ses_id = self._gen_ses_id()
        if ses_id == None:
            return None
        self.peers_mq[ses_id] = in_mq
        
        return ses_id
    
    def _del_peer(self, ses_id):
        del self.peers_mq[ses_id]
    
    def _do_process_msg(self):
        try:
            msg = self.in_mq.get_nowait()
        except gevent.queue.Empty:
            return 0
        
        if msg['mt'] == self.MT_PEER_ADD_REQ:
            q = msg['q']
            in_mq = msg['in_mq']
            ses_id = self._add_peer(in_mq)
            
            rsp = {}
            rsp['mt'] = self.MT_PEER_ADD_RSP
            rsp['ses_id'] = ses_id
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
        
        return 1
    
    def process_msg(self):
        '''Process message to this client.'''
        for _ in xrange(0, 10):
            if self._do_process_msg() == 0:
                break
            
    def _inc_ses_id(self, ses_id):
        if ses_id == 255:
            return 1
        else:
            return ses_id + 1
        
    def _gen_ses_id(self):
        start_id = self.ses_id
        
        ses_id = start_id
        
        while ses_id in self.peers_mq.keys():
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
            print "error sending PING-RSP to ", self.user
            return False
        
        self.wait_ping_rsp = False
        
    def procsess_rsp_pkt(self, ba, ba_len):
        '''Forwad RSP Pkt to peer.'''
        #len checking
        if ba_len < packet.MIN_HEADER_LEN:
            print "FATAL:packet too small. discard"
            sys.exit(-1)
        
        #build rsp_packet
        rsp = packet.DataRsp(ba)
        
        #get ses_id
        ses_id = rsp.get_sesid()
        
        if rsp.cek_valid() == False:
            print "FATAL : bukan DATA RSP"
            packet.print_header(rsp.payload)
            sys.exit(-1)
        
        #get peer mq
        if ses_id not in self.peers_mq:
            '''ses_id sudah tidak ada.discard packet.'''
            return
        
        peer_mq = self.peers_mq[ses_id]
        
        #send RSP-PKT to peer mq
        msg = {}
        msg['mt'] = Peer.MT_ADD_RSP_PKT
        msg['pkt'] = rsp
        
        peer_mq.put(msg)


def client_auth_reply(sock):
    pass

def client_auth_rpc(username, password):
    res = auth_server.auth_client(str(username), str(password))
    return res

def client_auth(sock):
    #get auth req
    ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "can't recv auth req"
    
    pkt = packet.Packet(None, ba)
    
    if pkt.auth_req_cek() == False:
        print "Bukan Paket AUTH REQ"
        sys.exit(-1)
    
    user, password = pkt.auth_req_get_userpassword()
    print "user = ", user
    print "password = ", password
    
    if client_auth_rpc(user, password) != auth_rpcd.RES_OK:
        print "auth error"
        return user, AUTH_RES_UNKNOWN_ERR
    
    rsp = packet.Packet(packet.TYPE_AUTH_RSP)
    rsp.auth_rsp_build(packet.AUTH_RSP_OK)
    
    written, err = mysock.send_all(sock, rsp.payload)
    if err != None or written != len(rsp.payload):
        print "can't send auth reply"
        return user, AUTH_RES_UNKNOWN_ERR
    
    return user, AUTH_RES_OK

def unregister_client(CM, client):
    msg = {}
    msg['mt'] = CM.MT_CLIENT_DEL_REQ
    msg['user'] = client.user
    
    CM.in_mq.put(msg)
    
def register_client(CM, user, in_mq):
    #prepare the message
    msg = {}
    msg['mt'] = ClientMgr.MT_CLIENT_ADD_REQ
    msg['user'] = user
    msg['in_mq'] = in_mq
    
    #send the message
    CM.in_mq.put(msg)
    
    #wait the reply
    return True
    
def handle_client(sock, addr):
    print "sock = ", sock
    print "addr = ", addr
    
    user, auth_res = client_auth(sock)
    if auth_res != AUTH_RES_OK:
        print "AUTH failed"
        return
    
    cli = Client(user, sock)
    register_client(CM, cli.user, cli.in_mq)
    
    while True:
        cli.process_msg()
        
        #select() sock
        wlist = []
        if len(cli.req_pkt) > 0 or cli.wait_ping_rsp == True:
            wlist.append(sock)
            
            
        rsocks, wsocks, _ = select.select([sock], wlist , [], 0.1)
        if len(rsocks) > 0:       
            ba, err = packet.get_all_data_pkt(sock)
            if ba is None or err is not None:
                print "read client sock err.exiting.."
                break
            
            if ba[0] == packet.TYPE_DATA_RSP:  
                cli.procsess_rsp_pkt(ba, len(ba))
            elif ba[0] == packet.TYPE_PING_REQ:
                #print "[PING-REQ] from ", client.user
                cli.wait_ping_rsp = True
        
        
        if len(wsocks) > 0:
            #forward http request packet to client
            if cli.req_pkt_fwd(1) == False:
                break
            #send PING-RSP to client
            if cli.ping_rsp_send() == False:
                break

        gevent.sleep(0)
    
    #CM.del_client(client)
    unregister_client(CM, cli)

def client_server(port):
    server = StreamServer(('0.0.0.0', port), handle_client)
    print 'Starting client server on port ', port
    server.serve_forever()

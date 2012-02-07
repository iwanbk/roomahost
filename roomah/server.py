import sys
import select

import jsonrpclib
from gevent.server import StreamServer
import gevent
import gevent.pool
from gevent import queue
from gevent import monkey; monkey.patch_all()


import client_mgr
from client_mgr import ClientMgr
from client import Client
from peer import Peer
import mysock
import packet
from client import ReqPkt
import http_utils
import auth_rpcd

BUF_LEN = 1024

CM = client_mgr.ClientMgr()

BASE_DOMAIN = "homehost.tk"
auth_server = jsonrpclib.Server('http://localhost:4141')

AUTH_RES_OK = 1
AUTH_RES_UNKNOWN_ERR = 0
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
    
    written, err = mysock.send(sock, rsp.payload)
    if err != None:
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
    print "BASE_DOMAIN = ", BASE_DOMAIN
    print "sock = ", sock
    print "addr = ", addr
    
    user, auth_res = client_auth(sock)
    if auth_res != AUTH_RES_OK:
        print "AUTH failed"
        return
    
    client = Client(user, sock)
    register_client(CM, client.user, client.in_mq)
    
    while True:
        client.process_msg()
        
        #select() sock
        wlist = []
        if len(client.req_pkt) > 0 or client.wait_ping_rsp == True:
            wlist.append(sock)
            
            
        rsocks,wsocks, xsocks = select.select([sock], wlist , [], 0.1)
        if len(rsocks) > 0:       
            ba, err = packet.get_all_data_pkt(sock)
            if ba is None or err is not None:
                print "read client sock err.exiting.."
                break
            
            if ba[0] == packet.TYPE_DATA_RSP:  
                client.procsess_rsp_pkt(ba, len(ba))
            elif ba[0] == packet.TYPE_PING_REQ:
                #print "[PING-REQ] from ", client.user
                client.wait_ping_rsp = True
        
        
        if len(wsocks) > 0:
            #forward http request packet to client
            if client.req_pkt_fwd(1) == False:
                break
            #send PING-RSP to client
            if client.ping_rsp_send() == False:
                break

        gevent.sleep(0)
    
    #CM.del_client(client)
    unregister_client(CM, client)

def client_server(port):
    server = StreamServer(('0.0.0.0', port), handle_client)
    print 'Starting client server on port ', port
    server.serve_forever()

def get_subdom(req, base_domain = BASE_DOMAIN):
    header = http_utils.get_http_req_header(req)
    
    host= header['Host']
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
    msg['mt'] = Client.MT_PEER_ADD_REQ
    msg['in_mq'] = peer.in_mq
    msg['q'] = q
    client_mq.put(msg)
    
    rsp = q.get()
    
    ses_id = rsp['ses_id']
    
    peer.ses_id = ses_id
    
    return peer

def _peer_add_reqpkt_to_client(client_mq, req_pkt):
    msg = {}
    msg['mt'] = Client.MT_REQPKT_ADD_REQ
    msg['req_pkt'] = req_pkt
    client_mq.put(msg)

def _peer_del_from_client(client_mq, peer):
    msg = {}
    msg['mt'] = Client.MT_PEER_DEL_REQ
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
    
    peer = _add_peer_to_client(client_mq, sock)
    
    if peer == None:
        print "can't add peer. MAX_CONN REACHED?"
        return
    
    #print "peer baru.ses_id =", peer.ses_id
    req_pkt = ReqPkt(peer, ba)
    _peer_add_reqpkt_to_client(client_mq, req_pkt)
    
    while True:
        wlist = []
        
        try:
            msg = peer.in_mq.get_nowait()
            rsp = msg['pkt']
            peer.rsp_list.append(rsp)
        except gevent.queue.Empty:
            pass
        
        if len(peer.rsp_list) > 0:
            wlist.append(sock)
            
        rsocks,wsocks, xsocks = select.select([sock], wlist , [], 0.1)
        
        if len(rsocks) > 0:
            ba, err = mysock.recv(sock, BUF_LEN)
            if len(ba) == 0:
                #peer close the socket
                peer.close()
                _peer_del_from_client(client_mq, peer)
                break    
            elif len(ba) > 0:
                req_pkt = ReqPkt(peer, ba)
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
    
if __name__ == '__main__':
    BASE_DOMAIN = sys.argv[1]
    group = gevent.pool.Group()
    cs = group.spawn(client_server, 3939)
    ps = group.spawn(peer_server, 4000)
    CM.start()
    #gevent.joinall([cs, ps])
    group.join()
import sys
import select

import jsonrpclib
from gevent.server import StreamServer
import gevent
import gevent.pool
from gevent import queue
from gevent import monkey; monkey.patch_all()


import client_mgr
import mysock
import packet
from client_mgr import ReqPkt
import http_utils
import auth_rpcd

BUF_LEN = 1024

CM = client_mgr.ClientMgr()

BASE_DOMAIN = "master.lan"
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

def handle_client(sock, addr):
    print "sock = ", sock
    print "addr = ", addr
    
    user, auth_res = client_auth(sock)
    if auth_res != AUTH_RES_OK:
        print "AUTH failed"
        return
    
    client = CM.add_client(user, sock)
    #print "rsp len = ", len(rsp.payload), ".written = ", written
    
    while True:
        #jika ada di req pkt queue, kirim ke client
        if len(client.req_pkt) > 0:
            client.req_pkt_fwd(1)
        
        #select() sock
        wlist = client.get_socks_need_write()
        rsocks,wsocks, xsocks = select.select([sock], wlist , [], 0.1)
        if len(rsocks) > 0:       
            ba, err = packet.get_all_data_pkt(sock)
            client.procsess_rsp_pkt(ba, len(ba))
            
        if len(wsocks) > 0:
            for s in wsocks:
                peer = client.get_peer_by_sock(s)
                peer.forward_rsp_pkt()
                
        client.del_client_ended()
        gevent.sleep(0)
    
    CM.del_client(client)

def client_server(port):
    server = StreamServer(('0.0.0.0', port), handle_client)
    print 'Starting client server on port ', port
    server.serve_forever()

def get_subdom(req, base_domain = BASE_DOMAIN):
    header = http_utils.get_http_req_header(req)
    
    host= header['host']
    
    idx = host.find("." + base_domain)
    
    if idx < 0:
        return None
    else:
        return host[:idx]
        
def handle_peer(sock, addr):
    #print "##### peer baru ############"
    #print "sock = ", sock
    #print "addr = ", addr
    
    ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "recv error"
        sys.exit(-1)
    
    subdom = get_subdom(ba)
    
    client = CM.get_client(subdom)
    
    peer = client.add_peer(sock)
    
    if peer == None:
        print "can't add peer. MAX_CONN REACHED?"
        return
    
    #print "peer baru.ses_id =", peer.ses_id
    req_pkt = ReqPkt(peer, ba)
    client.add_req_pkt(req_pkt)
    
    while peer.ended == False:
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
    
    #gevent.joinall([cs, ps])
    group.join()
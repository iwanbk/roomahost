import sys
import select

from gevent.server import StreamServer
import gevent
from gevent import queue
from gevent import monkey; monkey.patch_all()

import client_mgr
import mysock
import packet
from client_mgr import ReqPkt

BUF_LEN = 1024

CM = client_mgr.ClientMgr()

def client_auth_reply(sock):
    pass
def handle_client(sock, addr):
    print "sock = ", sock
    print "addr = ", addr
    
    #get auth req
    recvd_len, ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "can't recv auth req"
    
    pkt = packet.Packet(None, ba)
    
    if pkt.auth_req_cek() == False:
        print "bukan paket auth req"
    
    user, password = pkt.auth_req_get_userpassword()
    print "user = ", user
    print "password = ", password
    if user != password:
        print "auth error"
        sys.exit(-1)
    
    client = CM.add_client(user, sock)
    
    rsp = packet.Packet(packet.TYPE_AUTH_RSP)
    rsp.auth_rsp_build(packet.AUTH_RSP_OK)
    
    written, err = mysock.send(sock, rsp.payload)
    if err != None:
        print "can't send auth reply"
        sys.exit(-1)
    
    print "rsp len = ", len(rsp.payload), ".written = ", written
    
    while True:
        #jika ada di req pkt queue, kirim ke client
        if len(client.req_pkt) > 0:
            client.req_pkt_fwd(1)
        
        #select() sock
        rsocks,wsocks, xsocks = select.select([sock], [], [], 1)
        if len(rsocks) > 0:
            client.recv_rsp_pkt()
        if len(wsocks) > 0:
            pass
        
        gevent.sleep(1)

def client_server(port):
    server = StreamServer(('0.0.0.0', port), handle_client)
    print 'Starting client server on port ', port
    server.serve_forever()

def handle_peer(sock, addr):
    print "sock = ", sock
    print "addr = ", addr
    
    recv, ba, err = mysock.recv(sock, BUF_LEN)
    if err != None:
        print "recv error"
        sys.exit(-1)
    #anggap saja domainnya paijo
    client = CM.get_client("paijo")
    
    peer = client.add_peer(sock)
    
    print "peer baru.ses_id =", peer.ses_id
    req_pkt = ReqPkt(peer, ba)
    client.add_req_pkt(req_pkt)
    while True:
        gevent.sleep(0)
        
def peer_server(port):
    server = StreamServer(('0.0.0.0', port), handle_peer)
    print 'Starting peer server on port ', port
    server.serve_forever()
    
if __name__ == '__main__':
    cs = gevent.spawn(client_server, 3939)
    ps = gevent.spawn(peer_server, 4000)
    
    gevent.joinall([cs, ps])
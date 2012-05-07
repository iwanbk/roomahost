#!/usr/bin/env python
"""
Roomahost client
Copyright(2012) Iwan Budi Kusnanto
"""
import sys
import socket
import select
import time
import datetime
import logging
import ConfigParser

import packet
import mysock

SERV_BUF_LEN = 1024
HOST_BUF_LEN = SERV_BUF_LEN - packet.MIN_HEADER_LEN

HOST_CONNS_DICT = {}

logging.basicConfig(level = logging.INFO)
LOG = logging.getLogger("rhclient")

class HostConn:
    '''Connection to host.'''
    def __init__(self, ses_id):
        self.sock = None
        self.ses_id = ses_id
        self.ended = False
        self.rsp_list = []
        self.first_rsp_recvd = False
    
    def reset(self):
        '''reset semua value (set None).'''
        try:
            self.sock.close()
        except Exception:
            pass
        
        self.sock = None
        self.rsp_list = []

class HostRsp:
    '''Response from host.'''
    def __init__(self, h_conn, payload):
        self.conn = h_conn
        self.payload = payload
        
        
def clean_host_conn():
    '''Clean HostConn.
    
    HostConn that will be deleted:
        hostconn that marked as ended
        host conn with empty rsp_list
    '''
    to_del = []
    for h_conn in HOST_CONNS_DICT.itervalues():
        if h_conn.ended == True and len(h_conn.rsp_list) == 0:
            to_del.append(h_conn)
    
    for h_conn in to_del:
        del_host_conn(h_conn.ses_id, h_conn)

def get_host_conn_by_sock(sock):
    '''Get HostConn object from a socket to host.'''
    if sock == None:
        return None
    
    for h_conn in HOST_CONNS_DICT.itervalues():
        if h_conn.sock == sock:
            return h_conn
    
    return None

def del_host_conn(ses_id, h_conn = None):
    '''Del HostConn by ses_id.'''
    conn = h_conn
    if conn == None:
        try:
            conn = HOST_CONNS_DICT[ses_id]
        except KeyError:
            LOG.debug("key_error")
            return 
    conn.reset()
    del HOST_CONNS_DICT[ses_id]

def forward_incoming_req_pkt(ba_req, ba_len, host_host, host_port):
    '''Forward incoming req packet to host.'''
    req = packet.DataReq(ba_req)
    if req.cek_valid() == False:
        LOG.fatal("Bad DATA-REQ packet")
        return
    
    ses_id = req.get_sesid()
    req_data = req.get_data()
    #req_data = rewrite_req(req_data, host_host, host_port)
    LOG.debug("ses_id=%d" % ses_id)
    
    try:
        h_conn = HOST_CONNS_DICT[ses_id]
        LOG.debug("use old connection.ses_id = %d" % h_conn.ses_id)
    except KeyError:
        h_conn = HostConn(ses_id)
        HOST_CONNS_DICT[ses_id] = h_conn
        h_conn.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _, err = mysock.connect(h_conn.sock, (host_host, host_port))
        if err != None:
            LOG.fatal("Connection to %s port %d failed." % (host_host, host_port))
            LOG.fatal("Please check your local web server")
            sys.exit(0)
    
    h_sock = h_conn.sock
    written, err = mysock.send_all(h_sock, req_data)
    if err != None:
        print "error forward"
        del HOST_CONNS_DICT[ses_id]
        sys.exit(-1)
    
    if written != len(req_data):
        print "PARTIAL FORWARD to host"
        print "FATAL UNHANDLED COND"
        sys.exit(-1)

def accept_host_rsp(h_sock):
    '''accept host response.
    enqueue it to rsp_list.
    '''
    #get HostConn object
    h_conn = get_host_conn_by_sock(h_sock)
    if h_conn == None:
        print "FATAL UNHANDLED ERROR:can't get h_conn"
        sys.exit(-1)
        
    #receive the response
    ba_rsp, err = mysock.recv(h_sock, HOST_BUF_LEN)
    if err != None:
        print "FATAL ERROR. error recv resp from host"
        sys.exit(-1)
    
    if len(ba_rsp) == 0:
        LOG.debug("ses_id %d closed", h_conn.ses_id)
        h_sock.close()
        h_conn.ended = True
    
    if h_conn.first_rsp_recvd == False:
        #ba = rewrite_first_rsp(ba, "192.168.56.10", 80, "paijo.master.lan", 80)
        h_conn.first_rsp_recvd = True
        
    h_conn.rsp_list.append(ba_rsp)
        
def _send_rsp_pkt_to_server(rsp_pkt, server_sock):
    '''Send response packet to server.'''
    written, err = mysock.send_all(server_sock, rsp_pkt.payload)
    if err != None:
        print "error sending packet to server"
        sys.exit(-1)
    
    if written != len(rsp_pkt.payload):
        print "partial write to server"
        sys.exit(-1)

def forward_host_rsp(server_sock):
    '''Forward Host response to server.'''
    for h_conn in HOST_CONNS_DICT.itervalues():
        if len(h_conn.rsp_list) > 0:
            ba_rsp = h_conn.rsp_list.pop(0)
            rsp_pkt = packet.DataRsp()
            rsp_pkt.build(ba_rsp, h_conn.ses_id)
    
            if len(ba_rsp) == 0:
                rsp_pkt.set_eof()
            
            _send_rsp_pkt_to_server(rsp_pkt, server_sock)
            
            if rsp_pkt.is_eof():
                h_conn.ended = True

def any_host_response():
    '''check if there is any host response.'''
    for h_conn in HOST_CONNS_DICT.itervalues():
        if len(h_conn.rsp_list) > 0:
            return True
    return False
        
class Client:
    '''Client class.'''
    PING_REQ_PERIOD = 120
    PING_RSP_WAIT_TIME = PING_REQ_PERIOD / 2
    
    def __init__(self, server_sock):
        self.last_ping = time.time()
        self.server_sock = server_sock
        self.to_server_pkt = []
        self.wait_ping_rsp = False
    
    def cek_ping_req(self):
        '''Check last ping
        enqueue ping packet if it exceeded ping period.'''
        if time.time() - self.last_ping >= Client.PING_REQ_PERIOD:
            preq = packet.PingReq()
            self.to_server_pkt.append(preq)
    
    def cek_ping_rsp(self):
        '''Check ping response.
        
        Return false if it exceeding PING_RSP_WAIT_TIME timeout.
        '''
        if not self.wait_ping_rsp:
            return True
        
        if time.time() - self.last_ping > Client.PING_RSP_WAIT_TIME:
            return False
        
        return True
    
    def handle_ping_rsp(self, ba_rsp):
        '''Handle PING-RSP.'''
        self.wait_ping_rsp = False
        self.last_ping = time.time()
    
    def handle_ctrl_pkt(self, ba_pkt):
        """Ctrl Packet Handling dispatcher."""
        pkt = packet.CtrlPkt(ba_pkt)
        if pkt.cek_valid() == False:
            return False
        
        pkt_type = pkt.get_type()
        if pkt_type == pkt.T_PEER_DEAD:
            ses_id = pkt.peer_dead_ses_id()
            self.handle_peer_dead(ses_id)
        else:
            print "Unknown control packet"
            sys.exit(-1)
        
    def handle_peer_dead(self, ses_id):
        """Deleting host conn with ses_id = peer's session id."""
        del_host_conn(ses_id)
        
    def send_to_server_pkt(self):
        '''Send a packet in to_server queue'''
        if len(self.to_server_pkt) == 0:
            return True
        
        pkt = self.to_server_pkt.pop(0)
        
        written, err = mysock.send_all(self.server_sock, pkt.payload)
        if (err != None) or (written != len(pkt.payload)):
            LOG.error("can't send pkt to server")
            return False
        
        if pkt.payload[0] == packet.TYPE_PING_REQ:
            self.last_ping = time.time()
            self.wait_ping_rsp = True
            #print "[PING-REQ]", datetime.datetime.now()
        
        return True
    
    def any_pkt_to_server(self):
        '''True if there is pkt to server.'''
        return len(self.to_server_pkt) > 0

def do_auth(user, password, server_sock):
    """Doing roomahost authentication."""
    auth_req = packet.AuthReq()
    auth_req.build(user, password)
    
    written, err = mysock.send(server_sock, auth_req.payload)
    
    #sending packet failed
    if err != None or written < len(auth_req.payload):
        print "can't send auth req to server.err = ", err
        return False
    
    #receiving reply failed
    ba_rsp, err = mysock.recv(server_sock, 1024)
    if err != None:
        print "failed to get auth reply"
        return False
    
    #bad username/password
    rsp = packet.AuthRsp(ba_rsp)
    if rsp.get_val() != packet.AUTH_RSP_OK:
        print "Authentication failed"
        if rsp.get_val() == packet.AUTH_RSP_BAD_USERPASS:
            print "Bad user/password"
            print "Please check your user/password"
        return False
    return True
    
def client_loop(server, port, user, passwd, host_host, host_port):
    """Main client loop."""
    #connect to server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mysock.setkeepalives(server_sock)
    ret, err = mysock.connect(server_sock, (server, port))
    
    if err != None:
        print "can't connect to server"
        sys.exit(-1)
    
    if do_auth(user, passwd, server_sock) == False:
        sys.exit(1)
        
    print "Authentication successfull"
    
    client = Client(server_sock)
    
    #start looping
    while True:
        #cek last_ping
        client.cek_ping_req()
        
        #server_sock select()
        wsock = []
        if client.any_pkt_to_server() or any_host_response():
            wsock.append(server_sock)
            
        to_read, to_write, _ = select.select([server_sock],
            wsock, [], 1)
        
        if len(to_read) > 0:
            #read sock
            ba_pkt, err = packet.get_all_data_pkt(server_sock)
            if ba_pkt is None or err != None:
                print "Error : Connection to server"
                break
            
            #request packet
            if ba_pkt[0] == packet.TYPE_DATA_REQ:
                forward_incoming_req_pkt(ba_pkt, len(ba_pkt), host_host, host_port)
            
            #ping rsp
            elif ba_pkt[0] == packet.TYPE_PING_RSP:
                #print "PING-RSP ", datetime.datetime.now()
                client.handle_ping_rsp(ba_pkt)
            
            #ctrl packet
            elif ba_pkt[0] == packet.TYPE_CTRL:
                LOG.debug("CTRL Packet. subtype = %d" % ba_pkt[1])
                client.handle_ctrl_pkt(ba_pkt)
            else:
                LOG.error("Unknown packet.type = %d" % ba_pkt[0])
                LOG.fatal("exiting...")
                sys.exit(-1)
        
        if len(to_write) > 0:
            forward_host_rsp(server_sock)
            if client.send_to_server_pkt() == False:
                break
           
        clean_host_conn()
        
        #select() untuk host sock
        rlist = []
        for h_conn in HOST_CONNS_DICT.itervalues():
            if h_conn.sock != None and h_conn.ended == False:
                rlist.append(h_conn.sock)
        
        if len(rlist) > 0:      
            h_read, _, _ = select.select(rlist, [], [], 0.5)
        
            if len(h_read) > 0:
                for sock in h_read:
                    accept_host_rsp(sock)
        
        #cek ping rsp
        if client.cek_ping_rsp() == False:
            LOG.error("PING-RSP timeout")
            break
                
    LOG.error("Client exited...")
    
        
if __name__ == '__main__':
    conf = ConfigParser.ConfigParser()
    conf.read("client.ini")
    
    SERVER = conf.get('roomahost', 'server')
    PORT = int(conf.get('roomahost','port'))
    USER = conf.get('roomahost','user')
    PASSWD = conf.get('roomahost','password')
    HOST_HOST = conf.get('roomahost','localhost_host')
    HOST_PORT = int(conf.get('roomahost','localhost_port'))
    
    client_loop(SERVER, PORT, USER, PASSWD, HOST_HOST, HOST_PORT)
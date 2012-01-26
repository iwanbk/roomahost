import sys
import socket

import packet
import mysock

SERV_BUF_LEN = 1024
HOST_BUF_LEN = SERV_BUF_LEN - packet.MIN_HEADER_LEN

if __name__ == '__main__':
    server = sys.argv[1]
    port = int(sys.argv[2])
    user = sys.argv[3]
    passwd = sys.argv[4]
    host_host = sys.argv[5]
    host_port = int(sys.argv[6])
    
    sock_dict = {}
    
    #connect to server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    mysock.setkeepalives(sock)
    ret, err = mysock.connect(sock, (server, port))
    
    if err != None:
        print "can't connect to server"
        sys.exit(-1)
    
    #send auth req
    pkt = packet.Packet(packet.TYPE_AUTH_REQ)
    pkt.auth_req_build(user, passwd)
    written, err = mysock.send(sock, pkt.payload)
    if err != None:
        print "can't send auth req to client"
        print "err = ", err
    
    print "pkt len = ", len(pkt.payload)
    print "sent len = ", written
    
    recvd, ba, err = mysock.recv(sock, 1024)
    if err != None:
        print "failed to get auth reply"
        sys.exit(-1)
    
    rsp = packet.Packet()
    rsp.payload = ba
    if rsp.auth_rsp_cek() == False:
        print "bukan auth rsp"
        sys.exit(-1)
    
    if rsp.auth_rsp_get_val() != packet.AUTH_RSP_OK:
        print "auth failed"
        sys.exit(-1)
    
    print "AUTH OK"
    str_len, str, err = mysock.recv_str(sock, 1024)
    if err != None:
        print "error receiving data packet"
        sys.exit(-1)
    
    print "###########"
    req_pkt = packet.Packet(packet.TYPE_DATA_REQ, bytearray(str))
    if req_pkt.data_req_cek() == False:
        print "bukan DATA REQ"
        print "FATAL ERROR"
        sys.exit(-1)
    
    ses_id = req_pkt.data_req_get_sesid()
    real_req = req_pkt.data_req_get_data()
    print real_req
    #forward ke host
    h_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ret, err = mysock.connect(h_sock, (host_host, host_port))
    written, err = mysock.send(h_sock, real_req)
    if err != None:
        print "error forward"
        sys.exit(-1)
    
    ba_len, ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
    while err == None:
        rsp_pkt = packet.Packet()
        print "build rsp pkt.ses_id =", ses_id
        rsp_pkt.data_rsp_build(ba, ses_id, 0)
        written, err = mysock.send(sock, rsp_pkt.payload)
        if err != None:
            print "error sending packet to server"
            sys.exit(-1)
        
        if written != len(rsp_pkt.payload):
            print "partial write to server"
            sys.exit(-1)
        
        print "written = ", written
        ba_len, ba, err = mysock.recv(h_sock, HOST_BUF_LEN)
"""
roomahost message
Copyright(2012) - Iwan Budi Kusnanto
"""

#client daemon message type
CL_ADDPEER_REQ = 1 #add peer request
CL_ADDPEER_RSP = 2 #add peer response
CL_DELPEER_REQ = 3 #del peer request
CL_DELPEER_RSP = 4 #del peer response
CL_ADD_REQPKT_REQ = 5 #add request pkt request
CL_ADD_REQPKT_RSP = 6 #add request pkt response

#Client manager message type
CM_ADDCLIENT_REQ = 1
CM_ADDCLIENT_RSP = 2
CM_DELCLIENT_REQ = 3
CM_DELCLIENT_RSP = 4
CM_GETCLIENT_REQ = 5
CM_GETCLIENT_RSP = 6

#peer daemon message type
PD_ADD_RSP_PKT = 1

class HttpReq:
    '''HTTP request message that send from peerd to clientd.'''
    def __init__(self, ses_id, payload):
        self.ses_id = ses_id
        self.payload = payload
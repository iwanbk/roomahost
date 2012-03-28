"""
Roomahost's Client Manager
Copyritght(2012) Iwan Budi Kusnanto
"""
import gevent.queue

import rhmsg

class ClientMgr(gevent.Greenlet):
    '''Client Manager.'''
    PUT_TIMEOUT_DEFAULT = 5
        
    def __init__(self):
        gevent.Greenlet.__init__(self)
        self.clients_mq = {}
        
        #queue of infinite size (gevent > 1.0)
        self.in_mq = gevent.queue.Queue(0)
    
    def _run(self):
        while True:
            msg = self.in_mq.get(block = True, timeout = None)
            self.proc_msg(msg)
            gevent.sleep(0)
            
    def _add_client(self, user, in_mq):
        self.clients_mq[str(user)] = in_mq
    
    def _del_client(self, user):
        del self.clients_mq[str(user)]
        
    def _get_client_mq(self, user_str):
        if user_str in self.clients_mq:
            return self.clients_mq[user_str]
        else:
            return None
    
    def proc_msg(self, msg):
        '''Memproses message dari client & peer.'''
        if msg['mt'] == rhmsg.CM_ADDCLIENT_REQ:
            '''Add Client Msg.'''
            user = msg['user']
            in_mq = msg['in_mq']
            print "CM.proc_msg.client_add user=", user
            
            self._add_client(user, in_mq)
            
        elif msg['mt'] == rhmsg.CM_DELCLIENT_REQ:
            '''Del Client message.'''
            user = msg['user']
            print "CM.proc_msg.client_del user=", user
            self._del_client(user)
        
        elif msg['mt'] == rhmsg.CM_GETCLIENT_REQ:
            user_str = msg['user_str']
            q = msg['q']
            
            rsp = {}
            rsp['mt'] = rhmsg.CM_GETCLIENT_RSP
            rsp['client_mq'] = self._get_client_mq(user_str)
            
            try:
                q.put(rsp, timeout = self.PUT_TIMEOUT_DEFAULT)
            except gevent.queue.Full:
                pass
            
        else:
            print "CM.proc_msg.unknown message"
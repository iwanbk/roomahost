import sys

import gevent.pool
from gevent import monkey; monkey.patch_all()

import client_mgr
import client
import peer

if __name__ == '__main__':
    BASE_DOMAIN = sys.argv[1]
    group = gevent.pool.Group()

    CM = client_mgr.ClientMgr()    
    CM.start()
    
    peer.CM = CM
    peer.BASE_DOMAIN = BASE_DOMAIN
    
    client.CM = CM
    
    cs = group.spawn(client.client_server, 3939)
    ps = group.spawn(peer.peer_server, 4000)
    #gevent.joinall([cs, ps])
    group.join()

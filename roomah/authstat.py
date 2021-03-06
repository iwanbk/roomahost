"""
Roomahost Authentication and Stats Module.

This module is responsible to communicate with external
authentication and stats module.

Function that  communicate with external auth & stats server:
* report_usage
  report traffic usage to server
* client_status
  get client status
* get_client_own_domain
  get own-domain of some client
"""
import time

import jsonrpclib
from gevent import coros

import rhconf

#Client status
RH_STATUS_OK = 0
RH_STATUS_NOT_FOUND = 1
RH_STATUS_QUOTA_EXCEEDED = 2
RH_STATUS_UNKNOWN_ERROR = 100

CL_STATUS_TAB = {}
cl_status_sem = coros.Semaphore()

def report_usage(username, trf_req, trf_rsp):
    '''Report data transfer usage.'''
    stat_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = stat_server.usage_add(username, trf_req, trf_rsp)
    return res

def client_status(username):
    """Get client status."""
    status = cache_status_get(username)
    if status is not None:
        return status
    
    auth_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    status = auth_server.status(username)
    if status != RH_STATUS_NOT_FOUND:
        cache_status_set(username, status)
    return status

def get_client_own_domain(host):
    '''Get client name that have own-domain.'''
    server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = server.rh_domain_client(host)
    return res

def client_status_msg(status, username):
    if status == RH_STATUS_NOT_FOUND:
        return client_notfound_str(username)

def cache_status_get(username):
    """get status from cache.
    return None if it can't found from cache
    or if cache exceed treshold."""
    try:
        cl_status_sem.acquire()
        st = CL_STATUS_TAB[username]
        cl_status_sem.release()
        
        if (time.time() - st['time']) <= rhconf.CACHE_STATUS_SECONDS:
            return st['status']
    except Exception:
        cl_status_sem.release()
        return None
    
def cache_status_set(username, status):
    #update cache
    ts = time.time()
    cl_status_sem.acquire()
    CL_STATUS_TAB[username] = {
        'time' : ts,
        'status' : status,
    }
    cl_status_sem.release()

def cache_status_del(username):
    try:
        cl_status_sem.acquire()
        del CL_STATUS_TAB[username]
    finally:
        cl_status_sem.release()

def client_notfound_str(username):
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big><b>" + username + " </b> is not registered</big></center>"
    html += "</body></html>"
    return html

def quota_exceeded_msg(username):
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big><b>" + username + "  : </b> Quota Exceeded</big></center>"
    html += "</body></html>"
    return html

def unknown_err_msg(username):
    html = "HTTP/1.1\n\
Server: roomahost/0.1\n\
Content-Type: text/html\n\
Connection: close\n\
\r\n\
"
    html += "<html><body>"
    html += "<center><big><b>" + username + " : </b> Unknown Error</big></center>"
    html += "</body></html>"
    return html
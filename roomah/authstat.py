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
import jsonrpclib

import rhconf

#Client status
RH_STATUS_OK = 0
RH_STATUS_NOT_FOUND = 1
RH_STATUS_QUOTA_EXCEEDED = 2
RH_STATUS_UNKNOWN_ERROR = 100

def report_usage(username, trf_req, trf_rsp):
    '''Report data transfer usage.'''
    stat_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = stat_server.usage_add(username, trf_req, trf_rsp)
    return res

def client_status(username):
    """Get client status."""
    auth_server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    return auth_server.status(username)

def get_client_own_domain(host):
    '''Get client name that have own-domain.'''
    server = jsonrpclib.Server(rhconf.AUTH_SERVER_URL)
    res = server.rh_domain_client(host)
    return res

def client_status_msg(status, username):
    if status == RH_STATUS_NOT_FOUND:
        return client_notfound_str(username)

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
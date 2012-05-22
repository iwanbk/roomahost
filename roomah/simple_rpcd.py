import hashlib

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

import authstat

#dictionary of user-password
userpass_dict = {
    "iwanbk":"iwanbk",
    "ibk":"ibk",
    "paijo":"paijo",
}
userdomain_dict = {
    "iwanbk.lan":"iwanbk",
}

#authentication
def rh_auth(username, password):
    try:
        passwd = userpass_dict[username]
    except KeyError:
        print "user not found : ", username
        return False
    
    hashed_pass = hashlib.sha1(passwd).hexdigest()
    if hashed_pass == password:
        return True
    else:
        print "bad pasword = ", password
        return False

#add data transfer usage
def usage_add(username, trf_req, trf_rsp):
    print "---usage add"
    print "username = ", username
    print "trf_req = ", trf_req
    print "trf_rsp = ", trf_rsp
    return True

#get client status
def status(username):
    return authstat.RH_STATUS_OK

#client own domain
def rh_domain_client(domain):
    print "domain = ", domain
    try:
        client_name = userdomain_dict[domain]
        return client_name
    except KeyError:
        return None

if __name__ == '__main__':
    server = SimpleJSONRPCServer(('0.0.0.0',6565 ))
    server.register_function(rh_auth)
    server.register_function(usage_add)
    server.register_function(status)
    server.register_function(rh_domain_client)
    server.serve_forever()
import hashlib

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

#dictionary of user-password
userpass_dict = {
    "iwanbk":"iwanbk",
    "ibk":"ibk",
    "paijo":"paijo",
}

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

def usage_add(username, trf_req, trf_rsp):
    print "---usage add"
    print "username = ", username
    print "trf_req = ", trf_req
    print "trf_rsp = ", trf_rsp
    return True

if __name__ == '__main__':
    server = SimpleJSONRPCServer(('0.0.0.0',6565 ))
    server.register_function(rh_auth)
    server.register_function(usage_add)
    server.serve_forever()
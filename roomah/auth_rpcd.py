from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

RES_OK = 1
RES_UNKNOWN_ERR = 0
RES_USER_NOT_FOUND = -1
RES_WRONG_PASS = -2
RES_EXCEED_QUOTA = -3

user_dict = {}
user_dict['paijo'] = RES_OK

def auth_client(username, password):
    print "username = ", username
    print "password = ", username
    if username == password:
        return RES_OK
    
    return RES_UNKNOWN_ERR

def status_client(username):
    return user_dict[username]

if __name__ == '__main__':
    server = SimpleJSONRPCServer(('0.0.0.0',4141 ))
    server.register_function(auth_client)
    server.serve_forever()
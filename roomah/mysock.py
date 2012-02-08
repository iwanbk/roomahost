import socket

def connect(sock, addr):
    try:
        sock.connect(addr)
    except socket.error as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return -1, errno
    except socket.herror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return -1, errno
    except socket.gaierror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return -1, errno
    except socket.timeout:
        return -1, errno.ETIMEDOUT
    
    return 0, None

def _send(sock, payload):
    """Write payload to socket."""
    written = 0
    try:
        written = sock.send(payload)
    except socket.error as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return written, errno
    except socket.herror as (errno, err_str):
        print "socket.herror. Errno = ", errno, " err msg = ", err_str
        return written, errno
    except socket.gaierror as (errno, err_str):
        print "socket.gaierror. Errno = ", errno, " err msg = ", err_str
        return written, errno
    except socket.timeout:
        return written, errno.ETIMEDOUT
    
    return written, None

def send(sock, payload):
    return _send(sock, payload)
    
def send_all(sock, data):
    if isinstance(data, unicode):
        data = data.encode()
    err = None
    data_sent = 0
    while data_sent < len(data):
        written, err = _send(sock, data)
        data_sent += written
        if err is not None:
            break
    
    return data_sent, err
        
def recv_str(sock, count):
    """Read count byte from socket."""
    try:
        recv_str = sock.recv(count)
    except socket.error as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.herror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.gaierror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.timeout:
        return None, errno.ETIMEDOUT
    
    return recv, None

def recv(sock, count):
    """Read count byte from socket."""
    try:
        recv_str = sock.recv(count)
    except socket.error as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.herror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.gaierror as (errno, err_str):
        print "socket.error. Errno = ", errno, " err msg = ", err_str
        return None, errno
    except socket.timeout:
        return None, errno.ETIMEDOUT
    
    ba = bytearray(recv_str)
    return ba, None

def recv_safe(sock, count):
    to_read = count
    ba, err = recv(sock, to_read)
    if err != None:
        return None, err
    
    if ba != None and len(ba) == 0:
        return None, err
    
    buf = ba
    
    to_read -= len(ba)
    while to_read > 0:
        ba, err = recv(sock, to_read)
        
        if err != None:
            return None, err
    
        if ba != None and len(ba) == 0:
            return None, err
        buf += ba
        to_read -= len(ba)
        
    return buf, err
def setkeepalives(sock):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,1)
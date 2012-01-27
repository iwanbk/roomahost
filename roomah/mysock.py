import socket

def connect(sock, addr):
    try:
        ret = sock.connect(addr)
    except socket.error as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.herror as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.gaierror as (errno,str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.timeout:
        return -1, errno.ETIMEDOUT
    
    return 0, None

def send(sock, payload):
    """Write payload to socket."""
    try:
        len = sock.send(payload)
    except socket.error as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.herror as (errno, str):
        print "socket.herror. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.gaierror as (errno,str):
        print "socket.gaierror. Errno = ", errno, " err msg = ", str
        return -1, errno
    except socket.timeout:
        return -1, errno.ETIMEDOUT
    
    return len, None
    
def recv_str(sock, count):
    """Read count byte from socket."""
    try:
        str = sock.recv(count)
    except socket.error as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.herror as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.gaierror as (errno,str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.timeout:
        return None, errno.ETIMEDOUT
    
    return str, None

def recv(sock, count):
    """Read count byte from socket."""
    try:
        str = sock.recv(count)
    except socket.error as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.herror as (errno, str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.gaierror as (errno,str):
        print "socket.error. Errno = ", errno, " err msg = ", str
        return None, errno
    except socket.timeout:
        return None, errno.ETIMEDOUT
    
    ba = bytearray(str)
    return ba, None

def recv_safe(sock, count):
    to_read = count
    ba, err = recv(sock, to_read)
    tot = len(ba)
    
    buf = ba
    
    to_read -= len(ba)
    while to_read > 0:
        ba, err = recv(sock, to_read)
        buf += ba
        to_rad -= len(ba)
        
    return buf, err
def setkeepalives(sock):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE,1)
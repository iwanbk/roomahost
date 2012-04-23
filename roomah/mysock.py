"""
My socket wrapper
Copyright(c) Iwan Budi Kusnanto 2012
"""
import socket

def connect(sock, addr):
    """Connect to server."""
    try:
        sock.connect(addr)
    except socket.error as (_, err_str):
        return -1, (socket.error, err_str)
    except socket.herror as (_, err_str):
        return -1, (socket.herror, err_str)
    except socket.gaierror as (_, err_str):
        return -1, (socket.gaierror, err_str)
    except socket.timeout:
        return -1, (socket.timeout, "")
    
    return 0, None

def _send(sock, payload):
    """Send payload to socket."""
    written = 0
    try:
        written = sock.send(payload)
    except socket.error as (_, err_str):
        return written, (socket.error, err_str)
    except socket.herror as (_, err_str):
        return written, (socket.herror, err_str)
    except socket.gaierror as (_, err_str):
        return written, (socket.gaierror, err_str)
    except socket.timeout:
        return written, (socket.timeout, "")
    
    return written, None

def send(sock, payload):
    """Send payload."""
    return _send(sock, payload)
    
def send_all(sock, data):
    """Send all payload."""
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
        the_str = sock.recv(count)
    except socket.error as (_, err_str):
        return None, (socket.error, err_str)
    except socket.herror as (_, err_str):
        return None, (socket.herror, err_str)
    except socket.gaierror as (_, err_str):
        return None, (socket.gaierror, err_str)
    except socket.timeout:
        return None, (socket.timeout, "")
    
    return the_str, None

def recv(sock, count):
    """Read count byte from socket."""
    try:
        recv_str = sock.recv(count)
    except socket.error as (_, err_str):
        return None, (socket.error, err_str)
    except socket.herror as (_, err_str):
        return None, (socket.herror, err_str)
    except socket.gaierror as (_, err_str):
        return None, (socket.gaierror, err_str)
    except socket.timeout:
        return None, (socket.timeout, "")
    
    ba = bytearray(recv_str)
    return ba, None

def recv_safe(sock, count):
    """Recv all data from socket."""
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
    """Set socket to keepalive socket."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
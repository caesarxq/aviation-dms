#!/usr/bin/env python3
"""EICAR INSTREAM test - backend to backup scanner"""
import socket
import struct

def scan_instream(payload, host='10.20.173.120', port=3310):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.sendall(b'zINSTREAM\x00')
    sock.sendall(struct.pack('!I', len(payload)))
    sock.sendall(payload)
    sock.sendall(struct.pack('!I', 0))
    response = b''
    while not response.endswith(b'\x00'):
        chunk = sock.recv(1024)
        if not chunk:
            break
        response += chunk
    sock.close()
    return response.decode().strip()

# Test clean file
clean = b'This is a clean test file for INSTREAM scanning.'
result = scan_instream(clean)
print(f'Clean file: {result}')

# Test EICAR
eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
result = scan_instream(eicar)
print(f'EICAR test: {result}')
import socket, struct

def scan(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(('127.0.0.1', 3310))
    sock.sendall(b'zINSTREAM\x00')
    for offset in range(0, len(payload), 4096):
        chunk = payload[offset:offset+4096]
        sock.sendall(struct.pack('!I', len(chunk)))
        sock.sendall(chunk)
    sock.sendall(struct.pack('!I', 0))
    response = b''
    while not response.endswith(b'\x00'):
        chunk = sock.recv(1024)
        if not chunk:
            break
        response += chunk
    sock.close()
    return response.decode('utf-8', errors='replace').strip()

# Clean file
clean = b'This is a clean test file for clamav verification.'
result = scan(clean)
print(f'Clean file: {result}')

# EICAR test string (should be detected as malware)
eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
result = scan(eicar)
print(f'EICAR test: {result}')

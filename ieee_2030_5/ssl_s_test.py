
import ssl
import socket
import http.server

def RunDefaultContext ():
    hostname = '0.0.0.0'
    port = 7443
    cert_files = '../all_certs.pem'
    server_cert = '../tls/certs/127.0.0.1_7443.crt'
    server_key = '../tls/private/127.0.0.1_7443.pem'
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    #context.load_verify_locations(cafile=cert_files)
    context.load_cert_chain(certfile=server_cert, keyfile=server_key)
    context.check_hostname = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((hostname, port))
        sock.listen()
        print(f"Default Listening on {hostname}:{port}")
        with context.wrap_socket(sock, server_side=True) as ssock:
            conn, addr = ssock.accept()
            print(ssock.version())
            print(f"Connected by {addr}")
            data = conn.recv(1024)
            print(f"Received: {data}")
            conn.close()

def RunCustomContext ():
    hostname = socket.gethostbyname(socket.gethostname())
    port = 7443
    cert_files = '../all_certs.pem'
    server_cert = '../tls/certs/127.0.0.1_7443.crt'
    server_key = '../tls/private/127.0.0.1_7443.pem'
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)#ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_verify_locations(cafile=cert_files)
    context.load_cert_chain(certfile=server_cert, keyfile=server_key)
    context.verify_mode = ssl.CERT_REQUIRED
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((hostname, port))
        sock.listen()
        print(f"Custom Listening on {port}")
        with context.wrap_socket(sock, do_handshake_on_connect=True, server_side=True) as ssock:
            conn, addr = ssock.accept()
            print(conn)
            print(conn.getpeercert(False))
            print(f"Connected by {addr}")
            data = conn.recv(1024)
            print(f"Received: {data[:32]}")
            conn.close()

def RunHttpServer ():
    hostname = '0.0.0.0'
    port = 7443
    server_cert = '../tls/certs/127.0.0.1_7443.crt'
    server_key = '../tls/private/127.0.0.1_7443.pem'
    client_certs = '../client_certs.pem'
    '''
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER) #ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_verify_locations(cafile=client_certs)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=server_cert, keyfile=server_key)
    '''
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=server_cert, keyfile=server_key)
    httpd = http.server.HTTPServer((hostname, port), http.server.SimpleHTTPRequestHandler)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving HTTP on {hostname}:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    try:
        if 0:
            RunHttpServer ()
        elif 0:
            RunDefaultContext ()
        elif 1:
            RunCustomContext ()
    except Exception as e:
        print(e)

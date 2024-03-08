
import os
import time
import socket
import ssl
from http.client import HTTPSConnection

def VerifyDefaultContext():
    if 0:
        hostname = 'www.python.org'
        port = 443
    else:
        hostname = '127.0.0.1'
        #hostname = "34.228.188.193"
        port = 7443
    cert_files = '../all_certs.pem'
    client_cert = '../tls/certs/dev2.crt'
    client_key = '../tls/private/dev2.pem'
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_verify_locations(cafile=cert_files)
    context.check_hostname = False                  # certificate verify failed: IP address mismatch, certificate is not valid for '127.0.0.1'. (_ssl.c:1125)
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            print(ssock)
            data = os.urandom (1024)
            ssock.send(data)
            print(f"Sent: {data}")
            time.sleep(2)

def VerifyCustomCertContext():
    if 0:
        hostname = 'www.python.org'
        port = 443
    else:
        hostname = "10.115.34.61"
        port = 7443
    cert_files = '../all_certs.pem'
    client_cert = '../tls/certs/dev2.crt'
    client_key = '../tls/private/dev2.pem'
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)#ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.load_verify_locations(cafile=cert_files)
    context.load_cert_chain(certfile=client_cert, keyfile=client_key)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False  # certificate verify failed: IP address mismatch, certificate is not valid for '127.0.0.1'. (_ssl.c:1125)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            ssock.connect((hostname, port))
            print(ssock)
            print(ssock.getpeercert(False))
            data = os.urandom(1024)
            ssock.send(data)
            print(f"Sent: {data[:32]}")
            time.sleep(2)

def VerifyServerCert (hostname, port, ca_certs):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    server_cert = ssl.get_server_certificate(addr=(hostname, port), ca_certs=ca_certs)
    print (server_cert)

def VerifyServerCertTest ():
    if 0:
        VerifyServerCert(hostname='www.python.org', port=443, ca_certs='../GlobalSign.crt')  # OK
        # VerifyServerCert (hostname='www.python.org', port=443, ca_certs='../ca.crt')               # XXX
    else:
        #VerifyServerCert(hostname="10.115.34.61", port=7443, ca_certs='../ca.crt') #"34.228.188.193", port=7443, ca_certs='../ca.crt')  # OK
        VerifyServerCert (hostname="52.87.199.211", port=7443, ca_certs='../Somansa.crt')         # OK
        #VerifyServerCert (hostname="34.228.188.193", port=7443, ca_certs='../helpdesk.crt')        # XXX

def ReqServerResource (hostname, port, url, ca_certs, keyfile, certfile):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile='../ca.crt')
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False
    http_conn = HTTPSConnection(host=hostname, port=port, context=context)
    http_conn.set_debuglevel(4)
    headers = {'Connection': 'Keep-Alive', 'Keep-Alive': "max=1000,timeout=30"}
    http_conn.request(method="GET", url=url, body=None, headers=headers)
    response = http_conn.getresponse()
    response_data = response.read().decode("utf-8")
    print(response.headers, response_data)


def ReqServerResourceTest ():
    if 0:
        ReqServerResource(hostname="10.115.34.61", port=7443, url='/dcap', ca_certs='../ca.crt', keyfile='../tls/private/dev2.pem', certfile='../tls/certs/dev2.crt')
        #ReqServerResource(hostname="127.0.0.1", port=7443, url='/', ca_certs='../ca.crt', keyfile='../tls/private/dev2.pem', certfile='../tls/certs/dev2.crt')
    else:
        ReqServerResource(hostname="52.87.199.211", port=7443, url='/dcap', ca_certs='../ca.crt', keyfile='../tls/private/dev2.pem', certfile='../tls/certs/dev2.crt')

if __name__ == "__main__":
    try:
        if 0:
            VerifyDefaultContext ()
        elif 0:
            VerifyCustomCertContext ()
        elif 0:
            VerifyServerCertTest ()
        elif 1:
            ReqServerResourceTest ()
    except Exception as e:
        print(e)

from __future__ import print_function

import os
import socket
import sys
from .compat import urlsplit
from .utils import pack_uwsgi_vars, parse_addr, get_host_from_url


def ask_uwsgi(uwsgi_addr, var, body='', timeout=0, udp=False):
    sock_type = socket.SOCK_DGRAM if udp else socket.SOCK_STREAM
    if isinstance(uwsgi_addr, str) and '/' in uwsgi_addr:
        addr = uwsgi_addr
        s = socket.socket(family=socket.AF_UNIX, type=sock_type)
    else:
        addr = parse_addr(addr=uwsgi_addr)
        s = socket.socket(*socket.getaddrinfo(
            addr[0], addr[1], 0, sock_type)[0][:2])

    if timeout:
        s.settimeout(timeout)

    s.connect(addr)
    s.send(pack_uwsgi_vars(var) + body)
    response = []
    while 1:
        data = s.recv(4096)
        if not data:
            break
        response.append(data)
    s.close()

    def try_decode(b):
        try:
            return b.decode('utf-8')
        except UnicodeDecodeError:
            return b

    response_lines = [
        try_decode(b) for b in
        bytearray(os.linesep.encode()).join(response).splitlines()
    ]

    return response_lines


def curl(uwsgi_addr, url, method='GET', body='', body_binary=b'', timeout=0, headers=(),
         udp=False):
    host, uri = get_host_from_url(url)
    parts_uri = urlsplit(uri)

    if '/' not in uwsgi_addr:
        addr = parse_addr(addr=uwsgi_addr)
        if not host:
            host = addr[0]
        port = addr[1]
    else:
        port = None

    if body_binary:
        body = body_binary
    else:
        body = (body or '').encode('utf-8')

    var = {
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'PATH_INFO': parts_uri.path,
        'REQUEST_METHOD': method.upper(),
        'REQUEST_URI': uri,
        'QUERY_STRING': parts_uri.query,
        'HTTP_HOST': host,
        'CONTENT_LENGTH': str(len(body)),
        # Other varaibles seen in nginx's uwsgi_params file but not explicitly
        # handled anywhere in this file
        # https://github.com/nginx/nginx/blob/master/conf/uwsgi_params
        # DOCUMENT_ROOT
        # REQUEST_SCHEME
        # HTTPS
        # REMOTE_ADDR
        # REMOTE_PORT
    }

    for header in headers or ():
        key, _, value = header.partition(':')
        var['HTTP_' + key.strip().upper().replace('-', '_')] = value.strip()
    if 'HTTP_CONTENT_TYPE' in var.keys():
        var['CONTENT_TYPE'] = var['HTTP_CONTENT_TYPE']
    var['SERVER_NAME'] = var['HTTP_HOST']
    if port:
        var['SERVER_PORT'] = str(port)

    return ask_uwsgi(uwsgi_addr=uwsgi_addr, var=var, body=body,
                     timeout=timeout, udp=udp)



def cli(*args):
    import argparse

    class LoadFile(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            if values.startswith('@'):
                if option_string == '--data' or option_string == '-d':
                    with open(values[1:]) as fh:
                        namespace.data = fh.read()
                elif option_string == '--data-binary':
                    with open(values[1:], 'rb') as fh:
                        namespace.data_binary = fh.read()
            else:
                namespace.data = values

    parser = argparse.ArgumentParser()

    parser.add_argument('uwsgi_addr', nargs=1,
                        help="Remote address of uWSGI server")

    parser.add_argument('url', nargs='?', default='/',
                        help="Request URI optionally containing hostname")

    parser.add_argument('-X', '--method', default='GET',
                        help="Request method. Default: GET")

    parser.add_argument('-H', '--header', action='append', dest='headers',
                        help="Request header. It can be used multiple times")

    parser.add_argument('-d', '--data', action=LoadFile, help="Request body")

    parser.add_argument('--data-binary', action=LoadFile, help="Request body")

    parser.add_argument('-t', '--timeout', default=0.0, type=float,
                        help="Socket timeout")

    parser.add_argument('--udp', action='store_true',
                        help="Use UDP instead of TCP")

    args = parser.parse_args(args or sys.argv[1:])

    response = curl(uwsgi_addr=args.uwsgi_addr[0], method=args.method,
                    url=args.url, body=args.data, body_binary=args.data_binary,
                    timeout=args.timeout, headers=args.headers, udp=args.udp)

    for line in response:
        if isinstance(line, bytearray):
            print(line.decode(errors='ignore'))
        elif sys.version_info < (3, ):
            print(line.decode())
        else:
            print(line)

    status = int(response[0].split(' ', 2)[1])
    return not (200 <= status < 300)


if __name__ == '__main__':
    sys.exit(cli(*sys.argv[1:]))

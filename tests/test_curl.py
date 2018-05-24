from copy import deepcopy
import socket
import unittest
from uwsgi_tools.curl import cli
from tests.utils import server


class CurlTests(unittest.TestCase):
    def test_cli(self):
        with server():
            self.assertFalse(cli('127.0.0.1', 'host.name/'))

    def test_cli_nok(self):
        with server(status=300):
            self.assertTrue(cli('127.0.0.1:3030', '--timeout', '10'))

    def test_file_socket(self):
        fname = '/tmp/unix-socket'

        with server(addr=fname, params=(socket.AF_UNIX, socket.SOCK_STREAM)):
            self.assertFalse(cli(fname))

    def test_headers(self):
        with server(callback=lambda x: self.assertIn(b'localhost', x)):
            self.assertFalse(cli('127.0.0.1:3030', '-H', 'Host: localhost'))

    def test_post(self):
        requests = []

        def request_sniper(x):
            requests.append(deepcopy(x))

        with server(callback=request_sniper):
            self.assertFalse(cli(
                '--method', 'POST',
                '--header', 'Content-Type: application/json',
                r'''--data=\'{"foo":"bar"}\'''',
                '127.0.0.1',
                'host.name/'))

        self.assertIn(b'POST', requests[0])
        # Magic number is the val_size + val
        self.assertIn(b'CONTENT_LENGTH\x02\x0017', requests[0])
        self.assertIn(b'CONTENT_TYPE', requests[0])
        self.assertIn(b'application/json', requests[0])

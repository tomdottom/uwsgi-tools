from copy import deepcopy
import json
import socket
import tempfile
import unittest

from uwsgi_tools.curl import cli
from tests.utils import server


class CurlTests(unittest.TestCase):
    def setUp(self):
        self.datafile = tempfile.NamedTemporaryFile(delete=True)
        with open(self.datafile.name, 'w') as fh:
            json.dump({'foo': 'bar'}, fh)

        self.binary_datafile = tempfile.NamedTemporaryFile(delete=True)
        with open(self.binary_datafile.name, 'wb') as fh:
            fh.write(b'binary-fooooo')

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

    def test_at_prefixed_data(self):
        requests = []

        def request_sniper(x):
            requests.append(deepcopy(x))

        with server(callback=request_sniper):
            self.assertFalse(cli(
                '--method', 'POST',
                '--header', 'Content-Type: application/json',
                '--data', '@{}'.format(self.datafile.name),
                '127.0.0.1',
                'host.name/',
            ))

        self.assertIn(b'POST', requests[0])
        # Magic number is the val_size + val
        self.assertIn(b'CONTENT_LENGTH\x02\x0014', requests[0])
        self.assertIn(b'CONTENT_TYPE', requests[0])
        self.assertIn(b'application/json', requests[0])
        self.assertIn(b'{"foo": "bar"}', requests[0])

    def test_binary_data(self):
        requests = []

        def request_sniper(x):
            requests.append(deepcopy(x))

        with server(callback=request_sniper):
            self.assertFalse(cli(
                '--method', 'POST',
                '--header', 'Content-Type: application/json',
                '--data-binary', '@{}'.format(self.binary_datafile.name),
                '127.0.0.1',
                'host.name/',
            ))

        self.assertIn(b'POST', requests[0])
        # Magic number is the val_size + val
        self.assertIn(b'CONTENT_LENGTH\x02\x0013', requests[0])
        self.assertIn(b'CONTENT_TYPE', requests[0])
        self.assertIn(b'application/json', requests[0])
        self.assertIn(b'binary-fooooo', requests[0])

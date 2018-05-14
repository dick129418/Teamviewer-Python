# -*- coding: utf-8 -*-
import time
import functools
import sys
import json
import subprocess
import queue
import threading
import io

from PIL import Image, ImageChops, ImageGrab
from time import time, sleep

from tornado import gen
from tornado import httpclient
from tornado import httputil
from tornado import ioloop
from tornado import websocket

APPLICATION_JSON = 'application/json'

DEFAULT_CONNECT_TIMEOUT = 30
DEFAULT_REQUEST_TIMEOUT = 30

q_screen = queue.Queue()

def img_to_byte_arr(img):
    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format='PNG')
    return imgByteArr.getvalue()

def get_changed_screen():
    im1 = ImageGrab.grab()
    imgByteArr = img_to_byte_arr(im1)
    q_screen.put(((), imgByteArr))
    
    while 1:
        print('q_screen', q_screen.qsize())
        if q_screen.qsize() > 5:
            sleep(1)
        im2 = ImageGrab.grab()
        diff = ImageChops.difference(im1, im2)
        box = diff.getbbox()
        if not box:
            continue
        img = im2.crop(box)
        imgByteArr = img_to_byte_arr(img)
        q_screen.put((box, imgByteArr))
        im1 = im2
threading._start_new_thread(get_changed_screen, ())


class WebSocketClient(object):
    """Base for web socket clients.
    """

    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2

    def __init__(self, io_loop=None,
                 connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                 request_timeout=DEFAULT_REQUEST_TIMEOUT):

        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self._io_loop = io_loop or ioloop.IOLoop.current()
        self._ws_connection = None
        self._connect_status = self.DISCONNECTED

    def connect(self, url):
        """Connect to the server.
        :param str url: server URL.
        """
        self._connect_status = self.CONNECTING
        headers = httputil.HTTPHeaders({'Content-Type': APPLICATION_JSON})
        request = httpclient.HTTPRequest(url=url,
                                         connect_timeout=self.connect_timeout,
                                         request_timeout=self.request_timeout,
                                         headers=headers)
        ws_conn = websocket.WebSocketClientConnection(self._io_loop, request)
        ws_conn.connect_future.add_done_callback(self._connect_callback)
        return ws_conn

    def _connect_callback(self, future):
        if future.exception() is None:
            self._connect_status = self.CONNECTED
            self._ws_connection = future.result()
            self.on_connection_success()
            self._read_messages()
        else:
            self.close(future.exception())

    def send(self, data, is_bin=False):
        """Send message to the server
        :param str data: message.
        """

        if self._ws_connection:
            if not is_bin:
                self._ws_connection.write_message(json.dumps(data))
            else:
                self._ws_connection.write_message(data, binary=True)

    def close(self, reason=''):
        """Close connection.
        """

        if self._connect_status != self.DISCONNECTED:
            self._connect_status = self.DISCONNECTED
            self._ws_connection and self._ws_connection.close()
            self._ws_connection = None
            self.on_connection_close(reason)

    @gen.coroutine
    def _read_messages(self):
        while True:
            msg = yield self._ws_connection.read_message()
            if msg is None:
                self.close()
                break

            self.on_message(msg)

    def is_connected(self):
        return self._ws_connection is not None

    def on_message(self, msg):
        """This is called when new message is available from the server.
        :param str msg: server message.
        """

        pass

    def on_connection_success(self):
        """This is called on successful connection ot the server.
        """

        pass

    def on_connection_close(self, reason):
        """This is called when server closed the connection.
        """
        pass


class RTCWebSocketClient(WebSocketClient):
    msg = {'type': 'msg', 'from': 'F'}
    task = None
    func = None

    def __init__(self, io_loop=None,
                 connect_timeout=DEFAULT_CONNECT_TIMEOUT,
                 request_timeout=DEFAULT_REQUEST_TIMEOUT):

        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout
        self._io_loop = io_loop or ioloop.IOLoop.current()
        self.ws_url = None
        self.auto_reconnect = False

        super(RTCWebSocketClient, self).__init__(self._io_loop,
                                                 self.connect_timeout,
                                                 self.request_timeout)

    def connect(self, url, auto_reconnect=True, reconnet_interval=3):
        self.ws_url = url
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnet_interval

        conn = super(RTCWebSocketClient, self).connect(self.ws_url)
        conn.connect_future.add_done_callback(self.send_screen)

    def send(self, msg, is_bin=False):
        super(RTCWebSocketClient, self).send(msg, is_bin)

    def on_message(self, msg):
        print('Server: ', msg)

    @gen.coroutine
    def send_screen(self, *args):
        while 1:
            box, img_bin = q_screen.get()
            box_bin = bytes(str(box).encode())
            self.send(b'<-------->'.join([bytes('screen'.encode()), box_bin, img_bin]), is_bin=True)
            print('sent')

    def on_connection_success(self):
        print('Connected!')

    def on_connection_close(self, reason):
        print('Connection closed reason=%s' % (reason,))
        self.reconnect()

    def reconnect(self):
        sys.exit()
        print('reconnect')
        if not self.is_connected() and self.auto_reconnect:
            self._io_loop.call_later(
                self.reconnect_interval,
                super(RTCWebSocketClient, self).connect,
                self.ws_url)


def main():
    io_loop = ioloop.IOLoop.instance()

    client = RTCWebSocketClient(io_loop)
    ws_url = 'ws://127.0.0.1:9095/ws'
    # ws_url = 'ws://192.168.8.158:9095/ws'
    client.connect(ws_url, auto_reconnect=True, reconnet_interval=3)

    try:
        io_loop.start()
    except KeyboardInterrupt:
        client.close()

if __name__ == '__main__':
    main()
import asyncio
import selectors
import socket
import socketserver
import sys
import threading
import time
import struct
import os

PACKET_CODE = {
    "write": 1,
    "read": 2,
    "list": 3,
    "data": 4,
    "ack": 5
}

PACKET_CODE_DICT = {val: key for key, val in PACKET_CODE.items()}
DATA_PACKET_PIECE_LEN = 1500 - 20 - 6  # packet - tcp header - packet header

FILE_DIR = "./Files"
GUEST_TASK_TABLE = {}
GUEST_LIST = []


def gen_file_data(filename: str) -> bytes:
    with open(filename, "rb+") as f:
        length = DATA_PACKET_PIECE_LEN
        while length == DATA_PACKET_PIECE_LEN:
            data = f.read(DATA_PACKET_PIECE_LEN)
            length = len(data)
            print(f"[DEBUG] 生成 {filename} 的包含长度为{length}的文件片段的数据包")
            yield _build_data_packet(data)


def _build_data_packet(data: bytes):
    """
    给定数据流data，返回数据包
    格式 packetCode+length+data
    :param data:嵌入数据
    :return:数据包格式
    """
    length = len(data)
    return struct.pack(f"=1H1I{length}s", PACKET_CODE['data'], len(data), data)


def guest_upload(client: socket.socket, filename):
    """
    将用户添加到用户队列
    将上传任务添加到该用户字典内
    :param client: 客户端连接
    :param filename: 上传文件名
    :return:
    """
    if client in GUEST_LIST:
        task = GUEST_TASK_TABLE[client]
        task["upload"].append(filename)
    else:
        task = {"download": [], "upload": filename}
    GUEST_TASK_TABLE[client] = task


def is_uploading(client, filename):
    """
    查询该用户是否在上传该文件
    :param client: 连接socket
    :param filename: 文件名
    :return:
    """
    task = GUEST_TASK_TABLE.get(client, {})
    file_list = task.get("upload", [])
    return filename in file_list


def is_downloading(client, filename):
    """
    查询该用户是否在下载该文件
    :param client:
    :param filename:
    :return:
    """
    task = GUEST_TASK_TABLE.get(client, {})
    file_list = task.get("download", [])
    return filename in file_list


def packet_handle(client: socket.socket):
    data = client.recv(6)
    code, length = struct.unpack("=1H1I", data)
    print("[DEBUG] 包类型", PACKET_CODE_DICT[code])
    if len(data) != 6:
        raise Exception("客户端释放连接")
    if PACKET_CODE_DICT[code] == "read":
        # get filename
        # read file
        # build packet
        # send
        rawFileName = client.recv(length)
        filename = rawFileName.decode("utf8")
        data = gen_file_data(filename)
        for packet in data:
            client.send(packet)

    if PACKET_CODE_DICT[code] == "write":
        # get filename
        # read file till end
        # ending is a empty file packet
        rawFileName = client.recv(length)
        filename = rawFileName.decode("utf8")
        guest_upload(client, filename)
        pass
    if PACKET_CODE_DICT[code] == "list":
        info = "\n".join([f"{i.name}  {i.stat().st_size}" for i in os.scandir(".")])
        print("[+] DEBUG")
        print(info)
        packet = _build_data_packet(info.encode("utf8"))
        client.send(packet)
        print("[DEBUG] 已发送")
    # gen file list
    if PACKET_CODE_DICT[code] == "data":
        task = GUEST_TASK_TABLE.get(client, {})
        uploadTask = task.get("upload", [])
        if len(uploadTask) != 1:
            raise Exception("上传任务数不为1,len(uploadTask)=%d" % len(uploadTask))
        filename = uploadTask[0]
        data = client.recv(length)
        with open(filename, "ab+") as f:
            f.write(data)


class BlockIOServer:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(60)

    def serve(self, host='127.0.0.1', port=4455):
        self.server.bind((host, port))  # 绑定端口
        self.server.listen(1)  # 监听
        while True:
            client, addr = self.server.accept()  # 等待客户端连接
            print(f"[+] Connection from {addr}")
            self.handle(client)

    def handle(self, client):
        while True:
            try:
                packet_handle(client)
            except Exception as e:
                print(e)
                break


class MultiThreadServer():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(60)

    def serve(self, host='127.0.0.1', port=4455):
        self.server.bind((host, port))  # 绑定端口
        self.server.listen(1000)  # 监听
        while True:
            client, addr = self.server.accept()  # 等待客户端连接
            print(f"[+] Connection from {addr}")
            t = threading.Thread(target=self.handle, args=(client,))
            t.start()

    def handle(self, client):
        while True:
            try:
                packet_handle(client)
            except Exception as e:
                print(e.with_traceback())
                break


class MultiplexingServer:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(60)

    def __init__(self, host='127.0.0.1', port=4455):
        self.server.bind((host, port))
        self.server.listen(100)
        self.server.setblocking(False)

        # 使用默认选择器
        self.selector = selectors.DefaultSelector()
        self.selector.register(fileobj=self.server,
                               events=selectors.EVENT_READ,
                               data=self.on_accept)

    def on_accept(self, sock):
        # 这是给正处于监听状态套接字的handler
        # 负责处理 新连接
        conn, _ = self.server.accept()
        self.selector.register(conn, events=selectors.EVENT_READ, data=self.handle)

    def handle(self, client):
        try:
            packet_handle(client)
        except Exception as e:
            tb = sys.exc_info()[2]
            print(e.with_traceback(tb))

    def serve(self):
        while True:
            events = self.selector.select(timeout=1)
            # For each new event, dispatch to its handler
            for key, mask in events:
                print(key.data, key.fileobj)
                handler = key.data
                handler(key.fileobj)


class AsyncIOServer:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(60)

    def __init__(self, host='127.0.0.1', port=4455):
        self.server.bind((host, port))
        self.server.listen(100)
        self.server.setblocking(False)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # 使用默认选择器
        self.selector = selectors.DefaultSelector()
        self.selector.register(fileobj=self.server,
                               events=selectors.EVENT_READ,
                               data=self.on_accept)

    async def on_accept(self, sock):
        # This is a handler for the server which is now listening, so we
        # know it's ready to accept a new connection.
        conn, _ = self.server.accept()
        self.selector.register(conn, events=selectors.EVENT_READ, data=self.handle)

    async def handle(self, client):
        try:
            packet_handle(client)
        except Exception as e:
            tb = sys.exc_info()[2]
            print(e.with_traceback(tb))

    def serve(self):
        while True:
            events = self.selector.select(timeout=1)
            # For each new event, dispatch to its handler
            for key, mask in events:
                print(key.data, key.fileobj)
                handler = key.data
                asyncio.run(handler(key.fileobj))


if __name__ == "__main__":
    os.chdir(FILE_DIR)
    # 阻塞
    # s1 = BlockIOServer()
    # s1.serve()

    # 多线程
    # s2 = MultiThreadServer()
    # s2.serve()

    # 多路复用
    # s3 = MultiplexingServer()
    # s3.serve()

    # asyncio 库
    s4 = AsyncIOServer()
    s4.serve()

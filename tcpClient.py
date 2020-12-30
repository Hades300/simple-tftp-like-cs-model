import socket
import time
import struct

DATA_PACKET_PIECE_LEN = 1500 - 20 - 6  # packet - tcp header - packet header

PACKET_CODE = {
    "write": 1,
    "read": 2,
    "list": 3,
    "data": 4,
    "ack": 5
}


def _build_rrq_packet(filename: str):
    return struct.pack("=1H1I%ds" % (len(filename.encode("utf8"))), PACKET_CODE["read"], len(filename.encode("utf8")),
                       filename.encode("utf8"))


def _build_wrq_packet(filename: str):
    return struct.pack("=1H1I%ds" % (len(filename.encode("utf8"))), PACKET_CODE["write"], len(filename.encode("utf8")),
                       filename.encode("utf8"))


def _build_lrq_packet():
    return struct.pack("=1H1I", PACKET_CODE["list"],0)


def _build_data_packet(data: bytes):
    """
    给定数据流data，返回数据包
    格式 packetCode+length+data
    :param data:嵌入数据
    :return:数据包格式
    """
    length = len(data)
    return struct.pack(f"=1H1I{length}s", PACKET_CODE['data'], len(data),data)

def gen_file_data(filename: str) -> bytes:
    with open(filename, "rb+") as f:
        length =DATA_PACKET_PIECE_LEN
        while length==DATA_PACKET_PIECE_LEN:
            data = f.read(DATA_PACKET_PIECE_LEN)
            length =len(data)
            print(f"[DEBUG] 生成 {filename} 的包含长度为{length}的文件片段的数据包")
            yield _build_data_packet(data)


class Client:
    host = "localhost"
    port = 4455
    timeout = 30

    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        self.client.settimeout(30)
        self.client.connect((self.host, self.port))

    def upload(self, filename,remotename):
        packet = _build_wrq_packet(remotename)
        self.client.send(packet)
        for packet in gen_file_data(filename):
            self.client.send(packet)
        print(f"[+] file {filename} uploaded")

    def download(self, filename):
        packet = _build_rrq_packet(filename)
        self.client.send(packet)
        with open(filename, "wb") as f:
            length = DATA_PACKET_PIECE_LEN
            while length == DATA_PACKET_PIECE_LEN:
                data = self.client.recv(6)
                _, length = struct.unpack("=1H1I", data)
                fileData = self.client.recv(length)
                print(f"[+] DEBUG 文件 {filename} 收到 {len(fileData)}字节" )
                f.write(fileData)
        print(f"[+] file {filename} downloaded")

    def list(self):
        packet = _build_lrq_packet()
        self.client.send(packet)
        data = self.client.recv(6)
        _, length = struct.unpack("=1H1I", data)
        data = self.client.recv(length)
        info = data.decode("utf8")
        print(info)

    def execute(self, cmd: list):
        if len(cmd) <1:
            raise Exception("缺少命令")
        baseCmd = cmd[0].lower()
        if baseCmd == "read":
            self.download(cmd[1])
        if baseCmd == "write":
            if len(cmd) != 3:
                raise Exception("缺少命令")
            self.upload(cmd[1], cmd[2])
        if baseCmd == "list":
            self.list()

    def loop(self):
        self.connect()
        while True:
            command = input("Guest>").split()
            self.execute(command)


if __name__=="__main__":
    c = Client()
    c.loop()

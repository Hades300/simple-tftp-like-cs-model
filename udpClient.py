import queue
import time
from _socket import *
import os
import threading, struct

# max transfer? unit
MTU = 8192-20-8
# max data length
MDL = MTU -6

PACKET_CODE = {
    "write": 1,
    "read": 2,
    "list": 3,
    "data": 4,
    "ack": 5
}

CMD_CODE = {
    1: "write",
    2: "read",
    3: "list",
    4: "exit"
}


def _build_rrq_packet(filename: str):
    return struct.pack("1H1H%ds" % (len(filename.encode("utf8"))), PACKET_CODE["read"], len(filename.encode("utf8")),
                       filename.encode("utf8"))


def _build_wrq_packet(filename: str):
    return struct.pack("1H1H%ds" % (len(filename.encode("utf8"))), PACKET_CODE["write"], len(filename.encode("utf8")),
                       filename.encode("utf8"))


def _build_lrq_packet():
    return struct.pack("1H", PACKET_CODE["list"])


def _build_ack_packet(id: int):
    return struct.pack("=1H1I", PACKET_CODE["ack"], id)


def _build_data_packet(id: int, data: bytes):
    length = len(data)
    return struct.pack(f"=1H1I{length}s", PACKET_CODE['data'], id, data)


def _build_err_packet(e: Exception):
    return _build_ack_packet(0, repr(e).encode("utf8"))


def download(c: socket, *args):
    if len(args) ==1:
        raise Exception("需提供写入本地的文件名")
    if len(args) != 2:
        raise Exception("参数长度不对劲")
    filename = args[0]
    localfilename = args[1]
    c.send(_build_rrq_packet(filename))
    data = c.recv(MTU)
    packet_code, = struct.unpack("1H", data[:2])
    if packet_code != (PACKET_CODE["ack"]):
        raise Exception("下载请求未接受到对应ACK,接收到：", data.decode("utf8"))
    file_length = 0
    start_time = time.time()
    with open(localfilename, "wb") as f:
        while True:
            data = c.recv(MTU)
            packet_code, = struct.unpack("1H", data[:2])
            if packet_code != (PACKET_CODE["data"]):
                raise Exception("期待一个data包,收到", data.decode("utf8"))
            id, = struct.unpack("=1I", data[2:6])
            file_length+=len(data[6:])
            f.write(data[6:])
            c.send(_build_ack_packet(id))
            if (len(data[6:])) != MDL:
                break
    end_time = time.time()
    print(f"[+] File {filename} Downloaded ,Speed :{file_length/(end_time-start_time)/1024} Kib/s")


def upload(c: socket, *args):
    if len(args) != 2:
        raise Exception("参数长度不对劲")
    filename = args[0]
    serverfilename = args[1]
    print("[DEBUG] SERVERNAME", serverfilename)
    c.send(_build_wrq_packet(serverfilename))
    data = c.recv(MTU)
    packet_code, = struct.unpack("1H", data[:2])
    if packet_code != (PACKET_CODE["ack"]):
        raise Exception("下载请求未接受到对应ACK,接收到：", data.decode("utf8"))
    if not os.path.exists(filename):
        raise Exception(f"文件{filename}不存在")
    file_length = 0
    start_time = time.time()
    with open(filename, "rb") as f:
        id = 1
        while True:
            # 先不考虑最后一部分就刚好是506的情况
            content = f.read(MDL)
            file_length+=len(content)
            if len(content) < MDL:
                # file end
                packet = _build_data_packet(id, content)
                c.send(packet)
                break
            else:
                packet = _build_data_packet(id, content)
                c.send(packet)
                # 此处开始 超时 计算
                # 阻塞直到获取 ack
                while True:
                    def warn():
                        raise Exception("超时")

                    t = threading.Timer(1, function=warn)
                    t.start()
                    data = c.recv(MTU)
                    packet_code, = struct.unpack("H", data[:2])
                    if packet_code == PACKET_CODE["ack"]:
                        t.cancel()
                        break
                    else:
                        raise Exception("期望是一个ACK 但不是")
                    # 超时重传
                    # c.send(packet)
                id += 1
    end_time = time.time()
    print(f"[+] {filename} uploaded , Speed {file_length/(end_time-start_time)/1024} Kib/s")
    pass


def get_list(c: socket):
    c.send(_build_lrq_packet())
    data = c.recv(MTU)
    packet_code, = struct.unpack("1H", data[:2])
    if packet_code != (PACKET_CODE["ack"]):
        raise Exception("查看文件列表请求未接受到对应ACK,接收到：", data.decode("utf8"))
    content = b""
    while True:
        data = c.recv(MTU)
        packet_code, = struct.unpack("1H", data[:2])
        if packet_code != (PACKET_CODE["data"]):
            raise Exception("期待一个data包,收到", data.decode("utf8"))
        content += data[6:]
        if (len(data[6:])) != MDL:
            break
    print("[+] File List ⤵️")
    print(content.decode("utf8"))


def get_input():
    text = input("Hades300 >> :").split()
    while text[0].lower() not in CMD_CODE.values():
        print("[+] Unsupported cmd %s" % text)
        text = input("Hades300 >> :").split()
    return text


def connect(addr):
    c = socket(AF_INET, SOCK_DGRAM)
    c.connect(addr)
    cmd = get_input()
    if len(cmd) == 1 and cmd[0].lower() == "exit":
        print("[+] Exiting... Bye~")
        c.close()
    if cmd[0].lower() == "read":
        print("[+] Downloading...")
        download(c, *cmd[1:])
    if cmd[0].lower() == "write":
        print("[+] Uploading...")
        upload(c, *cmd[1:])
    if cmd[0].lower() == "list":
        get_list(c)


if __name__ == "__main__":
    addr = ("localhost", 8081)
    while True:
        connect(addr)

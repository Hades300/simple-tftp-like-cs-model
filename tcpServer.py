import socket
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
            # try:
            packet_handle(client)
            # except Exception as e:
            #     print(e)
            #     break


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

# class multiPlexingIOServer:
#     server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     server.settimeout(60)
#
#     def serve(self, host='127.0.0.1', port=4455):
#         self.server.bind((host, port))  # 绑定端口
#         self.server.listen(1000)  # 监听






if __name__ == "__main__":
    os.chdir(FILE_DIR)
    # s1 = BlockIOServer()
    # s1.serve()
    s2 = MultiThreadServer()
    s2.serve()

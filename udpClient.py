import queue
from _socket import *
import time
import threading,struct

PACKET_CODE ={
    "write":1,
    "read":2,
    "list":3,
    "data":4,
    "ack":5
}

CMD_CODE = {
    1:"write",
    2:"read",
    3:"list",
    4:"exit"
}


def _build_rrq_packet(filename:str):
    return struct.pack("1H1H%ds"%(len(filename)),PACKET_CODE["read"],len(filename.encode("utf8")),filename.encode("utf8"))

def _build_wrq_packet(filename:str):
    return struct.pack("1H1H%ds" % (len(filename)), PACKET_CODE["write"], len(filename.encode("utf8")), filename.encode("utf8"))

def _build_ack_packet(id:int):
    return struct.pack("=1H1I",PACKET_CODE["ack"],id)

def _build_data_packet(id:int,data:bytes):
    length = len(data)
    return struct.pack(f"=1H1I{length}s",PACKET_CODE['data'],id,data)


def _build_err_packet(e:Exception):
    return _build_ack_packet(0,repr(e).encode("utf8"))

def download(c:socket,*args):
    if len(args)!=1:
        raise Exception("参数长度不对劲")
    filename = args[0]
    c.send(_build_rrq_packet(filename))
    data = c.recv(512)
    packet_code, = struct.unpack("1H", data[:2])
    if packet_code != (PACKET_CODE["ack"]):
        raise Exception("下载请求未接受到对应ACK,接收到：",data.decode("utf8"))
    with open(filename,"wb") as f:
        while True:
            data = c.recv(512)
            packet_code, = struct.unpack("1H",data[:2])
            if packet_code!=(PACKET_CODE["data"]):
                raise Exception("期待一个data包,收到",data.decode("utf8"))
            id, = struct.unpack("=1I",data[2:6])
            f.write(data[6:])
            c.send(_build_ack_packet(id))
            if (len(data[6:]))!=506:
                break
    print(f"[+] File {filename} Downloaded")





def upload(c:socket,*args):
    if len(args)!=2:
        raise Exception("参数长度不对劲")
    filename = args[0]
    serverfilename = args[1]
    c.send(_build_wrq_packet(serverfilename))
    data = c.recv(512)
    packet_code, = struct.unpack("1H", data[:2])
    if packet_code != (PACKET_CODE["ack"]):
        raise Exception("下载请求未接受到对应ACK,接收到：",data.decode("utf8"))
    with open(filename, "rb") as f:
        id = 1
        while True:
            # 先不考虑最后一部分就刚好是506的情况
            content = f.read(506)
            if len(content)<506:
                # file end
                packet = _build_data_packet(id, content)
                c.send(packet)
                break
            else:
                packet = _build_data_packet(id,content)
                c.send(packet)
                # 此处开始 超时 计算
                # 阻塞直到获取 ack
                while True:
                    def warn():
                        raise Exception("超时")
                    t= threading.Timer(1,function=warn)
                    t.start()
                    data = c.recv(512)
                    packet_code, = struct.unpack("H",data[:2])
                    if packet_code == PACKET_CODE["ack"]:
                        t.cancel()
                        break
                    else:
                        raise Exception("期望是一个ACK 但不是")
                    # 超时重传
                    # c.send(packet)
                id +=1
    print(f"[+] {filename} uploaded")
    pass


def get_input():
    text = input("Hades300 >> :").split()
    while text[0].lower() not in CMD_CODE.values():
        print("[+] Unsupported cmd %s"%text)
        text = input("Hades300 >> :").split()
    return text

def connect(addr):
    c = socket(AF_INET,SOCK_DGRAM)
    c.connect(addr)
    cmd = get_input()
    print("[DEBUG]",cmd)
    if len(cmd)==1 and cmd[0].lower()=="exit":
        print("[+] Exiting... Bye~")
        c.close()
    if cmd[0].lower()=="read":
        print("[+] Downloading...")
        download(c,*cmd[1:])
    if cmd[0].lower() == "write":
        print("[+] Uploading...")
        upload(c,*cmd[1:])


if __name__=="__main__":
    addr = ("localhost",8081)
    connect(addr)



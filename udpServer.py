import socketserver
import struct,threading
import time
import socket,queue
import typing
import os

FILE_DIR = "Files"
FILE_LIST = []

GUEST_LIST = []
GUEST_ACK = {}
GUEST_UPLOADING = {}

TIME_OUT = 2

def guest_add(host:(str,int)):
    GUEST_LIST.append(host)
    GUEST_ACK[host] = queue.Queue(1)

def guest_del(host:(str,int)):
    GUEST_LIST.remove(host)
    del GUEST_ACK[host]

def guest_exist(host:(str,int)):
    try:
        GUEST_LIST.index(host)
        return True
    except:
        return False

def mark_acked(host:(str,int),id:int):
    GUEST_ACK[host].put(id)

def mark_timeout(host:(str,int)):
    GUEST_ACK[host].put(False)


def is_acked(host,id):
    if not guest_exist(host):
        return False
    t= threading.Timer(1,function=mark_timeout,args=(host,))
    t.start()
    res = GUEST_ACK[host].get()
    if res == id:
        t.cancel()
        return True
    else:
        return False


def on_file_piece_uploading(client: (socket.socket, (str, int)),data:bytes):
    sock,addr = client
    packet_code, = struct.unpack("=H",data[:2])
    # 若得到的是wrq
    if packet_code==PACKET_CODE["write"]:
        file_name_length ,= struct.unpack("=H",data[2:4])
        print("[length]",len(data[4:]))
        filename,= struct.unpack(f"{file_name_length}s",data[4:])
        filename = filename.decode("utf8")
        GUEST_UPLOADING[addr] = filename
        sock.sendto(_build_ack_packet(0), addr)
        return
    # 不是wrq的话只能是data包
    if addr not in GUEST_UPLOADING.keys():
        raise Exception("当前无正在上传的文件")
    id , = struct.unpack("1I",data[2:6])
    sock.sendto(_build_ack_packet(id),addr)
    content = data[6:]
    filename= GUEST_UPLOADING[addr]
    if len(content)!=(512-6):
        print(f"[+] File {GUEST_UPLOADING[addr]} uploaded")
        del GUEST_UPLOADING[addr]
    else:
        filename = os.path.join(FILE_DIR,filename)
        with open(filename,"ab") as f:
            f.write(content)
    pass



# single thread downloading
def download(client: (socket.socket, (str, int)), filename: str):
    sock, addr = client
    guest_add(addr)
    if filename not in FILE_LIST:
        raise Exception(f"{filename} Not Exists,We have {FILE_LIST}")
    filename = os.path.join(FILE_DIR,filename)
    sock.sendto(_build_ack_packet(0),addr)
    with open(filename, "rb") as f:
        id = 1
        while True:
            # 先不考虑最后一部分就刚好是506的情况
            content = f.read(506)
            if len(content)<506:
                # file end
                packet = _build_data_packet(id, content)
                sock.sendto(packet, addr)
                break
            else:
                packet = _build_data_packet(id,content)
                sock.sendto(packet,addr)
                # 此处开始 超时 计算
                # 阻塞直到获取 ack
                while is_acked(addr,id)==False:
                    # 超时重传
                    sock.sendto(packet, addr)
                id +=1
    guest_del(addr)
    pass

def list_files(client: (socket.socket, (str, int))):
    sock,addr = client
    sock.sendto(_build_ack_packet(0),addr)
    info = "\n".join([f"{i.name}  {i.stat().st_size}" for i in os.scandir(FILE_DIR)])
    data = info.encode("utf8")
    part = data[:506]
    id =1
    # 默认非满506 为结尾
    while True:
        if len(part)==506:
            sock.sendto(_build_data_packet(id,part),addr)
        else:
            sock.sendto(_build_data_packet(id, part), addr)
            break
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
    3:"list"
}


def parse_packet(data:bytes):

    pass



def err_hook(request: (socket.socket, (str, int)), e: Exception):
    sock,addr = request
    sock.sendto(repr(e).encode("utf8"),addr)

def _build_ack_packet(id:int):
    return struct.pack("=1H1I",PACKET_CODE["ack"],id)

def _build_data_packet(id:int,data:bytes):
    print("[DEBUG] Build %d data Packet"%id)
    length = len(data)
    return struct.pack(f"=1H1I{length}s",PACKET_CODE['data'],id,data)

def _build_err_packet(e:Exception):
    return _build_ack_packet(0,repr(e).encode("utf8"))




def init():
    global FILE_LIST
    res = os.path.exists(FILE_DIR)
    if not res:
        os.mkdir(FILE_DIR)
    FILE_LIST = [i.name for i in os.scandir(FILE_DIR) ]
    print(f"[+] Init FILE_DIR {FILE_DIR}")
    print(f"[+] Init FILE_LIST {FILE_LIST}")

class MyUdpHandler(socketserver.BaseRequestHandler):
    def setup(self) -> None:
        init()
    def handle(self):
        data, sock = self.request
        # try:
        packet_code, = struct.unpack("H",data[:2])
        if packet_code not in PACKET_CODE.values():
            raise Exception("接受到代码  %s命令不存在"%(type(packet_code)),PACKET_CODE.values())
        if packet_code == PACKET_CODE["read"]:
            file_name_length, = struct.unpack("H",data[2:4])
            filename, = struct.unpack("%ds"%file_name_length,data[4:4+file_name_length])
            filename = filename.decode("utf8")
            t = threading.Thread(target=download,args=((sock,self.client_address),filename))
            t.start()
        if packet_code == PACKET_CODE["ack"]:
            id, = struct.unpack("I",data[2:6])
            mark_acked(self.client_address,id)
            print("[ACKED] %d"%id)
        if packet_code == PACKET_CODE["write"] or packet_code == PACKET_CODE["data"]:
            on_file_piece_uploading((sock,self.client_address),data)
        if packet_code == PACKET_CODE["list"]:
            print("[DEBUG] LIST")
            list_files((sock,self.client_address))
        # except Exception as e:
        #     err_hook((sock,self.client_address),e)

if __name__ == '__main__':
    server = socketserver.ThreadingUDPServer(('127.0.0.1', 8081), MyUdpHandler)
    server.serve_forever(poll_interval=0.01)

# TFTP-Like File Transfer Tool(python implemented)

## 使用
```bash
python3 udpClient.py
```
```bash
python3 tcpClient.py
```
```
list
```
```
read [remote-file-name] [local-file-name]
```
```
write [local-file-name] [remote-file-name]
```

## UDP设计考虑

-[X] 实现了超时重传
-[X] 实现了数据包确认(ack)
-[X] 数据分片大小可修改（是网络情况而定）
-[X] 服务端本身使用多线程+多路复用


### 最长数据报长度

选为512原因如下：

> 鉴于Internet上的标准MTU值为576字节,所以我建议在进行Internet的UDP编程时.
最好将UDP的数据长度控件在548字节(576-8-20)以内.

其实主要目的是为了避免IP层的分片，TCP存在分段，所以一般不会进行IP层的分片。
- 对IP分片的数据报来说，即使只丢失一片数据也要重新传整个数据报
- TCP自己实现了超时重传
- UDP没有这个
- 可以自己在应用层实现重传，但是局域网几乎用不上，公网...(无论如何我还是写了重传，但是写死了512)

## Server Side
起了一个Multi-thread的UDP服务器，也就是对于将请求放在不同的线程内处理。

### 优化
### 参数
酌情修改
- 限制服务端IO的关键因素
    - 平台导致的selector选择（默认优先选择poll、其次select)
    - 轮询时间间隔（修改server.serve_forever(poll_interval=**xxxx**)）
- 限制传输速度的因素
    - 单个包大小，有待测试的是 不考虑最小分片下的局域网从传输 将512调至 1472 =（1500-20-8）
    - 夸张一点，不考虑分片，8164 =（8192-20-8） （选 8192是因为大部分系统都默认提供了可读写大于 8192 字节的 UDP 数据报。

### 测试
局域网
- MTU = 512       Speed = 1066 Kib/s
- MTU = 1500-20-8 Speed = 3153 Kib/s
- MTU = 8192-20-8 Speed = 17785 Kib/s

公网 待测试

### 设计
可以自行设计
- 客户端提升下载速度的方法
    - 多线程下载、（当然也需要修改服务端，来支持文件片段下载）
- 客户端提升上传速度的方法
    - 依旧是多线程
    - 客户端需要主动释放文件结束的信号
    - 这次服务端不用（因为原来用on_file_piece_uploading的想法写的）
## Client Side
简单的客户端

## 数据报交换流程

只介绍了下载
- CLIENT ---(READ REQ)---> Server (filename included)
- CLIENT <--(ACK     )--- Server
- CLIENT <--(DATA    )--- Server
- CLIENT ---(ACK     )--> Server
- CLIENT <--(DATA    )--- Server
- CLIENT ---(ACK     )--> Server
- ...
- CLIENT <--(DATA    )--- Server(最后一个不满长的Data 标志着结束)

万一最后一个刚好是满长的呢？TFTP中会发送一个0 bytes Payload的Data Packet来标志下载的结束。我太懒了没写。


## TCP设计考虑

协议本身实现了可靠传输，因此没有ack机制。

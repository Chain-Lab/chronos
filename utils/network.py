import struct


class TCPConnect(object):
    @staticmethod
    def send_msg(sock, msg: str):
        msg = struct.pack('>I', len(msg)) + msg.encode()
        sock.sendall(msg)

    @staticmethod
    def recv_msg(sock):
        raw_msglen = TCPConnect.recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        return TCPConnect.recvall(sock, msglen)

    @staticmethod
    def recvall(sock, n):
        """
        接收所有的n bytes长度的数据
        :param sock: 已建立的sock连接
        :param n: 待接收数据的长度
        :return: 接收的数据
        """
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return b""
            data.extend(packet)
        return data


# class UDPConnect(object):
#     @staticmethod
#     def send_msg(sock, addr, msg: str):
#         msg = struct.pack('>I', len(msg)) + msg.encode()
#         sock.sendto(addr, msg)
#
#     @staticmethod
#     def recv_msg():
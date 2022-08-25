import dataclasses
import errno
import random
import select
import socket
import struct
import time
import typing as t


ICMP_ECHO_HDR = "!BBHHH"


def checksum(b: bytes) -> int:
    """Do the internet checksum"""
    check = 0
    for i in range(0, len(b), 2):
        val = (b[i] << 8) + b[i + 1]
        check += val
    return (check & 0xFFFF) + (check >> 16)


def make_echo_request(ident: int, seqno: int) -> bytes:
    unsummed = struct.pack(ICMP_ECHO_HDR, 8, 0, 0, ident, seqno)
    check = checksum(unsummed)
    return struct.pack(ICMP_ECHO_HDR, 8, 0, check, ident, seqno)


@dataclasses.dataclass
class PingResult:

    addr: str
    replied: bool
    time_ms: t.Optional[float]


class Pinger:
    def __init__(self, addr: str):
        self.sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_ICMP,
        )
        self.addr = addr
        self.ident = random.randrange(0, 0xFFFF)
        self.seqno = 1

    def ping(self, timeout: float = 1.0):
        this_seq = self.seqno
        self.seqno = (self.seqno + 1) % 0x10000
        data = make_echo_request(self.ident, this_seq)
        start = time.time()
        try:
            self.sock.sendto(data, (self.addr, 0))
        except OSError as exc:
            if exc.errno == errno.ENETUNREACH:
                return PingResult(self.addr, False, None)
            raise
        fd = self.sock.fileno()
        try:
            r, _, e = select.select((fd,), (), (fd,), timeout)
        except TimeoutError:
            return PingResult(self.addr, False, None)
        duration = time.time() - start
        if e:
            raise Exception("error!")
        data, addr = self.sock.recvfrom(4096)
        assert addr[0] == self.addr
        rtup = struct.unpack(ICMP_ECHO_HDR, data)
        assert rtup[4] == this_seq
        return PingResult(self.addr, True, duration * 1000)

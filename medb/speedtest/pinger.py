import dataclasses
import errno
import ipaddress
import random
import select
import socket
import struct
import time
import typing as t

ICMP_ECHO_HDR = "!BBHHH"
ECHO_V4 = 8
ECHO_V6 = 128
ECHO_DATA = b"Stephen was here.\nhttps://brennan.io\npinging since 2022!"
assert len(ECHO_DATA) == 56


def make_echo_request(
    ident: int, seqno: int, v6: bool = False, data: t.Optional[bytes] = None
) -> bytes:
    if data is None:
        # It seems that some data is necessary for some ping implementations to
        # respond. The ping included with iputils sends 56 bytes of data (after
        # the 8-byte ICMP header, making 64 bytes total). We will default to
        # that here, but not make the data anything particularly special.
        data = ECHO_DATA
    type_ = ECHO_V6 if v6 else ECHO_V4
    return struct.pack(ICMP_ECHO_HDR, type_, 0, 0, ident, seqno) + data


@dataclasses.dataclass
class PingResult:

    addr: t.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
    replied: bool
    time_ms: t.Optional[float]


class Pinger:
    def __init__(self, addr: str):
        self.addr = ipaddress.ip_address(addr)
        self.v6 = self.addr.version == 6
        self.sock = socket.socket(
            socket.AF_INET6 if self.v6 else socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_ICMPV6 if self.v6 else socket.IPPROTO_ICMP,
        )
        self.ident = random.randrange(0, 0xFFFF)
        self.seqno = 1

    def ping(self, timeout: float = 1.0, data: t.Optional[bytes] = None):
        this_seq = self.seqno
        self.seqno = (self.seqno + 1) % 0x10000
        data = make_echo_request(self.ident, this_seq, self.v6, data)
        start = time.time()
        try:
            ret = self.sock.sendto(data, (str(self.addr), 0))
            print(ret)
        except OSError as exc:
            print("ERR")
            if exc.errno == errno.ENETUNREACH:
                return PingResult(self.addr, False, None)
            raise
        fd = self.sock.fileno()
        r, _, e = select.select((fd,), (), (fd,), timeout)
        if e:
            raise Exception("error!")
        if not r:
            return PingResult(self.addr, False, None)
        duration = time.time() - start
        data, addr = self.sock.recvfrom(4096)
        parsed_addr = ipaddress.ip_address(addr[0])
        assert parsed_addr == self.addr
        rtup = struct.unpack(ICMP_ECHO_HDR, data[:8])
        assert rtup[4] == this_seq
        return PingResult(self.addr, True, duration * 1000)

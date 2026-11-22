import errno
import socket
import ctypes

for label, make_socket in (
    ("UDP", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)),
    ("TCP", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM)),
    ("TCP_IPV6", lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM)),
    ("UNIX", lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)),
    ("NETLINK", lambda: socket.socket(socket.AF_NETLINK, socket.SOCK_RAW)),
    ("SOCKETPAIR", lambda: socket.socketpair()),
):
    try:
        sock = make_socket()
    except OSError as exc:
        print(f"{label}=denied errno={exc.errno} expected={errno.EPERM}")
    else:
        print(f"{label}=ALLOWED")
        if isinstance(sock, tuple):
            for item in sock:
                item.close()
        else:
            sock.close()

libc = ctypes.CDLL(None, use_errno=True)
result = libc.syscall(53, 1, 1, 0, (ctypes.c_int * 2)())
print(f"SYSCALL_SOCKETPAIR={'denied' if result == -1 and ctypes.get_errno() == errno.EPERM else 'ALLOWED'} errno={ctypes.get_errno()}")

for host, port in (("1.1.1.1", 443), ("127.0.0.1", 8001), ("127.0.0.1", 8002),
                   ("127.0.0.1", 8004), ("127.0.0.1", 4000), ("127.0.0.1", 8010)):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((host, port))
    except OSError as exc:
        print(f"TCP_{host}_{port}=denied errno={exc.errno}")
    else:
        print(f"TCP_{host}_{port}=ALLOWED")
        sock.close()

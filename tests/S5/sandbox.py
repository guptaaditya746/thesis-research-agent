#!/usr/bin/env python3
"""Apply a Landlock policy, then exec one bash command."""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import sys


SYS_CREATE_RULESET = 444
SYS_ADD_RULE = 445
SYS_RESTRICT_SELF = 446
CREATE_RULESET_VERSION = 1
RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
SECCOMP_RET_KILL_PROCESS = 0x80000000
SECCOMP_RET_ALLOW = 0x7fff0000
SECCOMP_RET_ERRNO = 0x00050000
AUDIT_ARCH_X86_64 = 0xC000003E
NR_SOCKET = 41
NR_SOCKETPAIR = 53
AF_UNIX = 1
AF_INET = 2
AF_INET6 = 10
AF_NETLINK = 16


class SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(SockFilter))]


def install_socket_seccomp(libc: ctypes.CDLL) -> None:
    # Classic BPF: verify x86_64, reject socket(AF_INET/6/UNIX/NETLINK) and
    # socketpair, and allow all other syscalls. Inherited descriptors remain usable.
    instructions = [
        (0x20, 0, 0, 4),                         # LD W ABS seccomp_data.arch
        (0x15, 1, 0, AUDIT_ARCH_X86_64),         # JEQ arch, skip kill if matched
        (0x06, 0, 0, SECCOMP_RET_KILL_PROCESS),
        (0x20, 0, 0, 0),                         # LD W ABS seccomp_data.nr
        (0x15, 12, 0, NR_SOCKETPAIR),            # socketpair -> EPERM
        (0x15, 1, 0, NR_SOCKET),                 # socket -> family checks
        (0x06, 0, 0, SECCOMP_RET_ALLOW),
        (0x20, 0, 0, 16),                        # LD W ABS seccomp_data.args[0]
        (0x15, 0, 1, AF_INET),
        (0x06, 0, 0, SECCOMP_RET_ERRNO | 1),
        (0x15, 0, 1, AF_INET6),
        (0x06, 0, 0, SECCOMP_RET_ERRNO | 1),
        (0x15, 0, 1, AF_UNIX),
        (0x06, 0, 0, SECCOMP_RET_ERRNO | 1),
        (0x15, 0, 1, AF_NETLINK),
        (0x06, 0, 0, SECCOMP_RET_ERRNO | 1),
        (0x06, 0, 0, SECCOMP_RET_ALLOW),
        (0x06, 0, 0, SECCOMP_RET_ERRNO | 1),
    ]
    filters = (SockFilter * len(instructions))(*(SockFilter(*item) for item in instructions))
    program = SockFprog(len(instructions), filters)
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(program), 0, 0) < 0:
        fail_syscall("prctl(PR_SET_SECCOMP)")

FS_EXECUTE = 1 << 0
FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
FS_REMOVE_DIR = 1 << 4
FS_REMOVE_FILE = 1 << 5
FS_MAKE_CHAR = 1 << 6
FS_MAKE_DIR = 1 << 7
FS_MAKE_REG = 1 << 8
FS_MAKE_SOCK = 1 << 9
FS_MAKE_FIFO = 1 << 10
FS_MAKE_BLOCK = 1 << 11
FS_MAKE_SYM = 1 << 12
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14
FS_IOCTL_DEV = 1 << 15
NET_BIND_TCP = 1 << 0
NET_CONNECT_TCP = 1 << 1
SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
SCOPE_SIGNAL = 1 << 1


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _layout_ = "ms"
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64),
                ("parent_fd", ctypes.c_int32)]


def fail_syscall(name: str) -> None:
    err = ctypes.get_errno()
    raise OSError(err, f"{name}: {os.strerror(err)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readonly", action="append", default=[])
    parser.add_argument("--writable", action="append", default=[])
    parser.add_argument("--writeonly", action="append", default=[])
    parser.add_argument("--workdir")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("supply a command after --")
    workdir = args.workdir or (args.writable[0] if args.writable else None)
    if workdir is None:
        parser.error("supply --workdir or at least one --writable directory")
    if platform.machine() != "x86_64":
        raise SystemExit("This wrapper currently uses x86_64 Landlock syscall numbers")

    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(SYS_CREATE_RULESET, None, ctypes.c_size_t(0),
                       ctypes.c_uint32(CREATE_RULESET_VERSION))
    if abi < 0:
        fail_syscall("landlock_create_ruleset(VERSION)")

    handled_fs = (1 << 13) - 1
    if abi >= 2:
        handled_fs |= FS_REFER
    if abi >= 3:
        handled_fs |= FS_TRUNCATE
    if abi >= 5:
        handled_fs |= FS_IOCTL_DEV
    handled_net = (NET_BIND_TCP | NET_CONNECT_TCP) if abi >= 4 else 0
    scoped = (SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL) if abi >= 6 else 0
    attr = RulesetAttr(handled_fs, handled_net, scoped)
    ruleset_fd = libc.syscall(SYS_CREATE_RULESET, ctypes.byref(attr),
                              ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint32(0))
    if ruleset_fd < 0:
        fail_syscall("landlock_create_ruleset")

    readonly_rights = FS_EXECUTE | FS_READ_FILE | FS_READ_DIR
    writable_rights = handled_fs
    open_path = getattr(os, "O_PATH", os.O_RDONLY) | os.O_CLOEXEC
    try:
        path_rules = ([(p, readonly_rights) for p in args.readonly]
                      + [(p, writable_rights) for p in args.writable]
                      + [(p, FS_WRITE_FILE) for p in args.writeonly])
        for path, rights in path_rules:
            fd = os.open(os.path.realpath(path), open_path)
            try:
                rule = PathBeneathAttr(rights, fd)
                if libc.syscall(SYS_ADD_RULE, ruleset_fd,
                                ctypes.c_int(RULE_PATH_BENEATH),
                                ctypes.byref(rule), ctypes.c_uint32(0)) < 0:
                    fail_syscall(f"landlock_add_rule({path})")
            finally:
                os.close(fd)

        os.chdir(os.path.realpath(workdir))
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0:
            fail_syscall("prctl(PR_SET_NO_NEW_PRIVS)")
        install_socket_seccomp(libc)
        if libc.syscall(SYS_RESTRICT_SELF, ctypes.c_int(ruleset_fd),
                        ctypes.c_uint32(0)) < 0:
            fail_syscall("landlock_restrict_self")
    finally:
        os.close(ruleset_fd)

    os.execvp(command[0], command)
    return 127


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f"sandbox: {exc}", file=sys.stderr)
        raise SystemExit(125)

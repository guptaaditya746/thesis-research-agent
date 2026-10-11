#!/usr/bin/env python3
"""Sandbox wrapper for one agent command (row 1.8; ported from tests/S5/sandbox.py and run_sandbox.py).

Two halves, standard library only, so the wrapper also runs on the agent-venv Python:

- `main()` is the wrapper itself. It runs as the command's first process, inside a fresh session.
  In mode `landlock` it applies a Landlock ruleset (read-only system dirs, corpus, toolchain and
  agent code; one writable scratch dir) and the x86_64 seccomp filter that refuses new IP, Unix
  and netlink sockets and socketpair(); an inherited CLAIM_FD stays usable. In mode `unsandboxed`
  it applies nothing: that mode exists for tests and machines without Landlock, and every run
  records in config.json which mode ran. In both modes it then runs
      bash -c 'ulimit -v <KiB> || exit 125; exec bash -c "<command>"'
  in its own process group and waits at most the timeout (120 s), then stops that group and
  exits 124 like `timeout -k 5`. So the 2 GB address-space limit and the timeout are both set
  here, in the wrapper.

- `run_command()` is the harness side (POSIX): starts the wrapper in its own session with the
  claim descriptor passed through, collects stdout and stderr as one byte stream, and removes any
  process left in the session afterwards (SIGTERM, then SIGKILL).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

MODES = ("landlock", "unsandboxed")
TIMEOUT_EXIT = 124  # what `timeout` returns; the harness uses it too when its own guard fires

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

FS_EXECUTE = 1 << 0
FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14
FS_IOCTL_DEV = 1 << 15
NET_BIND_TCP = 1 << 0
NET_CONNECT_TCP = 1 << 1
SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
SCOPE_SIGNAL = 1 << 1


class SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]


class SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(SockFilter))]


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _layout_ = "ms"
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def _fail(name: str) -> None:
    err = ctypes.get_errno()
    raise OSError(err, f"{name}: {os.strerror(err)}")


def landlock_abi() -> int | None:
    """The kernel's Landlock ABI version, or None where Landlock (or x86_64 Linux) is missing."""
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return None
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(SYS_CREATE_RULESET, None, ctypes.c_size_t(0), ctypes.c_uint32(CREATE_RULESET_VERSION))
    return abi if abi > 0 else None


def _install_socket_seccomp(libc: ctypes.CDLL) -> None:
    # Classic BPF, as in S5: check x86_64, refuse socket(AF_INET/6/UNIX/NETLINK) and socketpair
    # with EPERM, allow everything else. Inherited descriptors stay usable.
    program = [
        (0x20, 0, 0, 4),                         # LD W ABS seccomp_data.arch
        (0x15, 1, 0, AUDIT_ARCH_X86_64),
        (0x06, 0, 0, SECCOMP_RET_KILL_PROCESS),
        (0x20, 0, 0, 0),                         # LD W ABS seccomp_data.nr
        (0x15, 12, 0, NR_SOCKETPAIR),
        (0x15, 1, 0, NR_SOCKET),
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
    filters = (SockFilter * len(program))(*(SockFilter(*item) for item in program))
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(SockFprog(len(program), filters)), 0, 0) < 0:
        _fail("prctl(PR_SET_SECCOMP)")


def apply_landlock(readonly: list[str], writable: list[str], writefiles: list[str]) -> int:
    """Restrict this process (and what it execs) to the given paths. Returns the ABI used."""
    abi = landlock_abi()
    if abi is None:
        raise OSError(0, "Landlock is not available on this kernel; use --mode unsandboxed")
    libc = ctypes.CDLL(None, use_errno=True)
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
    ruleset = libc.syscall(SYS_CREATE_RULESET, ctypes.byref(attr), ctypes.c_size_t(ctypes.sizeof(attr)),
                           ctypes.c_uint32(0))
    if ruleset < 0:
        _fail("landlock_create_ruleset")
    file_rights = FS_WRITE_FILE | FS_READ_FILE | (FS_TRUNCATE if abi >= 3 else 0)
    rules = ([(p, FS_EXECUTE | FS_READ_FILE | FS_READ_DIR) for p in readonly]
             + [(p, handled_fs) for p in writable] + [(p, file_rights) for p in writefiles])
    try:
        for path, rights in rules:
            fd = os.open(os.path.realpath(path), getattr(os, "O_PATH", os.O_RDONLY) | os.O_CLOEXEC)
            try:
                rule = PathBeneathAttr(rights, fd)
                if libc.syscall(SYS_ADD_RULE, ruleset, ctypes.c_int(RULE_PATH_BENEATH), ctypes.byref(rule),
                                ctypes.c_uint32(0)) < 0:
                    _fail(f"landlock_add_rule({path})")
            finally:
                os.close(fd)
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0:
            _fail("prctl(PR_SET_NO_NEW_PRIVS)")
        _install_socket_seccomp(libc)
        if libc.syscall(SYS_RESTRICT_SELF, ctypes.c_int(ruleset), ctypes.c_uint32(0)) < 0:
            _fail("landlock_restrict_self")
    finally:
        os.close(ruleset)
    return abi


# The memory limit lives in this line: ulimit -v in the shell that execs the agent's command, so it
# applies to the command and everything it starts. $1 KiB, $2 the agent's command.
LIMITS = 'ulimit -v "$1" || exit 125; exec bash -c "$2"'


def wrapper_argv(command: str, *, ulimit_v_kib: int) -> list[str]:
    return ["bash", "-c", LIMITS, "agent-sandbox", str(ulimit_v_kib), command]


def supervise(argv: list[str], timeout_s: int) -> int:
    """Run `argv` in its own process group; after `timeout_s` stop the group and return 124.

    This is `timeout -k 5 <s>` done here rather than by the coreutils binary: the uutils `timeout`
    on the WSL test machine could not start its command under Landlock plus seccomp ("failed to
    execute process: Operation not permitted"), and the wrapper should not depend on which
    coreutils a node has. The claim descriptor, if any, is passed on.
    """
    fd = os.environ.get("CLAIM_FD", "")
    child = subprocess.Popen(argv, process_group=0, pass_fds=(int(fd),) if fd.isdigit() else ())
    try:
        return _status(child.wait(timeout=timeout_s))
    except subprocess.TimeoutExpired:
        _killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _killpg(child.pid, signal.SIGKILL)
            child.wait()
        _killpg(child.pid, signal.SIGKILL)  # children of the command that ignored SIGTERM
        return TIMEOUT_EXIT


def _status(code: int) -> int:
    return 128 - code if code < 0 else code  # killed by signal N -> 128 + N, as a shell reports it


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sandbox.py")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--readonly", action="append", default=[])
    parser.add_argument("--writable", action="append", default=[])
    parser.add_argument("--writefile", action="append", default=[], help="a single file opened for writing, e.g. /dev/null")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--ulimit-v-kib", type=int, required=True)
    parser.add_argument("command", help="the agent's command, run with bash -c")
    args = parser.parse_args(argv)
    os.chdir(os.path.realpath(args.workdir))
    if args.mode == "landlock":
        apply_landlock(args.readonly, args.writable, args.writefile)
    return supervise(wrapper_argv(args.command, ulimit_v_kib=args.ulimit_v_kib), args.timeout)


@dataclass(frozen=True)
class Result:
    output: bytes
    exit_code: int
    timed_out: bool
    seconds: float
    cleanup: str


def _killpg(pgid: int, sig: int) -> bool:
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return False


def run_command(argv: list[str], *, env: dict[str, str], cwd: str, timeout_s: int,
                pass_fds: tuple[int, ...] = (), before_wait: object = None) -> Result:
    """Run the wrapper `argv` in a new session; return its combined output and exit status.

    `timeout` inside the wrapper normally ends the command (exit 124); the guard here waits 30 s
    longer and then kills the session itself. `before_wait`, if given, is called right after the
    process starts (the harness closes its copy of the claim socket there).
    """
    if os.name != "posix":
        raise OSError("agent commands run on POSIX only (bash, process groups, descriptor passing)")
    started = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True, pass_fds=pass_fds)
    if callable(before_wait):
        before_wait()
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout_s + 30)
        code = process.returncode
    except subprocess.TimeoutExpired:
        _killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        code = TIMEOUT_EXIT
    timed_out = code == TIMEOUT_EXIT
    # Anything the command left behind in its session (e.g. `cmd &`) goes now.
    cleanup = "none-left"
    if _killpg(process.pid, signal.SIGTERM):
        cleanup = "sigterm"
        for _ in range(20):
            if not _killpg(process.pid, 0):
                break
            time.sleep(0.1)
        else:
            _killpg(process.pid, signal.SIGKILL)
            cleanup = "sigkill"
    return Result(output, code, timed_out, time.monotonic() - started, cleanup)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f"sandbox: {exc}", file=sys.stderr)
        raise SystemExit(125)

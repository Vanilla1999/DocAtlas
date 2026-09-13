"""Run Python checks with kernel-enforced denial of all IP sockets, including native dependencies."""
import ctypes, errno, os, runpy, socket, sys
lib=ctypes.CDLL('libseccomp.so.2', use_errno=True)
lib.seccomp_init.argtypes=[ctypes.c_uint32]; lib.seccomp_init.restype=ctypes.c_void_p
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_release.argtypes=[ctypes.c_void_p]
class Compare(ctypes.Structure):
    _fields_=[('arg',ctypes.c_uint),('op',ctypes.c_int),('a',ctypes.c_uint64),('b',ctypes.c_uint64)]
ctx=lib.seccomp_init(0x7fff0000)
for syscall in (b'connect', b'sendmsg', b'sendmmsg', b'io_uring_setup'):
    number=lib.seccomp_syscall_resolve_name(syscall)
    if number >= 0:
        assert lib.seccomp_rule_add(ctx,0x50000|errno.EPERM,number,0)==0
assert lib.seccomp_rule_add(ctx,0x50000|errno.EPERM,lib.seccomp_syscall_resolve_name(b'sendto'),1,Compare(4,1,0,0))==0
assert lib.seccomp_load(ctx)==0
lib.seccomp_release(ctx)
with socket.socket(socket.AF_INET) as probe:
    try: probe.connect(('127.0.0.1',1))
    except PermissionError: pass
    else: raise RuntimeError('outbound syscall isolation failed')
os.environ['PATH'] = str(__import__('pathlib').Path(sys.executable).parent) + os.pathsep + os.environ['PATH']
print('Kernel outbound-syscall denial verified; child processes inherit it.',flush=True)
if sys.argv[1]=='-m':
    module=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_module(module,run_name='__main__')
else:
    path=sys.argv[1];sys.argv=sys.argv[1:];sys.path.insert(0,os.getcwd());runpy.run_path(path,run_name='__main__')

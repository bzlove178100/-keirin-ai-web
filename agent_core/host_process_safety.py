"""Linux child safeguards; trusted launcher/imports and external supervision required."""
import ctypes
import os
import resource
import sys

_PYTHON_OVERRIDES = frozenset({
    "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "PYTHONBREAKPOINT",
    "PYTHONFAULTHANDLER", "PYTHONTRACEMALLOC", "PYTHONPROFILEIMPORTTIME",
})


def assert_safe_spawn_environment():
    # Values are never read, formatted or logged. This is a pre-spawn tripwire,
    # not proof that the already running interpreter/loader has not been modified.
    if any(key.startswith(("LD_", "DYLD_")) or key in _PYTHON_OVERRIDES for key in os.environ):
        raise RuntimeError("secret_host_environment_rejected")


def _prctl(option, value=0):
    call = ctypes.CDLL(None).prctl
    call.restype = ctypes.c_int
    call.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    return call(option, value, 0, 0, 0)


def harden_secret_child():
    """Only in the disposable child, before decoding secret IPC/calling a factory.

    These controls do not sandbox trusted Python/driver code or remove existing
    capabilities. Do not invoke in the parent: limits/no_new_privs are irreversible.
    """
    failed = False
    try:
        if sys.platform != "linux":
            raise RuntimeError()
        assert_safe_spawn_environment()
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Linux UAPI PR_SET/GET_DUMPABLE=4/3, PR_SET/GET_NO_NEW_PRIVS=38/39.
        if _prctl(4, 0) != 0 or _prctl(38, 1) != 0:
            raise RuntimeError()
        if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0) or _prctl(3) != 0 or _prctl(39) != 1:
            raise RuntimeError()
        os.umask(0o077)
    except BaseException:
        failed = True
    if failed:
        raise RuntimeError("secret_host_child_unsafe")

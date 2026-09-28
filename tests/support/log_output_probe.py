"""Non-secret markers only; this file never handles a credential."""
import os

STDOUT_MARKER = "SYNTHETIC_ONLY_STDOUT_LOG_PROBE"
STDERR_MARKER = "SYNTHETIC_ONLY_STDERR_LOG_PROBE"


if __name__ == "__main__":
    from host_limits_probe import verify_limits
    verify_limits()
    os.write(1, (STDOUT_MARKER + "\n").encode())
    os.write(2, (STDERR_MARKER + "\n").encode())

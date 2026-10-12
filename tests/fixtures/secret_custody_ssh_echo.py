"""Fixed forced command for synthetic SSH only; no caller command execution."""
import re
import sys

for line in sys.stdin.buffer:
    if len(line) > 64 or not re.fullmatch(rb'ssh-synthetic-[0-9]+\n', line):
        raise SystemExit(2)
    sys.stdout.buffer.write(line)
    sys.stdout.buffer.flush()

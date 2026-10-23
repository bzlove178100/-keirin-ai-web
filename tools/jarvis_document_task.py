"""No-model prerequisite check; intentionally does not install/authenticate a CLI.

An authorized host calls agent_core.document_task.run_document_task(model=...)
to execute live decisions. This command must never present its blocked check as
an autonomous model run.
"""
import argparse
import json
from pathlib import Path

from agent_core.document_task import run_document_task


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args(argv)
    outcome = run_document_task(task_id=args.task_id, source=args.source, output=args.output,
                                state_dir=args.state_dir)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

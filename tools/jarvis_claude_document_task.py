"""Explicitly gated existing-Claude transport. Default: read-only preflight."""
import argparse
import json
from pathlib import Path

from agent_core.claude_decision_provider import ClaudeDecisionProvider
from agent_core.decision_loop import ModelUnavailable
from agent_core.document_task import run_document_task


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runtime-reviewed", action="store_true")
    parser.add_argument("--subscription-only-reviewed", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--task-id")
    args = parser.parse_args(argv)
    if args.execute and not all((args.source, args.output, args.state_dir, args.task_id,
                                 args.runtime_reviewed, args.subscription_only_reviewed)):
        parser.error("execution requires paths, task ID and both completed operator reviews")
    model = ClaudeDecisionProvider(args.claude, runtime_reviewed=args.runtime_reviewed,
                                    subscription_only_reviewed=args.subscription_only_reviewed)
    try:
        preflight = model.preflight()
        if not args.execute:
            outcome = {"status": "preflight_only", **preflight}
        else:
            outcome = run_document_task(task_id=args.task_id, source=args.source, output=args.output,
                                        state_dir=args.state_dir, model=model,
                                        model_binding=model.binding())
    except ModelUnavailable as exc:
        outcome = {"status": "blocked", "reason": exc.code}
    outcome["inference_attempts"] = model.inference_attempts
    outcome["provider_receipts"] = model.receipts
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0 if outcome["status"] in {"completed", "preflight_only"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Fake CLI processes + real files, never authenticated model inference."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_core.claude_decision_provider import ClaudeDecisionProvider, _invoke
from agent_core.decision_loop import ModelUnavailable
from agent_core.document_task import run_document_task
from tools.jarvis_claude_document_task import main


class ClaudeProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = self.root / "fake-cli"
        self.trace = self.root / "trace.jsonl"
        self.source = self.root / "source.txt"
        self.source.write_text("Synthetic deadline is Friday.")

    def fake(self, *, auth=None, body=None, version="2.1.296 (Claude Code)"):
        if auth is None:
            auth = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
                    "subscriptionType": "pro"}
        if body is None:
            body = '''
request = json.load(sys.stdin)
observations = request["observations"]
if not observations:
    decision = {"kind":"tool", "action":"document.read_source", "args":{}}
elif len(observations) == 1:
    assert "Friday" in observations[0]["result"]["data"]["text"]
    decision = {"kind":"tool", "action":"document.write_report", "args":{"content":"## Summary\\nDeadline: Friday.\\n## Next action\\nPrepare the report."}}
else:
    decision = {"kind":"finish", "report":"Fixture report prepared."}
print(json.dumps({"type":"result", "subtype":"success", "is_error":False,
                  "result":json.dumps(decision), "usage":{"input_tokens":12,"output_tokens":8},
                  "modelUsage":{"claude-fixture":{}}, "session_id":"DO-NOT-COPY"}))
'''
        self.cli.write_text(f"#!{sys.executable}\nimport sys,json,os,time\n"
                            f"with open({str(self.trace)!r},'a') as f: f.write(json.dumps({{'args':sys.argv[1:],'keys':list(os.environ)}})+'\\n')\n"
                            f"if '--version' in sys.argv: print({version!r}); sys.exit(0)\n"
                            f"if 'status' in sys.argv: print({json.dumps(auth)!r}); sys.exit(0)\n" + body)
        self.cli.chmod(0o700)

    def provider(self, **kwargs):
        return ClaudeDecisionProvider(self.cli, runtime_reviewed=True,
                                      subscription_only_reviewed=True, **kwargs)

    def test_fake_cli_real_tools_feedback_and_duplicate(self):
        self.fake()
        model = self.provider()
        args = dict(task_id="fake-cli", source=self.source, output=self.root / "report.md",
                    state_dir=self.root / "state", model=model, model_binding=model.binding())
        result = run_document_task(**args)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(model.inference_attempts, 3)
        self.assertIn("Friday", (self.root / "report.md").read_text())
        self.assertEqual(run_document_task(**args)["status"], "completed")
        self.assertEqual(model.inference_attempts, 3)
        self.assertEqual(len(model.receipts), 3)
        self.assertNotIn("DO-NOT-COPY", json.dumps(model.receipts))

    def test_default_entrypoint_is_preflight_only(self):
        self.fake()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--claude", str(self.cli)]), 0)
        self.assertEqual(json.loads(out.getvalue())["inference_attempts"], 0)
        self.assertNotIn('"-p"', self.trace.read_text())

    def test_missing_auth_stops_before_inference(self):
        self.fake(auth={"loggedIn":False,"authMethod":"none"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--claude", str(self.cli)]), 2)
        self.assertEqual(json.loads(out.getvalue())["reason"], "authentication_required")
        self.assertNotIn('"-p"', self.trace.read_text())

    def test_api_key_oauth_token_and_unknown_plan_fail_closed(self):
        for method, plan, code in [("api_key","pro","authentication_required"),
                                    ("oauth_token","pro","authentication_required"),
                                    ("claude.ai","team","model_unavailable")]:
            with self.subTest(method=method, plan=plan):
                self.fake(auth={"loggedIn":True,"authMethod":method,"apiProvider":"firstParty","subscriptionType":plan})
                with self.assertRaisesRegex(ModelUnavailable, code):
                    self.provider()({})

    def test_explicit_reviews_are_required(self):
        self.fake()
        with self.assertRaises(ModelUnavailable):
            ClaudeDecisionProvider(self.cli)({})
        self.assertNotIn('"-p"', self.trace.read_text())

    def test_version_drift_stops_before_auth(self):
        self.fake(version="2.1.999 (Claude Code)")
        with self.assertRaises(ModelUnavailable):
            self.provider()({})
        self.assertNotIn('"status"', self.trace.read_text())

    def test_tool_denial_empty_arguments_and_environment_isolation(self):
        self.fake()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY":"secret", "ANTHROPIC_BASE_URL":"bad",
                                     "CLAUDE_CODE_OAUTH_TOKEN":"secret", "NODE_OPTIONS":"bad",
                                     "HTTP_PROXY":"bad", "CLAUDE_CODE_USE_BEDROCK":"1"}):
            self.provider()({"observations":[]})
        item = json.loads(self.trace.read_text().splitlines()[-1])
        args = item["args"]
        for flag in ("--tools", "--setting-sources"):
            self.assertEqual(args[args.index(flag)+1], "")
        for flag in ("--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, args)
        self.assertNotIn("--bare", args)
        self.assertEqual(args[args.index("--max-turns")+1], "1")
        self.assertEqual(args[args.index("--disallowedTools")+1], "mcp__*")
        self.assertFalse({"ANTHROPIC_API_KEY","ANTHROPIC_BASE_URL","CLAUDE_CODE_OAUTH_TOKEN",
                          "NODE_OPTIONS","HTTP_PROXY","CLAUDE_CODE_USE_BEDROCK"} & set(item["keys"]))

    def test_raw_errors_and_malformed_json_are_redacted(self):
        for body in ['print("secret-token"); sys.exit(1)',
                     'print(\'{"type":"result","subtype":"success","is_error":false,"result":"{}","type":"bad"}\')',
                     'print(json.dumps({"type":"result","subtype":"success","is_error":False,"result":"NaN"}))']:
            self.fake(body=body)
            with self.assertRaisesRegex(ModelUnavailable, "^model_unavailable$"):
                self.provider()({})

    def test_timeout_does_not_retry(self):
        self.fake(body="time.sleep(5)")
        model = self.provider(timeout=1)
        with self.assertRaisesRegex(ModelUnavailable, "model_timeout"):
            model({})
        self.assertEqual(model.inference_attempts, 1)
        self.assertEqual(model.receipts, [])

    def test_transport_bounds_stdout(self):
        self.fake(body="print('x'*10000)")
        with self.assertRaisesRegex(ModelUnavailable, "^model_unavailable$"):
            _invoke([str(self.cli)], env=self.provider().env, cwd=self.root, limit=100)

    def test_invalid_model_action_stays_under_host_validation(self):
        self.fake(body='print(json.dumps({"type":"result","subtype":"success","is_error":False,"result":json.dumps({"kind":"tool","action":"shell.run","args":{}})}))')
        model = self.provider()
        result = run_document_task(task_id="bad", source=self.source, output=self.root / "report.md",
                                   state_dir=self.root / "state", model=model, model_binding=model.binding())
        self.assertEqual(result["reason"], "invalid_model_decision")
        self.assertFalse((self.root / "report.md").exists())


if __name__ == "__main__":
    unittest.main()

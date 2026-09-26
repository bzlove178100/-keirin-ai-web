from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
AGENT_CORE = ROOT / "agent_core"


class _ExceptionPersistenceVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[str] = []
        self._exception_stack: list[str] = []

    @staticmethod
    def _references_name(node: ast.AST | None, name: str) -> bool:
        if node is None:
            return False
        return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._exception_stack.append(node.name)
            for statement in node.body:
                self.visit(statement)
            self._exception_stack.pop()
        else:
            self.generic_visit(node)

    def _record(self, node: ast.AST, rule: str) -> None:
        self.violations.append(f"{self.path.relative_to(ROOT)}:{getattr(node, 'lineno', '?')}:{rule}")

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._exception_stack:
            exc = self._exception_stack[-1]
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr in {"last_error", "blocked_reason"}:
                    if self._references_name(node.value, exc):
                        self._record(node, "raw_exception_assigned_to_persistent_state")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._exception_stack:
            exc = self._exception_stack[-1]
            target = node.target
            if isinstance(target, ast.Attribute) and target.attr in {"last_error", "blocked_reason"}:
                if self._references_name(node.value, exc):
                    self._record(node, "raw_exception_assigned_to_persistent_state")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._exception_stack:
            exc = self._exception_stack[-1]
            func_name = None
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in {"append_event", "save_state", "BlockedAction"}:
                expressions = list(node.args) + [kw.value for kw in node.keywords]
                if any(self._references_name(expr, exc) for expr in expressions):
                    self._record(node, f"raw_exception_reaches_{func_name}")
        self.generic_visit(node)


class PersistenceRedactionStaticTest(unittest.TestCase):
    def test_exception_objects_do_not_flow_directly_into_durable_state_or_events(self):
        violations: list[str] = []
        for path in sorted(AGENT_CORE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            visitor = _ExceptionPersistenceVisitor(path)
            visitor.visit(tree)
            violations.extend(visitor.violations)
        self.assertEqual(violations, [], "\n".join(violations))

    def test_runtime_bridge_blocked_reason_is_replaced_with_fixed_literal(self):
        path = AGENT_CORE / "runtime_bridge.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "BlockedAction"
        ]
        self.assertGreaterEqual(len(calls), 1)
        for call in calls:
            self.assertEqual(len(call.args), 1)
            self.assertIsInstance(call.args[0], ast.Constant)
            self.assertEqual(call.args[0].value, "runtime_bridge_blocked")

    def test_runner_untyped_error_fallbacks_remain_fixed_redacted_literals(self):
        source = (AGENT_CORE / "runner.py").read_text(encoding="utf-8")
        self.assertIn("UntrustedActionError:action_exception_redacted", source)
        self.assertIn("UntrustedActionError:verification_exception_redacted", source)
        self.assertNotIn('f"UntrustedActionError:{exc}', source)
        self.assertNotIn('f"{type(exc).__name__}:{exc}"', source)


if __name__ == "__main__":
    unittest.main()

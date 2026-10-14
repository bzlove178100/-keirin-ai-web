"""Synthetic, network-free publisher boundary and failure tests."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / '.github/scripts/claude_task_bridge.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
BASE = 'a' * 40
REPO = 'bzlove178100/-keirin-ai-web'
BODY = '### Goal and expected behavior\nSynthetic change.\n\n### Allowed Python files\nml/example.py\ntests/test_example.py\n\n### Synthetic tests and acceptance criteria\nDo not run here.'
EVENT = {'action': 'created', 'repository': {'full_name': REPO},
         'sender': {'login': 'bzlove178100'},
         'issue': {'number': 300, 'user': {'login': 'bzlove178100'}, 'state': 'open',
                   'title': 'Synthetic task', 'body': BODY},
         'comment': {'id': 100, 'user': {'login': 'bzlove178100'}, 'body': '/claude-run'}}


class FakeAPI:
    def __init__(self):
        self.calls = []
        self.base = BASE
        self.issue = {'title': 'Synthetic task', 'body': BODY,
                      'user': {'login': 'bzlove178100'}, 'state': 'open'}
        self.comment = {**EVENT['comment'], 'issue_url': f'https://api.github.com/repos/{REPO}/issues/300'}
        self.refs, self.prs, self.prfiles = [], [], []
        paths = ['ml/example.py', 'tests/test_example.py', 'AGENTS.md', 'SOURCE_ACQUISITION_STATUS.md']
        self.tree = {'truncated': False, 'tree': [
            {'path': p, 'sha': str(i + 1) * 40, 'mode': '100644', 'type': 'blob', 'size': 10}
            for i, p in enumerate(paths)]}
        self.fail_on = None
        self.move_on_commit = False
        self.change_on_commit = False

    def call(self, path, data=None):
        self.calls.append((path, copy.deepcopy(data)))
        if path == self.fail_on:
            raise b.Refused('SIMULATED_403')
        if data is not None:
            if path == 'git/commits':
                if self.move_on_commit:
                    self.base = 'b' * 40
                if self.change_on_commit:
                    self.issue['body'] += '\nchanged'
            if path == 'pulls':
                return {'html_url': f'https://github.com/{REPO}/pull/301'}
            if path == 'git/refs':
                self.refs.append({'ref': data['ref']})
            return {'sha': 'e' * 40}
        if path == 'git/ref/heads/main':
            return {'object': {'sha': self.base}}
        if path == 'issues/300':
            return copy.deepcopy(self.issue)
        if path == 'issues/comments/100':
            return copy.deepcopy(self.comment)
        if path.startswith('git/matching-refs/'):
            return self.refs
        if path == 'pulls?state=open&per_page=100':
            return self.prs
        if path.startswith('pulls/'):
            return self.prfiles
        if path.startswith('git/commits/'):
            return {'tree': {'sha': 'c' * 40}}
        if path.startswith('git/trees/'):
            return self.tree
        if path.startswith('git/blobs/'):
            return {'encoding': 'base64', 'content': base64.b64encode(b'value = 1\n').decode()}
        raise AssertionError('Unexpected endpoint: ' + path)

    @property
    def writes(self):
        return [(p, d) for p, d in self.calls if d is not None]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.manifest, self.prompt = b.prepare(self.api, EVENT, BASE)
        self.envelope = {'manifest': self.manifest,
                         'proposal': {'files': [{'path': 'ml/example.py', 'content': 'value = 2\n'}]}}
        self.api.calls.clear()

    def refused_without_writes(self):
        with self.assertRaises(b.Refused):
            b.publish(self.api, EVENT, self.envelope)
        self.assertEqual(self.api.writes, [])

    def test_success_creates_only_task_ref_and_draft_without_execution(self):
        marker = ROOT / 'must-not-exist-bridge-test'
        self.assertFalse(marker.exists())
        self.envelope['proposal']['files'][0]['content'] = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        url = b.publish(self.api, EVENT, self.envelope)
        self.assertTrue(url.endswith('/pull/301'))
        self.assertFalse(marker.exists())
        writes = self.api.writes
        self.assertEqual([p for p, _ in writes], ['git/blobs', 'git/trees', 'git/commits', 'git/refs', 'pulls'])
        self.assertEqual(writes[1][1]['tree'][0]['mode'], '100644')
        self.assertEqual(writes[2][1]['parents'], [BASE])
        self.assertEqual(writes[3][1], {'ref': 'refs/heads/claude/task-300', 'sha': 'e' * 40})
        self.assertTrue(writes[4][1]['draft'])
        self.assertIn('NOT RUN', writes[4][1]['body'])
        self.assertNotIn('force', json.dumps(writes))

    def test_prepare_is_read_only_and_includes_policy(self):
        self.assertIn('SOURCE_ACQUISITION_STATUS.md', self.prompt)
        self.assertIn('NO tools', self.prompt)
        self.assertEqual(self.api.writes, [])

    def test_scope_refuses_wildcards_nested_traversal_reserved_duplicate_and_empty(self):
        for scope in ['ml/*.py', 'ml/nested/x.py', '../ml/x.py', 'ml/../x.py',
                      '.github/workflows/x.py', 'tests/test_claude_task_bridge.py',
                      'ml/x.py\nml/x.py', '', 'ml/x.PY', 'ml/ä.py']:
            with self.subTest(scope=scope), self.assertRaises(b.Refused):
                b.allowed_paths('### Allowed Python files\n' + scope)

    def test_invalid_event_is_rejected(self):
        for path, value in [('sender', {'login': 'other'}), ('action', 'edited'),
                            ('repository', {'full_name': 'other/repo'}),
                            ('comment', {**EVENT['comment'], 'body': '/claude-run now'})]:
            event = {**EVENT, path: value}
            with self.subTest(path=path), self.assertRaises(b.Refused):
                b.prepare(self.api, event, BASE)
        event = copy.deepcopy(EVENT)
        event['issue']['pull_request'] = {}
        with self.assertRaises(b.Refused):
            b.prepare(self.api, event, BASE)
        self.assertEqual(self.api.writes, [])

    def test_stale_main(self):
        self.api.base = 'b' * 40
        self.refused_without_writes()

    def test_changed_issue(self):
        self.api.issue['body'] += '\nChanged goal.'
        self.refused_without_writes()

    def test_changed_or_foreign_trigger(self):
        for field, value in [('body', '/claude-run changed'), ('user', {'login': 'other'}),
                             ('issue_url', f'https://api.github.com/repos/{REPO}/issues/301')]:
            with self.subTest(field=field):
                old = self.api.comment[field]
                self.api.comment[field] = value
                self.refused_without_writes()
                self.api.comment[field] = old

    def test_existing_branch_stops_retries(self):
        self.api.refs = [{'ref': 'refs/heads/claude/task-300'}]
        self.refused_without_writes()

    def test_overlap_including_rename_source(self):
        self.api.prs = [{'number': 253}]
        for files in [[{'filename': 'ml/example.py'}],
                      [{'filename': 'docs/new.txt', 'previous_filename': 'ml/example.py'}]]:
            self.api.prfiles = files
            self.refused_without_writes()

    def test_truncated_pr_list_and_files_fail_closed(self):
        self.api.prs = [{'number': 253}] * 100
        self.refused_without_writes()
        self.api.prs = [{'number': 253}]
        self.api.prfiles = [{'filename': 'docs/file.md'}] * 100
        self.refused_without_writes()

    def test_tree_truncation_and_symlink_and_executable(self):
        self.api.tree['truncated'] = True
        self.refused_without_writes()
        self.api.tree['truncated'] = False
        for mode in ['120000', '100755', '160000']:
            self.api.tree['tree'][0]['mode'] = mode
            self.refused_without_writes()

    def test_tampered_manifest(self):
        for key, value in [('branch', 'main'), ('tree', 'd' * 40), ('scope', ['ml/other.py']),
                           ('issue', 301), ('comment', 101)]:
            with self.subTest(key=key):
                old = self.manifest[key]
                self.manifest[key] = value
                self.refused_without_writes()
                self.manifest[key] = old

    def test_invalid_proposals(self):
        bad = [{'files': []}, {'files': [], 'command': 'run'},
               {'files': [{'path': 'ml/unapproved.py', 'content': 'x'}]},
               {'files': [{'path': 'ml/example.py', 'content': ''}]},
               {'files': [{'path': 'ml/example.py', 'content': 'x\x00'}]},
               {'files': [{'path': 'ml/example.py', 'content': 'x' * 24001}]},
               {'files': [{'path': 'ml/example.py', 'content': 'value = 1\n'}]},
               {'files': [{'path': 'ml/example.py', 'content': 'x'}] * 2},
               {'files': [{'path': 'ml/example.py', 'content': 'x', 'mode': '120000'}]}]
        for proposal in bad:
            with self.subTest(proposal=str(proposal)[:100]):
                self.envelope['proposal'] = proposal
                self.refused_without_writes()

    def test_main_movement_during_write_never_exposes_ref(self):
        self.api.move_on_commit = True
        with self.assertRaisesRegex(b.Refused, 'MAIN_MOVED'):
            b.publish(self.api, EVENT, self.envelope)
        self.assertNotIn('git/refs', [p for p, _ in self.api.writes])

    def test_issue_changes_during_write_never_exposes_ref(self):
        self.api.change_on_commit = True
        with self.assertRaisesRegex(b.Refused, 'ISSUE_CHANGED_AFTER_OWNER_TRIGGER'):
            b.publish(self.api, EVENT, self.envelope)
        self.assertNotIn('git/refs', [p for p, _ in self.api.writes])

    def test_ref_conflict_never_retries_or_opens_pr(self):
        self.api.fail_on = 'git/refs'
        with self.assertRaises(b.Refused):
            b.publish(self.api, EVENT, self.envelope)
        self.assertEqual([p for p, _ in self.api.writes].count('git/refs'), 1)
        self.assertNotIn('pulls', [p for p, _ in self.api.writes])

    def test_pr_failure_leaves_branch_and_retry_stops(self):
        self.api.fail_on = 'pulls'
        with self.assertRaises(b.Refused):
            b.publish(self.api, EVENT, self.envelope)
        self.api.calls.clear()
        self.refused_without_writes()

    def test_missing_file_and_large_source_are_refused(self):
        self.api.tree['tree'][0]['path'] = 'ml/elsewhere.py'
        self.refused_without_writes()
        self.api.tree['tree'][0]['path'] = 'ml/example.py'
        self.api.tree['tree'][0]['size'] = 24001
        self.refused_without_writes()

    def test_http_failure_does_not_retry_or_write(self):
        self.api.fail_on = 'issues/300'
        self.refused_without_writes()
        self.assertEqual([p for p, _ in self.api.calls].count('issues/300'), 1)

    def test_workflow_separates_credentials_and_fails_closed(self):
        workflow = (ROOT / '.github/workflows/claude-task-bridge.yml').read_text()
        propose, publish = workflow.split('\n  publish:', 1)
        self.assertIn("vars.CLAUDE_TASK_BRIDGE_ENABLED == 'true'", propose)
        self.assertIn("vars.CLAUDE_TASK_BRIDGE_ENABLED == 'true'", publish)
        self.assertIn("github.triggering_actor == 'bzlove178100'", propose)
        self.assertNotIn(': write', propose)
        self.assertNotIn('secrets.', publish)
        self.assertNotIn('anthropics/', publish)
        self.assertNotIn('id-token:', workflow)
        self.assertNotIn('schedule:', workflow)
        self.assertNotIn('workflow_dispatch:', workflow)
        self.assertIn('--disallowedTools "*"', propose)
        self.assertIn('--strict-mcp-config', propose)
        self.assertIn('--bare', propose)
        # The pinned Action treats empty CLI values as boolean flags and falls
        # back to all settings sources. Use nonempty, supported values instead.
        self.assertIn('--setting-sources user', propose)
        self.assertNotIn('--setting-sources ""', propose)
        self.assertIn('"disableAllHooks":true', propose)
        self.assertIn('github_token: ${{ github.token }}', propose)
        self.assertNotIn('outputs.branch_name', workflow)
        for line in workflow.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'@[0-9a-f]{40}(?: |$)')


if __name__ == '__main__':
    unittest.main()

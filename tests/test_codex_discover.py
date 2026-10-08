"""Codex discovery must find sources without a project path or content reads."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_discover import discover

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'codex_discover.py'


class CodexDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.user_home = Path(self.tmp.name) / 'person'
        self.user_home.mkdir()
        self.codex_home = self.user_home / '.codex'
        self.codex_home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, content='example'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--user-home', str(self.user_home),
                               '--codex-home', str(self.codex_home), *args], capture_output=True, text=True)

    def result(self, *args):
        ran = self.run_tool(*args)
        self.assertEqual(ran.returncode, 0, ran.stderr + ran.stdout)
        return json.loads(ran.stdout)

    def paths(self, result):
        return {item['path'] for source in result['sources'] for item in source['files']}

    def test_discovers_skills_prompts_rules_automations_and_sessions_without_project_path(self):
        expected = [self.codex_home/'skills/review/SKILL.md', self.user_home/'.agents/skills/helper/SKILL.md',
                    self.codex_home/'prompts/planning.md', self.codex_home/'AGENTS.md',
                    self.codex_home/'automations/weekly/automation.toml', self.codex_home/'sessions/day/task.jsonl',
                    self.codex_home/'archived_sessions/task.jsonl', self.codex_home/'history.jsonl']
        for path in expected: self.put(path)
        result = self.result()
        self.assertTrue(set(map(str,expected)) <= self.paths(result))
        self.assertFalse(result['content_read'])
        self.assertEqual(result['summary']['files'], len(expected))

    def test_credentials_configs_databases_and_source_content_are_not_exposed(self):
        sentinel = 'PRIVATE_CONTENT_MUST_NOT_APPEAR'
        secret_paths = [self.codex_home/'auth.json', self.codex_home/'config.toml', self.codex_home/'state.sqlite',
                        self.codex_home/'skills/test/.env', self.codex_home/'skills/test/token.json']
        for path in secret_paths: self.put(path, sentinel)
        material = self.put(self.codex_home/'skills/test/SKILL.md', sentinel)
        result = self.result()
        self.assertEqual(self.paths(result), {str(material)})
        self.assertNotIn(sentinel, json.dumps(result))
        self.assertEqual(material.read_text(), sentinel)

    def test_source_symlinks_are_reported_without_traversing_external_material(self):
        external = self.put(self.user_home/'other/private.md')
        (self.codex_home/'skills').mkdir()
        (self.codex_home/'skills/linked').symlink_to(external.parent, target_is_directory=True)
        result = self.result()
        self.assertNotIn(str(external), self.paths(result))
        self.assertGreater(result['summary']['blocked_paths'], 0)

    def test_linked_codex_root_is_not_followed(self):
        target = self.user_home/'actual'
        self.put(target/'skills/test/SKILL.md')
        linked = self.user_home/'linked-codex'
        linked.symlink_to(target, target_is_directory=True)
        result = self.result('--codex-home', str(linked))
        self.assertEqual(result['summary']['files'], 0)
        self.assertGreater(result['summary']['blocked_paths'], 0)

    def test_plugin_material_is_separated_from_personal_skill_authorship(self):
        path = self.put(self.codex_home/'plugins/cache/vendor/package/1/skills/check/SKILL.md')
        result = self.result()
        source = next(row for row in result['sources'] if str(path) in {f['path'] for f in row['files']})
        self.assertEqual(source['category'], 'plugin_material')
        self.assertEqual(source['authorship'], 'unknown_or_third_party')

    def test_discovery_never_opens_source_content(self):
        self.put(self.codex_home/'skills/review/SKILL.md')
        self.put(self.codex_home/'sessions/day/task.jsonl')
        with patch('builtins.open', side_effect=AssertionError('Source content read')):
            with patch.object(Path, 'open', side_effect=AssertionError('Source content read')):
                result = discover(self.user_home, self.codex_home)
        self.assertEqual(result['summary']['files'], 2)

    def test_missing_roots_produce_an_empty_inventory_instead_of_a_path_question(self):
        result = self.result()
        self.assertEqual(result['summary']['files'], 0)
        self.assertTrue(any(row['status']=='missing' for row in result['sources']))

    def test_output_is_local_new_file_and_stdout_is_compact(self):
        self.put(self.codex_home/'skills/test/SKILL.md')
        target = self.user_home/'results/discovery.json'
        result = self.result('--output', str(target))
        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text())['summary']['files'], 1)
        self.assertNotIn('sources', result)

    def test_existing_output_is_preserved(self):
        target = self.put(self.user_home/'results/discovery.json', 'keep original')
        ran = self.run_tool('--output', str(target))
        self.assertEqual(ran.returncode, 2)
        self.assertEqual(json.loads(ran.stdout)['code'], 'LOCAL_DISCOVERY_BLOCKED')
        self.assertEqual(target.read_text(), 'keep original')

    def test_output_cannot_be_written_into_codex_source(self):
        target = self.codex_home/'new-record.json'
        ran = self.run_tool('--output', str(target))
        self.assertEqual(ran.returncode, 2)
        self.assertEqual(json.loads(ran.stdout)['code'], 'LOCAL_DISCOVERY_BLOCKED')
        self.assertFalse(target.exists())

    def test_symlink_output_directory_is_not_followed(self):
        targetdir = self.user_home/'actual-results'
        targetdir.mkdir()
        (self.user_home/'linked-results').symlink_to(targetdir, target_is_directory=True)
        ran = self.run_tool('--output', str(self.user_home/'linked-results/discovery.json'))
        self.assertEqual(ran.returncode, 2)
        self.assertEqual(json.loads(ran.stdout)['code'], 'LOCAL_DISCOVERY_BLOCKED')
        self.assertFalse((targetdir/'discovery.json').exists())


if __name__ == '__main__': unittest.main()

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('cleanup', ROOT / 'collector/cleanup.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ConfigurationTests(unittest.TestCase):
    def test_opt_in_and_retention_validation(self):
        self.assertFalse(c.settings({})['enabled'])
        for invalid in (-1, 0, 23, '24h; rm -rf /', True):
            with self.assertRaises(ValueError):
                c.settings({'cleanup': {'imageAgeHours': invalid}})
        with self.assertRaises(ValueError):
            c.settings({'cleanup': {'enabled': 'yes'}})
        with self.assertRaises(ValueError):
            c.settings({'cleanup': {'scheduleTime': '03:30\nExecStart=bad'}})

    def test_only_fixed_docker_prunes(self):
        commands = c.docker_commands(c.settings({}))
        self.assertEqual([kind for kind, _ in commands], ['images', 'buildCache'])
        self.assertEqual(commands[0][1][1:3], ['image', 'prune'])
        self.assertIn('until=168h', commands[0][1])
        self.assertIn('until=24h', commands[1][1])
        self.assertNotIn('volume', repr(commands))
        self.assertNotIn('container', repr(commands))


@unittest.skipUnless(sys.platform == 'linux', 'Linux no-follow directory descriptors required')
class FileCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'lib/plugins').mkdir(parents=True)
        (self.root / 'lib/plugins/plugin.js').write_text('framework')
        self.ipc = self.root / 'data/status'
        self.ipc.mkdir(parents=True)
        self.config = {'yunzaiRoot': str(self.root), 'ipcDirectory': str(self.ipc),
                       'cleanup': {'enabled': True}}
        self.now = time.time()

    def tearDown(self):
        self.temporary.cleanup()

    def old(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('old')
        os.utime(path, (self.now - 30 * 86400,) * 2)
        return path

    def test_preserves_recent_hidden_links_and_business_files(self):
        old = self.old(self.root / 'temp/nested/old.png')
        recent = self.root / 'temp/recent.png'
        recent.write_text('recent')
        hidden = self.old(self.root / 'temp/.gitignore')
        history = self.old(self.root / 'plugins/chatgpt-plugin/data/history.db')
        os.symlink(history, self.root / 'temp/link')
        os.symlink(history.parent, self.root / 'temp/linked-directory')
        hardlink = self.root / 'temp/hardlink'
        os.link(history, hardlink)
        result = c.clean_tree(self.root / 'temp', self.now - 86400, True)
        self.assertEqual(result, {'files': 1, 'bytes': 3})
        self.assertFalse(old.exists())
        for path in (recent, hidden, history, hardlink):
            self.assertTrue(path.exists())
        self.assertTrue((self.root / 'temp/link').is_symlink())

    def test_root_symlink_is_rejected(self):
        outside = self.root / 'protected'
        outside.mkdir()
        os.symlink(outside, self.root / 'temp')
        with self.assertRaises(ValueError):
            c.clean_tree(self.root / 'temp', self.now, True)

    def test_only_rotated_logs(self):
        rotated = self.old(self.root / 'logs/error.log.1.gz')
        compressed = self.old(self.root / 'logs/command.2026-01-01.log.zst')
        active = self.old(self.root / 'logs/error.log')
        dated = self.old(self.root / 'logs/command.2026-01-01.log')
        result = c.clean_tree(self.root / 'logs', self.now - 86400, True, True)
        self.assertEqual(result['files'], 2)
        self.assertFalse(rotated.exists())
        self.assertFalse(compressed.exists())
        self.assertTrue(active.exists())
        self.assertTrue(dated.exists())

    def test_dry_run_does_not_invoke_docker_or_delete(self):
        old = self.old(self.root / 'temp/old.png')
        with patch.object(c, 'execute', side_effect=AssertionError('must not execute')):
            report = c.run_cleanup(self.config, False, runner=lambda _: self.fail('Docker invoked'))
        self.assertTrue(old.exists())
        self.assertEqual(report['filesDeleted'], 1)
        self.assertFalse((self.ipc / 'cleanup.json').exists())

    def test_disabled_apply_rejected(self):
        self.config['cleanup']['enabled'] = False
        with self.assertRaises(ValueError):
            c.run_cleanup(self.config, True)

    def test_failures_reported_and_unrelated_files_preserved(self):
        old = self.old(self.root / 'data/upload_tmp/old.tmp')
        database = self.old(self.root / 'data/important.db')
        def runner(args):
            if args[1] == 'image':
                raise PermissionError('Docker unavailable')
            return 'Total: 1.2GB\n'
        report = c.run_cleanup(self.config, True, runner=runner)
        self.assertFalse(report['success'])
        self.assertEqual(report['docker'][1]['reclaimed'], '1.2GB')
        self.assertFalse(old.exists())
        self.assertTrue(database.exists())
        self.assertEqual(json.loads((self.ipc / 'cleanup.json').read_text())['filesDeleted'], 1)


if __name__ == '__main__':
    unittest.main()

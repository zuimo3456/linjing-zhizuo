"""The public artifact must be explicit, portable and free of local runtime data."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_web_preview import OUTPUTS, build_preview


class WebPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'static').mkdir()
        (self.root/'static/index.html').write_text('<link href="./style.css"><script src="./app.js"></script>', encoding='utf8')
        (self.root/'static/app.js').write_text('const local = true;', encoding='utf8')
        (self.root/'static/style.css').write_text('body{}', encoding='utf8')
        (self.root/'data').mkdir()
        (self.root/'data/private-project.json').write_text('private', encoding='utf8')
        self.output = self.root/'public'

    def test_only_allowlisted_assets_are_published(self):
        build_preview(self.root, self.output, 'abc1234')
        self.assertEqual({item.name for item in self.output.iterdir()}, OUTPUTS)
        self.assertEqual(json.loads((self.output/'version.json').read_text())['commit'], 'abc1234')
        self.assertFalse((self.output/'data').exists())

    def test_preview_flag_is_injected_before_app_without_changing_source(self):
        before = (self.root/'static/index.html').read_bytes()
        build_preview(self.root, self.output, 'abc1234')
        html = (self.output/'index.html').read_text()
        self.assertLess(html.index('preview-config.js'), html.index('./app.js'))
        self.assertIn('LINJING_PREVIEW_MODE = true', (self.output/'preview-config.js').read_text())
        self.assertEqual(before, (self.root/'static/index.html').read_bytes())

    def test_unexpected_output_files_are_not_silently_published(self):
        self.output.mkdir()
        (self.output/'private.txt').write_text('private')
        with self.assertRaises(ValueError):
            build_preview(self.root, self.output, 'abc1234')

    def test_missing_entry_fails_before_build(self):
        (self.root/'static/index.html').write_text('<p>No app</p>')
        with self.assertRaises(ValueError):
            build_preview(self.root, self.output, 'abc1234')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from freeze import row, scan, write


class FreezeTests(unittest.TestCase):
    def test_content_change_detected_even_same_size(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'x'
            p.write_text('abc')
            before = row(root, p)
            p.write_text('abd')
            self.assertNotEqual(before['sha256'], row(root, p)['sha256'])

    def test_symlink_record_does_not_follow_mutable_target(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'x'
            p.write_text('abc')
            link = root / 'y'
            link.symlink_to('x')
            self.assertEqual(row(root, link)['kind'], 'symlink')
            self.assertEqual(row(root, link)['target'], 'x')

    def test_cache_excluded_and_real_file_kept(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '__pycache__').mkdir()
            (root / '__pycache__/cache').write_text('x')
            (root / 'evidence').write_text('y')
            self.assertEqual([x['path'] for x in scan(root)], ['evidence'])

    def test_freeze_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'manifest.json'
            write(p, {'v': 1})
            with self.assertRaises(FileExistsError):
                write(p, {'v': 2})


if __name__ == '__main__':
    unittest.main()

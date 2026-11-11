"""Handoff manifests must detect drift, not just list files."""
import unittest,tempfile,json
from pathlib import Path
from ..ops.handoff_manifest import build,verify


class HandoffManifestTests(unittest.TestCase):
    def test_detects_change_and_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'sub').mkdir()
            (root/'a.json').write_text('{"x":1}');(root/'sub'/'b.sqlite').write_bytes(b'rows')
            manifest=build(root)
            self.assertEqual([f['path'] for f in manifest['files']],['a.json','sub/b.sqlite'])
            self.assertEqual(verify(root,manifest),{'unchanged':2,'missing':[],'changed':[]})
            (root/'a.json').write_text('{"x":2}')
            (root/'sub'/'b.sqlite').unlink()
            result=verify(root,manifest)
            self.assertEqual(result['changed'],['a.json'])
            self.assertEqual(result['missing'],['sub/b.sqlite'])

    def test_manifest_file_is_not_hashed_into_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'a.txt').write_text('x')
            (root/'handoff-file-manifest.json').write_text('{}')
            self.assertEqual([f['path'] for f in build(root)['files']],['a.txt'])

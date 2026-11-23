import base64
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from saddle import Archive,Runtime
class InteropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cli=os.environ.get('SADDLE_CLI')
        if not cli:raise unittest.SkipTest('Set SADDLE_CLI to exercise the official CLI')
        cls.command=[os.environ.get('SADDLE_NODE','node'),cli]
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'files';self.root.mkdir();self.note=self.root/'note.md';self.note.write_text('hello')
        self.archive=Archive(self.root/'.note.md.saddle')
        self.runtime=Runtime(self.command,profile=Path(self.temp.name)/'profile')
    def test_bidirectional_named_records(self):
        self.archive.set_json('resource.json',dict(name='note',path='note.md',metadata=dict(tag='work')))
        result=self.runtime.request('archive.get',self.note,record='resource.json')
        self.assertEqual(base64.b64decode(result['bytes']),self.archive.read('resource.json'))
        self.runtime.request('archive.put',self.note,record='extensions/python',bytes=base64.b64encode(b'\x00\xff').decode())
        self.assertEqual(self.archive.read('extensions/python'),b'\x00\xff')
        self.archive.verify()
    def test_real_history_and_metadata_runtime(self):
        self.assertEqual(self.runtime.history(self.note),[])
        self.assertFalse(self.archive.path.exists())
        self.runtime.configure(self.note,'history','enabled')
        self.assertGreaterEqual(len(self.runtime.history(self.note)),1)
        self.assertIn('content.automerge',self.archive.names())
        self.runtime.set_metadata(self.note,dict(name='note',path='note.md',metadata=dict(tag='work')))
        self.assertEqual(self.archive.get_json('resource.json')['metadata']['tag'],'work')
        self.runtime.reset_history(self.note)
        self.assertEqual(len(self.runtime.history(self.note)),1)
        self.runtime.configure(self.note,'history','disabled')
        self.assertEqual(self.runtime.history(self.note),[])
        self.assertNotIn('content.automerge',self.archive.names())
        self.assertEqual(self.note.read_text(),'hello')
    def test_single_file_stops_parent_inheritance(self):
        self.runtime.configure(self.root,'history','enabled')
        self.assertFalse(self.runtime.inspect(self.note)['features']['history'])

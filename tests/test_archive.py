import tempfile
from pathlib import Path
import unittest
from saddle import Archive, SaddleError, MAGIC
class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'.note.md.saddle';self.archive=Archive(self.path)
    def test_unknown_records_and_document_chunks(self):
        self.archive.write('plugin/state',b'\0\xff')
        self.archive.write('content.automerge',b'first',heads=['a'],num_changes=1)
        self.archive.write('content.automerge',b'second',append=True,heads=['b'],num_changes=2)
        self.assertEqual(self.archive.read('content.automerge'),b'firstsecond')
        self.assertEqual(self.archive.read('plugin/state'),b'\0\xff')
        self.assertEqual(self.archive.inspect()['index']['content.automerge']['numChanges'],2)
        self.archive.remove('content.automerge')
        self.assertNotIn(b'first',self.path.read_bytes())
        self.assertEqual(self.archive.names(),['plugin/state'])
        self.assertEqual(self.path.read_bytes()[:8],MAGIC)
    def test_torn_slot_recovers_and_payload_corruption_fails(self):
        self.archive.write('value',b'first');self.archive.write('value',b'second')
        data=bytearray(self.path.read_bytes());data[8+68+36]^=1;self.path.write_bytes(data)
        self.assertEqual(self.archive.read('value'),b'first')
        data[144]^=1;self.path.write_bytes(data)
        with self.assertRaises(SaddleError):self.archive.read('value')
    def test_names_json_and_compaction(self):
        for name in ['../x','/x','a//b','a\\b','a:bad']:
            with self.assertRaises(SaddleError):self.archive.write(name,b'x')
        self.archive.set_json('resource.json',{'name':'note','path':'note.md','metadata':{'tag':'日本'}})
        self.assertEqual(self.archive.get_json('resource.json')['metadata']['tag'],'日本')
        before=self.archive.get_json('resource.json');self.archive.compact()
        self.assertEqual(self.archive.get_json('resource.json'),before)
        self.archive.verify()

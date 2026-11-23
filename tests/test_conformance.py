import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from saddle import Archive,resource,import_metadata
ROOT=Path(__file__).resolve().parents[1]/"conformance"
def cases(name):return json.loads((ROOT/"v1"/(name+".json")).read_text())["cases"]
class Conformance(unittest.TestCase):
 def test_source_pin(self):
  source=json.loads((ROOT/"source.json").read_text());self.assertRegex(source["revision"],r"^[0-9a-f]{40}$")
  for name,digest in source["sha256"].items():self.assertEqual(hashlib.sha256((ROOT/"v1"/name).read_bytes()).hexdigest(),digest)
 def test_containers(self):
  with tempfile.TemporaryDirectory() as temp:
   for case in cases("containers"):
    with self.subTest(case["name"]):
     path=Path(temp)/"fixture.saddle";path.write_bytes(base64.b64decode(case["archive"]));archive=Archive(path)
     if not case["valid"]:
      with self.assertRaises(ValueError):archive.verify()
      continue
     archive.verify();self.assertEqual(sorted(archive.names()),sorted(case["records"]))
     for name,value in case["records"].items():self.assertEqual(base64.b64encode(archive.read(name)).decode(),value)
     self.assertIsNone(archive.read("missing"))
 def test_resources(self):
  for case in cases("resources"):
   with self.subTest(case["name"]):
    if case["valid"]:self.assertEqual(resource(case["value"]),case["value"])
    else:
     with self.assertRaises(ValueError):resource(case["value"])
 def test_frontmatter(self):
  for case in cases("frontmatter"):
   with self.subTest(case["name"]):
    if case.get("invalid"):
     with self.assertRaises(ValueError):import_metadata("note.md",case["source"],case.get("descriptor"))
    else:self.assertEqual(import_metadata("note.md",case["source"]).get("properties"),case["properties"])

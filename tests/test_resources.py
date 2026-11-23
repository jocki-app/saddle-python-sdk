import unittest
from saddle import companion_path,resource,new_resource,import_metadata,effective_features,SaddleError
class ResourceTests(unittest.TestCase):
    def test_paths_and_inline_conflicts(self):
        self.assertEqual(companion_path('a/notes.md'),'a/.notes.md.saddle')
        value=new_resource('notes.md');value['metadata']={'tag':'work'}
        self.assertEqual(import_metadata('notes.md','---\nowner: me\n---\n',value)['properties']['owner'],'me')
        with self.assertRaises(SaddleError):import_metadata('notes.md','---\ntag: personal\n---\n',value)
        for path in ['../outside','file:///outside','https:broken']:
            with self.assertRaises(SaddleError):resource(dict(name='x',path=path))
    def test_feature_overrides_and_boundaries(self):
        policy=dict(vault=dict(history=True),folders={'a':{'history':False}},files={'f':{'sync':True}})
        self.assertEqual(effective_features(policy,{},'a/file','f'),{'history':False,'sync':True})
        self.assertEqual(effective_features({}, {},'file'),{'history':False,'sync':False})

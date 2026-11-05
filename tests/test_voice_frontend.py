import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace as T
from unittest.mock import patch
import voice_frontend as v
class Frontend(unittest.TestCase):
 def test_missing_word_blocks_instead_of_silent_omission(self):
  p=T(g2p=lambda text:('',[T(text='Bennett',phonemes=None),T(text='argues',phonemes='arg')]))
  with self.assertRaisesRegex(ValueError,'Bennett'):v.check(p,'Bennett argues')
 def test_known_name_and_punctuation_pass(self):
  p=T(g2p=lambda text:('',[T(text='Bennett',phonemes='bɛnɪt'),T(text='.',phonemes=None)]))
  self.assertEqual(v.check(p,'Bennett.'),2)
 def test_library_and_data_must_exist_as_a_pair(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);lib=root/'library.dylib';data=root/'data';lib.touch();data.mkdir()
   with patch.object(v,'PAIRS',[(lib,data)]):
    self.assertFalse(v.available());(data/'phontab').touch();self.assertTrue(v.available())

import unittest,tempfile,json,subprocess
from pathlib import Path
from unittest.mock import patch
import quality
class QualityRuntime(unittest.TestCase):
 def test_repaired_runtime_rechecks_cached_tool_failure_without_changing_fingerprint(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);folder=root/'video';folder.mkdir();(folder/'final.mp4').write_bytes(b'fixture');(folder/'POST_THIS.txt').write_text('Caption')
   with patch.object(quality,'CACHE',root/'cache'),patch.object(quality.media_runtime,'environment',return_value={'LOCAL_MEDIA':'verified'}):
    with patch.object(quality.subprocess,'run',side_effect=subprocess.CalledProcessError(1,[])):failed=quality.inspect(folder)
    valid={'format':{'duration':30},'streams':[{'codec_type':'video','width':1080,'height':1920},{'codec_type':'audio'}]}
    with patch.object(quality.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(valid))) as probe:passed=quality.inspect(folder)
    self.assertTrue(passed['can_approve']);self.assertEqual(passed['fingerprint'],failed['fingerprint']);self.assertEqual(probe.call_args.kwargs['env'],{'LOCAL_MEDIA':'verified'})
if __name__=='__main__':unittest.main()

import unittest,re,subprocess,json
from pathlib import Path
class FullPageControls(unittest.TestCase):
 def test_daily_limits_and_active_work_disable_misleading_actions(self):
  page=(Path(__file__).resolve().parents[1]/'index.html').read_text()
  policy=re.search(r'function fullGenerationPolicy\(lane\)\{[^\n]+',page).group(0)
  choices=re.search(r'function eligibleFullBooks\([^\n]+\n[\s\S]*?\n\}',page).group(0)
  js=policy+'\n'+choices+'''
const assert=require('node:assert/strict');
assert.deepEqual(fullGenerationPolicy(null),{build:false,retry:false});
const lane={completed:0,attempts_used:0,attempts_remaining:2,queued:0,running:0};
assert.equal(fullGenerationPolicy(lane).build,true);
assert.deepEqual(fullGenerationPolicy({...lane,attempts_used:1,attempts_remaining:1}),{build:false,retry:true});
assert.deepEqual(fullGenerationPolicy({...lane,attempts_used:2,attempts_remaining:0}),{build:false,retry:false});
for(const state of [{running:1},{queued:1},{completed:1}])assert.deepEqual(fullGenerationPolicy({...lane,...state}),{build:false,retry:false});
assert.deepEqual(eligibleFullBooks([{id:'1',title:'Failed book'},{id:'2',title:'New book'}],[],[{book:'1',state:'failed'}]).map(b=>b.id),['2']);
'''
  node='/Users/USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
  r=subprocess.run([node,'-'],input=js,text=True,capture_output=True)
  self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()

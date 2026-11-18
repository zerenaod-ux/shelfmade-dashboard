"""Preserve worker diagnostics and distinguish outages from invalid story content."""
import json,re
from pathlib import Path
def temporary(log):
    return bool(re.search(r'HTTP Error (408|429|500|502|503|504)\b|(?:TimeoutError|TimeoutExpired|ConnectionError|NoAudioReceived)\b',log))
def record(folder,story_id,log):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    # No environment or request bodies are copied into the metadata.
    (folder/(story_id+'.log')).write_text(log[-32000:])
    result={'story_id':story_id,'temporary':temporary(log),'owner_decision_changed':False}
    (folder/(story_id+'.json')).write_text(json.dumps(result,indent=2))
    return result['temporary']

"""Local pronunciation support for Kokoro Heart; this never synthesizes another voice.
Use a verified installed eSpeak library/data pair, not the bundled loader's stale
build-machine data path. Missing word phonemes stop before audio generation.
"""
from pathlib import Path
import re
PAIRS=[(Path('/opt/homebrew/opt/espeak-ng/lib/libespeak-ng.dylib'),Path('/opt/homebrew/opt/espeak-ng/share/espeak-ng-data')),(Path('/usr/local/opt/espeak-ng/lib/libespeak-ng.dylib'),Path('/usr/local/opt/espeak-ng/share/espeak-ng-data'))]
def paths():
 for library,data in PAIRS:
  if library.is_file() and (data/'phontab').is_file():return library,data
 raise ValueError('Restore the local pronunciation library and its matching data. Words must not be silently skipped.')
def available():
 try:paths();return True
 except ValueError:return False
def configure():
 # Call after importing Kokoro, before constructing its pipeline: misaki's import
 # installs bundled defaults, and this application must replace that broken pair.
 from phonemizer.backend.espeak.wrapper import EspeakWrapper
 library,data=paths();EspeakWrapper.set_library(str(library));EspeakWrapper.set_data_path(str(data))
 return {'library':str(library),'data':str(data),'voice':'af_heart','role':'pronunciation only; Kokoro generates the audio'}
def check(pipeline,text):
 _,tokens=pipeline.g2p(text)
 missing=[t.text for t in tokens if re.search(r'[A-Za-z0-9]',t.text) and not t.phonemes]
 if missing:raise ValueError('Narration pronunciation missing before audio generation: '+', '.join(dict.fromkeys(missing))[:240])
 return len(tokens)

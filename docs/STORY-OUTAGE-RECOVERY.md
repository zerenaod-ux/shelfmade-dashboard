# ShelfMade story outage recovery — November 18

Two recent story jobs stopped with HTTP 503 and produced zero videos. The wrapper only printed the last 900 characters, hiding the originating request. It also counted temporary service outages toward parking a script as invalid content.

The wrapper now retains up to 32 KB of per-story worker diagnostics plus structured failure classification. Known temporary HTTP/timeout/voice outages leave the story eligible for a later scheduled attempt instead of parking it. Invalid content retains the existing bounded park rule. Always-uploaded diagnostic artifacts preserve the job's drafted stories and queue-state snapshot even if no video is built. No owner decisions or publishing behavior are changed.

Two local regression tests cover outage versus permanent failures and retained root diagnostics. A dedicated no-media cloud check is added. Actual story recovery and the originating service remain unverified until a later diagnostic run; this change does not claim a successful video, guaranteed automatic artifact restoration, or unlimited retries. No generation was triggered for this code change.

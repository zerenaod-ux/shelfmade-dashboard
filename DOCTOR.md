# Doctor (self-healing) — added 2026-11-08
Runs every 3h (doctor.yml). Looks at the latest run of every workflow. If failed:
1. Known harmless cause (quota/network) -> waits, logs it.
2. A code commit made since the last good run AND named in the error log -> reverted.
3. Otherwise the free LLM proposes one tiny exact fix (root .py, <=25 lines, must compile).
Every change triggers a re-run; if it still fails the change is undone and an issue "Doctor: <workflow>" explains. Max 2 attempts per failure.
Never touches .github/, data/, secrets. Kill switch: publish/doctor.json {"on": false}. State/log: publish/doctor.json.
Why: Nov 7 Doodles outage (file packaging.py shadowed pip) would have been auto-reverted by rule 2.
TODO (Mac docs folder was offline): copy this into GROWTH-ENGINE-PLAN.md LOG + DEPENDENCIES.md.

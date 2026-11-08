# DEPENDENCIES & PLAN B (written 2026-11-06) — every free service the 3 systems use
Rule: when A stops, B takes over by itself; when A recovers, A is used again. Canary (deps.py, daily) probes each one and predicts running out.

| Need | Plan A | Plan B | Back to A | Status |
|---|---|---|---|---|
| Script writing (AI) | Gemini | Groq > Cerebras > OpenRouter > Mistral (llm.py) | every call tries A first | DONE |
| Stock footage/images | Pexels | Pixabay (auto, only when Pexels fails) | next search tries Pexels again | DONE 2026-11-06 |
| GPU voices+pictures+lip-sync (Doodles) | Kaggle GPU | lip-sync -> fast mouths only; voices/pictures none | - | OUTAGE MODE DONE 2026-11-06 (story handed back, run stops, alert); full CPU fallback not possible (pictures need GPU) |
| Review video hosting | Cloudinary (free credits) | GitHub release file link | next upload | PLAN: build fallback in review_publish; credit guard + prediction DONE |
| Instagram/TikTok posting | Buffer | none (posts wait + retry) | - | GAP (no free alternative with API) |
| YouTube posting | YouTube API (full) / Buffer (Shorts) | each covers the other for Shorts only | - | PARTIAL |
| Compute/schedule | GitHub Actions (public repo, free) | self-kick + retry-once (kick.py) | - | DONE |
| Phone pages | GitHub Pages | GitHub Issues approve/skip | - | DONE |
| Decisions while owner away | owner | Autopilot (switch) | owner turns OFF | DONE |
Next builds, in order: (1) Cloudinary->GitHub release fallback, (2) Pexels second source + cache, (3) Kaggle outage mode (reuse approved stock of finished stories / pause Doodles gracefully), (4) CPU voice fallback.

- GitLab (backup of GitHub): private contentempire1/shelfmade-backup, daily mirror.yml. If GitHub is lost: restore from branch `backup`. Token expires 2027-11-05.

- YouTube Data API quota: 10,000 units/day shared by all 3 channels. Heavy writers: retitle.py (50/update), flywheel.py (50/add), first_comment.py (50/comment). If "quota" errors appear, wait for ~08:00 UTC reset; retitle self-heals.

## Doctor (self-healing) — 2026-11-08
Needs only GitHub Actions (free) + existing free LLM keys (Gemini/Groq/Cerebras/Mistral/OpenRouter). Works with the laptop off. If all LLM keys die, rollback + playbook still work; AI patch is skipped.

# GROWTH ENGINE PLAN (owner gave full ownership 2026-11-06 19:00 CT)
READ THIS FIRST when continuing. Update the STATUS column + "LOG" at the bottom after EVERY step, then update README/MASTER-ROADMAP/SYSTEM/CHANGELOG/Implementation-history with one line pointing here.
Goal: make the 3 channels (ShelfMade, MindLore, Doodles) produce content people actually watch, follow, comment on and share - automatically, free, on GitHub, hard to kill.
Baseline 2026-11-06 (YouTube): ShelfMade 139 videos/2,741 views/9 subs; MindLore 120/2,972/10; Doodles 20/325/2. Compare every 3 days.
Rules: owner approves/skips only; short replies; push scripts in ~/Dev/_ops/gh-test (patch_*.py + push-*.sh), test on copies first, one command at a time; no secrets in chat; no destructive actions without owner OK.

## Phases (in order). [ ] todo  [~] in progress  [x] done
| # | Phase | What | Files / where | Status |
|---|---|---|---|---|
| A1 | Best-of-3 script judge (Doodles Shorts first) | writer makes 3 candidate stories, a judge prompt scores funny/relatable/hook/loop and only the best is kept (others recycled in pool) | doodles_engine/story_writer.py, new judge fn | [x] PUSHED + live 2026-11-06 (story_writer.pick_best); selfcheck.py verifies judge notes appear after the next Doodles run |
| A2 | Best-of-3 for full episodes + MindLore/ShelfMade Shorts | same judge idea in their writers | episode_writer.py, ml_autoscripts.py, sm scripts | [~] Doodles done. ShelfMade/MindLore long videos skipped on purpose (3x quota + gate chain risk); revisit only if a cheap hook/title-only judge is possible |
| B1 | Video ledger | every posted video tagged: brand, topic, hook type, length, series, publish time -> data/growth/ledger.json | review_publish/publisher + new growth.py | [x] DONE 2026-11-06: growth.py reads YouTube analytics directly (no separate ledger needed) |
| B2 | 24h/72h/7d scoreboard | join ledger with data/analytics; views/day, avg % viewed, subs gained | growth.py + learn.yml | [x] DONE 2026-11-06: data/growth/scoreboard.json + history.json, runs in learn.yml + analytics.yml, Growth card on Health page |
| B3 | Decision engine | winners/losers per feature -> weights + do_more/do_less lines into writers (learned.guidance), auto-retire weak formats | learner.py, hook_learn_gh.py | [x] DONE 2026-11-06: Shorts feature lifts (>=5 with/without, 1.6x/0.6x) -> learned.guidance -> Shorts writers |
| C1 | Leo & Mia series mechanics | running gags memory, cliffhanger, episode numbering, "tomorrow" teaser | series.py, story_writer SPICE | [x] DONE (already built: series.py bible, seasons, milestones, cliffhangers, running gags) |
| C2 | Comment-fed stories | top viewer comments/questions -> next story seeds | reply_helper.py + story_writer | [x] DONE 2026-11-06: comment_ideas.py (daily in reply-helper.yml) -> data/doodles/comment_ideas.json -> story_writer uses viewer topics first. Awaiting first live comments |
| D1 | Owned audience | email list + free guide per channel (needs owner accounts) | owner + bio page | [-] SKIPPED by owner 2026-11-06 (no email list; Brevo free plan was the option, needs a public mailing address) |
| D2 | Monetization ladder | Amazon links (done), YouTube Partner thresholds tracker, sponsors later | affiliate.py, growth page | [x] DONE 2026-11-06: Partner thresholds tracker in scoreboard + Health card (ShelfMade 9/1000 subs, MindLore 10, Doodles 2); Amazon tag shelfmade-20 live. Sponsors later |
| E1 | Resilience | Plan B per dependency (DEPENDENCIES.md), autopilot, canary | deps.py, autopilot.py | [x] mostly done 2026-11-06 |
| E2 | Mirror/backup of code+state | needs owner's 2nd account (GitLab/Codeberg) | - | [x] DONE 2026-11-06: private GitLab project contentempire1/shelfmade-backup (branch `backup`), mirror.yml daily 04:47 UTC, secret GITLAB_MIRROR_TOKEN (project token, write_repository, expires ~2027-11-05 -> RENEW), selfcheck watches it |
| F1 | More languages (Spanish...) | after one channel shows growth | - | parked |

## How to resume (any session)
1. Read this file, DEPENDENCIES.md, MASTER-ROADMAP.md tail, CHANGELOG tail.
2. Pick the first phase not [x]. Build the smallest testable piece, test on copies (VM path ~/mnt/repos--shelfmade-dashboard is the Mac clone; never edit it directly - use patch scripts).
3. Give owner ONE push command. After PUSHED verify live (browser JS fetch to api.github.com), then mark status here.
## LOG
- 2026-11-06 19:00 plan written. Starting A1.
- 2026-11-06 19:20 A1 built+tested on copy (stubbed LLM): story_writer.pick_best (3 candidates, judge scores funny/hook/spoken/relatable/loop, keeps best, stores judge info in story; judge failure => first candidate, never blocks). Caught+fixed a real bug in test (os not imported). Env DOODLES_BESTOF=3 (1 = off). Cost: ~4 LLM calls per story (free chain). Pending push-bestof.sh; verify on next Doodles run log "best-of-3: kept ...".

- 2026-11-06: B1-B3 live (commit 9ee430e, 4cf0880). First run saved data/growth. ShelfMade: no-emoji 11.4x, question titles 7.6x, <=30s 6.8x. A2 long videos deferred. Next: C1 series, C2 comment-fed stories.
- 2026-11-06: C1 confirmed existing; C2 pushed (comment_ideas.py, story_writer._viewer_topic, reply-helper.yml + doodles.yml commit the file). Next: D1 owned audience (needs owner), D2 monetization tracker, E1/E2.
- 2026-11-06: D2 pushed (growth.py monetization block + Health card line). Remaining: D1 (owner accounts), E2 (owner 2nd account), F1 parked, A2 long videos deferred. Verify dates: Nov 7 Doodles run, Nov 12 token test.
- 2026-11-06: SELF-CHECK built (selfcheck.py + selfcheck.yml, daily 14:17 UTC -> publish/selfcheck.json). Checks scoreboard fresh (auto re-runs analytics.yml), Doodles run ok, best-of-3 judge visible, Kaggle ok. Opens/closes its own ALERT issues. Rule: never "I will check" - every new feature gets a check here.

- 2026-11-06: B3 now ACTS: growth.fix_title strips emoji from Shorts titles (gh_story_short*.py) when scoreboard lift <=0.6 with >=5 videos (ShelfMade 0.09x, MindLore 0.46x today). selfcheck got free-tier-room check (>=80% -> ALERT) and a Self-check card on Health. First selfcheck run: all ok.

- 2026-11-06 19:34: owner SKIPPED D1 (owned audience/email). Do not ask again.
- 2026-11-06 20:00: E2 backup LIVE and verified (first run success, files visible on GitLab). RESTORE: clone gitlab.com/contentempire1/shelfmade-backup branch backup into a new GitHub repo; re-add secrets. GitLab trial ends ~Dec 6 -> auto-drops to Free, repo stays. Token renewal before 2027-11-05.
## PHASE G (started 2026-11-06 20:05, owner said: "build, come back when done")
| # | What | Where | Status |
|---|---|---|---|
| G1 | Packaging: underperforming videos get 2 stronger title options; owner approves by label, system applies via YouTube API | packaging.py, title-apply workflow | [x] BUILT+pushed 2026-11-06: packaging.py (weekly Wed) -> issue "Title proposals <brand>"; owner label titles-approved applies option A via title_apply.py/title-apply.yml (owner-only trigger), titles-revert undoes; log data/growth/title_log.json |
| G2 | Hook tester: retention (avg % viewed) lift by hook style feeds the writers | growth.py | [x] DONE: growth.py hook style feature + retention (avg % viewed) lifts -> learned.guidance "HOLDS VIEWERS LONGER" |
| G3 | Viewer flywheel: Shorts point to next episode/full video; playlists if API scope allows | first_comment.py / flywheel.py | [x] BUILT+pushed: flywheel.py + flywheel.yml daily 16:11 UTC, auto Shorts/full playlists per channel (max 6 adds/list/run), first_comment.py already points Shorts to the full video |
| G4 | Safety: per-channel kill switch + daily post cap | autopilot.py / review_publish.py | [x] DONE: guard.py + publish/guard.json (kill switch + max_new_per_day, default 12) read by publisher.py and yt_publish.py; guard.yml flips it from the GitHub app (channel, on=STOP/off=resume) |
| G5 | Weekly plain-words report issue | weekly_report.py + workflow | [x] DONE: weekly_report.py + weekly-report.yml Monday 14:07 UTC -> issue "Weekly report <date>" |
Rule: every G item gets a selfcheck.py entry and a LOG line here. Stop only when all five are [x].

- 2026-11-06 20:30: PHASE G all built, pushed (479df4b, 4a74d87, c7de68f) + selfcheck entries for guard, weekly jobs, flywheel. First live runs dispatched; results in selfcheck.json. Limits: title swaps need owner label; end cards cannot be made via API (manual in Studio); kill switch does not recall posts already waiting in Buffer.
## G6 RETITLE CAMPAIGN (owner request 2026-11-06 21:24: "short, hooky, cautious titles for every video, even old ones")
- retitle.py + retitle.yml (daily 17:31 UTC, RETITLE_LIVE=1). Scope: ShelfMade Shorts only. NOT touched: full videos, Doodles (series identity), proven winners (>=1.5x median vpd), titles already short+hooky (logged as auto-skip).
- MindLore PAUSED: canary of 4 gave weaker rewrites than the originals; the 4 changes were reverted (workflow retitle mode revert-mindlore). Re-enable only with a better prompt/judge (BRANDS tuple in retitle.py).
- Pace: guard.json retitle_per_run = 8/day. ~58 ShelfMade Shorts to go (about 7 days). Every change logged in data/growth/title_log.json (source auto) with the old title. UNDO ALL: run workflow retitle with mode revert-all.
- Quality watch: some rewrites replace decent titles (e.g. Aristotle one). Next improvement: judge old vs new before applying (best-of-2) and measure views/day before vs after (scoreboard) -> keep what wins.
- 2026-11-06 21:50 LIVE: canary done (7 ShelfMade titles changed, 4 MindLore reverted).

### G6 update 2026-11-06 22:00 (retitle v2)
- Owner: "make the algorithm smarter, replace ALL titles with better, shorter QUESTION titles". Done as v2: 4 question options per video (2-6 words, <=42 chars, must end with ?) -> judge compares them with the current title (grammar/true/curious/clear) -> only clearly better ones applied -> final grammar proofreader. If the judge/proofreader fails: nothing applied, retried next run. Scope: ShelfMade + MindLore Shorts (MindLore back on with the judge). Doodles excluded (series identity). Proven winners (>=1.5x median) protected.
- First v2 batch changed 44 titles; 4 were bad (one cut off "Why does the mind miss m?") -> reverted/being reverted; proofreader added.
- LESSON: YouTube Data API quota (10,000 units/day, ALL channels share one project) ran out: videos.update = 50 units, playlistItems.insert = 50, comments 50. Budget: retitle 20/brand/run x 2 runs (09:07 + 17:31 UTC), flywheel 6/list/run. Quota resets ~08:00 UTC. retitle now stops on quota and self-heals failed reverts (revert_error in title_log.json).
- Undo everything: workflow retitle, mode revert-all (or revert-mindlore, or ids:ID1,ID2).

### G6 update 2026-11-06 22:10 (owner approved the results: "perfect, attractive, short, simple")
- Scope now: ShelfMade + MindLore, SHORTS AND FULL VIDEOS (full: 3-9 word questions, max 62 chars; shorts: 2-6 words, max 42). Winners protected per format. Doodles excluded.
- Memory: data/growth/title_log.json remembers every change/keep (source auto / auto-skip v2); a video is never retitled twice. Test: 40 of 72 ShelfMade eligible were skipped as already done.
- Schedule: retitle.yml 09:07 and 17:31 UTC daily; NEW videos are picked up automatically the same way. Status: data/growth/retitle-status.json + weekly report line (changed / kept / waiting).
- Remaining at launch: ~13 ShelfMade + ~44 MindLore after the next run -> finishes in ~2 days by itself. Self-heals failed reverts and YouTube quota stops.

- LOG 2026-11-08 INCIDENT: my file packaging.py shadowed pip's `packaging` -> Kaggle CLI crashed -> Doodles made no videos Nov 7 (2 failed runs; outage mode worked: story released, nothing lost). Fix: renamed to title_packaging.py (ac03d71) + selfcheck "no module shadowing" guard. RULE: never name a repo-root .py after a pip/stdlib module.
- LOG 2026-11-08 INCIDENT 2: shelfmade-story-short failed 3x: saved cover headline didn't connect to hook (creative review blocked st-261105-5ebb9 / d0007). Fix fc637f0: fall back to hook-derived headline. Re-run dispatched; watchdog failures were just it reporting those two problems.
- LOG 2026-11-08 DOCTOR: doctor.py + doctor.yml (every 3h, free). Reads failed run logs -> playbook (quota/network: wait) -> rollback of code commit named in the error -> tiny AI patch (root .py, <=25 lines, must compile) -> re-run to verify, undo if still failing, issue "Doctor: <workflow>". Max 2 attempts. Kill switch publish/doctor.json {"on":false}. Never touches .github/, data/, secrets. Details in repo DOCTOR.md.

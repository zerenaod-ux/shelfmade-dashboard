# Studio publishing status — November 17, 2026

Enhanced the existing How It Ticks Health card rather than adding a second publishing screen. It is now first in Status and has a Home shortcut. YouTube, TikTok and Instagram each show Ready, Scheduled, Published and To check counts plus expandable video titles, Chicago posting times, watch links and channel links. Old owner-held records are excluded from Ready. Past due dates never count as publication; only Buffer-confirmed sent status does. Missing/partial/stale data is labeled rather than shown as reassuring zeros.

Both phone and laptop use this same responsive hosted page and shared verified snapshot. The app shell cache is versioned and checks updates on open/foreground; existing open sessions get a reload notice rather than an unexpected reload during a review. Saved-folder wording no longer incorrectly claims approved videos cannot already be published. Other channels retain their existing status views.

Data source: content-engine/data/scenes/publishing-status.json, read-only Buffer verification refreshed every 15 minutes and after publishing/review jobs. No credentials are sent to the frontend and the UI performs no publishing/approval mutations.

Validation: three state-model tests passed, inline/external JavaScript parsed, and real Chromium checks at 390x844 and 1280x900 confirmed one How It Ticks card, all three platforms, equal status content and no horizontal overflow. Phone and laptop screenshots were inspected. These checks verify the shared browser layout, not physical access to the owner's phone.


## November 17 — Home and four-system consistency

Home now reads How It Ticks' verified publishing snapshot, including separate Buffer-reported views and their source timestamp. Views cover the recent 20 published posts, may lag about a day, and are not live channel totals. Missing metrics remain unavailable, never invented. Publishing checks run every 15 minutes and after relevant jobs; refresh reads the saved result. The snapshot writer now uses conflict-safe single-file updates rather than a timed-out history fetch.

Home and Channels share the same How It Ticks card. Review totals include all four systems, with missing sources shown as unknown. Legacy scheduled dates are labeled past slots rather than proof of publication. Shared layout verified at 390 and 1280 pixels without horizontal overflow; four model tests pass. Studio app name and shell version updated for both devices. No approvals, publishing decisions or generation settings changed by this UI update.


## November 17 — four-system operational comparison

The existing Automatic jobs panel now includes both repositories, with readable How It Ticks job names, latest running/failure results, and a separate experimental-workflow note. Unavailable data is not labeled healthy. Direct channel links were added to the shared How It Ticks Home/Channels card. Identical simultaneous data reads share a request without caching away subsequent refreshes. Review lists use the same bounded pagination as review counts; incomplete lists show an error instead of silently hiding older cards. The top view-total tile explicitly describes the first three systems, since How It Ticks' recent-post Buffer metrics are not the same cumulative measure.

Seven model/actual-source tests pass, including pagination failure and request sharing. Phone and laptop Status layouts have one How It Ticks card and no horizontal overflow. The publisher's main workflow separately now checks Saved after review filing, retaining scheduled fallback and manual approval; save failure is explicit. Existing failed cinematic and legacy filing jobs remain visible and are not claimed fixed by this audit. Detailed direct YouTube analytics for How It Ticks are not connected by this change.


## November 17 — production documentation continuity

Added PRODUCTION-UI-DESIGN.md to record current deployed screens versus pending original-full-video presentation. Main Content Engine README, SYSTEM-STATUS and PRODUCTION-PLANNER now record the 40–70-second shorts rule, original 2–5-minute landscape requirement, full-history system-selected topic proof, completed filing/narration recovery and remaining mechanism-detail work. The existing long generator is explicitly identified as a compilation, not the replacement. This documentation commit does not change UI runtime or publishing settings.


## November 17 — overlapping playback prevention

The shared Studio app now pauses other audio/video when one review player starts. Supported browsers coordinate other Studio tabs using BroadcastChannel; single-document enforcement still works without it. Leaving the page pauses playback. This prevents a source of overlapping old and new narration; it does not claim the demonstrated overlap was proven to originate from the encoded media. Two unit tests cover active-player preservation, other-tab messages and page exit. No approvals, video files, generation or publishing settings change.


## November 17 — production stages and automatic recovery

The existing How It Ticks Status card now shows tracked daily shorts, experimental shorts and original full-video stages, attempt, source update time, recoverable service holds, retry eligibility time and content/configuration errors requiring attention. No duplicate dashboard. Source is the engine's persisted data/operations/latest.json, without credentials or raw logs. The no-media automatic recovery test passed live on attempt 2 after the coordinator resumed its intentionally failed first attempt. This proves the recovery path, not arbitrary video quality. Phone/laptop preview checks passed with one How It Ticks card and no overflow. The job list distinguishes original full production from the legacy compilation and includes recovery verification. How It Ticks manual approval remains unchanged.


## November 17 — latest verified handover

The live Status card now reads tracked short/full production stages and explicit retry/attention states. The recovery self-test passed automatically on its second attempt; it generated no media. The new hydraulic short technically completed and was delivered, but inspection rejected it as a novelty proof because a plural-title bug let an already covered subject through. Its card and operational status are marked accordingly. Do not label this output a new-topic success. Targeted full-narration repair and plural-aware coverage are saved in the test branch; new cloud proofs still need inspection. No original full video is yet verified. Complete ongoing reference: https://github.com/zerenaod-ux/content-engine/blob/main/docs/RECOVERY-AND-QUALITY-HANDOVER.md . Existing owner decisions and publishing switches remain unchanged.

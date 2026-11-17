# Studio publishing status — November 17, 2026

Enhanced the existing How It Ticks Health card rather than adding a second publishing screen. It is now first in Status and has a Home shortcut. YouTube, TikTok and Instagram each show Ready, Scheduled, Published and To check counts plus expandable video titles, Chicago posting times, watch links and channel links. Old owner-held records are excluded from Ready. Past due dates never count as publication; only Buffer-confirmed sent status does. Missing/partial/stale data is labeled rather than shown as reassuring zeros.

Both phone and laptop use this same responsive hosted page and shared verified snapshot. The app shell cache is versioned and checks updates on open/foreground; existing open sessions get a reload notice rather than an unexpected reload during a review. Saved-folder wording no longer incorrectly claims approved videos cannot already be published. Other channels retain their existing status views.

Data source: content-engine/data/scenes/publishing-status.json, read-only Buffer verification refreshed every 15 minutes and after publishing/review jobs. No credentials are sent to the frontend and the UI performs no publishing/approval mutations.

Validation: three state-model tests passed, inline/external JavaScript parsed, and real Chromium checks at 390x844 and 1280x900 confirmed one How It Ticks card, all three platforms, equal status content and no horizontal overflow. Phone and laptop screenshots were inspected. These checks verify the shared browser layout, not physical access to the owner's phone.


## November 17 — Home and four-system consistency

Home now reads How It Ticks' verified publishing snapshot, including separate Buffer-reported views and their source timestamp. Views cover the recent 20 published posts, may lag about a day, and are not live channel totals. Missing metrics remain unavailable, never invented. Publishing checks run every 15 minutes and after relevant jobs; refresh reads the saved result. The snapshot writer now uses conflict-safe single-file updates rather than a timed-out history fetch.

Home and Channels share the same How It Ticks card. Review totals include all four systems, with missing sources shown as unknown. Legacy scheduled dates are labeled past slots rather than proof of publication. Shared layout verified at 390 and 1280 pixels without horizontal overflow; four model tests pass. Studio app name and shell version updated for both devices. No approvals, publishing decisions or generation settings changed by this UI update.

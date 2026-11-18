# Four-system health audit — November 18, 2026

Verified from current GitHub jobs, publisher logs, shared selfcheck, approval labels and a read-only Buffer refresh around 1:11 PM Chicago. Workflow success is operational evidence, not a full video-quality or human-listening approval.

| System | Working | Current gap |
|---|---|---|
| ShelfMade | Latest full-video run 44364498987 actually built one package; review and publisher jobs succeed. | Latest story-short run 44353085941 produced zero videos after HTTP 503 failures. Diagnostic retention/transient-aware handling is deployed and tested, but successful subsequent short recovery is unverified. |
| MindLore | Latest 2D and story-short generation, review filing and publisher jobs succeeded. Publisher booked two additional YouTube posts. | No new hard failure found in the checked paths; this does not certify every finished video's creative quality. |
| Animation Doodles | Daily run 44350254520 generated the older chair/toaster videos; normal publisher is active and added bookings. | Isolated expression proof 44374678352 remains in generation with no accepted new-policy story or finished expression clip verified at this audit. The earlier proof failed before media. Regular expression default remains off. |
| How It Ticks | Approved check-valve video now scheduled once on all three platforms after publisher recovery; auto-approval remains off. Buffer confirms the hydraulic video sent to YouTube today. | Latest daily generation 44363993361 remains needs_attention after script-length rejection; targeted repair passed cloud tests but a subsequent actual successful run is not proven. Full-video creative standard remains unmet and owner-skipped. |

## Cross-system findings

- Shared selfcheck is warning, mainly due to its Doodles GPU-budget calculation. Its claimed 49.2 hours sums GitHub workflow created/updated elapsed time, including waits/CPU work. It is not measured Kaggle GPU consumption. The conservative cap is two stories per batch; do not report this as verified GPU-quota exhaustion or automatically lift that cap on this evidence.
- Shared publisher logs show future queues for the three older channels. ShelfMade's latest publisher correctly scheduled zero extra posts because its daily cap was reached; this is not a posting failure. Publisher queue-entry counts are not necessarily counts of finished unique videos.
- How It Ticks publishing snapshot refreshed at 19:11 UTC: YouTube three sent/two scheduled, Instagram two sent/three scheduled, TikTok two sent/three scheduled among returned recent records. These are Buffer statuses, not native audience analytics.
- How It Ticks operations/latest still says the latest full test awaits review even though its actual card 54 is closed with the owner's ce-skip. This is stale lifecycle reporting; the owner Skip must remain authoritative and must not be reset.
- The fifteen-minute Codex heartbeat remains deleted as requested. Existing cloud schedules and recovery coordinators remain separate. This audit did not create new publishing bookings, alter owner decisions or enable expression rollout.

## Next work

Finish the isolated expression test and inspect its actual media. Separately, restore successful ShelfMade story-short and How It Ticks daily-short generation, correct misleading GPU/lifecycle reporting, and verify outputs before declaring those paths healthy. No claim that all four systems are fully healthy is warranted.

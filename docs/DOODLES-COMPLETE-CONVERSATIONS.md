# Animation Doodles complete-conversation shorts — November 18, 2026

## Owner requirement

Keep the current visual style and characters. Future shorts should sound like everyday friends, have a complete mini-story and satisfying ending, and measure 40–70 seconds. Natural reactions and playful teasing are welcome; forced slang, cruelty, formulaic roasts and padding are not required.

## Implemented production changes

- The short writer uses six story beats with one to three conversational turns per shot, targeting 125–165 spoken words and roughly 50–60 seconds. The old micro/tight rotation is disabled for future shorts. Actual measured duration overrides the word proxy.
- The final reply must be a complete sentence and resolve the situation. The forced unfinished-question replay loop, part-two format and cliffhanger ending choice are removed from the short path.
- The editor now scores spoken naturalness and the ending, requires explicit natural/complete findings and scores of at least seven, including for a single candidate. Missing editor evidence is held instead of selecting the first unchecked candidate.
- Old queued scripts are retained but are not selected under the new policy. Existing generated videos, owner approvals and publishing bookings are not changed.
- After cloud voice generation, measured dialogue must be 40–70 seconds before expensive lip-sync. It is never extended with padding or shortened by cutting speech. A failing story is held through the existing bounded failure handling.
- The renderer preserves the entire final voice file, keeps more trailing quiet audio on other lines, and leaves a 0.9-second reaction on the final scene. This tail does not introduce an outro card or follow request.
- Final MP4 audio/video presence, duration, final-line coverage, reaction time and full decode are checked before packaging. DIALOGUE-QUALITY.json is included in successful short packages. All-failed batches fail visibly.
- Full episodes explicitly retain their separate scene contract; these short-duration rules do not force full episodes to 40–70 seconds. No new video or external voice request was started by applying this change.

## Evidence and limits

Seven local regression tests pass with authored fixtures and synthetic PCM only: complete versus dangling endings, old short scripts, missing/failed editor evidence, finite score checks, measured duration boundaries, missing/truncated encoded tracks, final quiet phoneme preservation and single-candidate review. No model request or finished production video was generated in these tests. Dedicated GitHub verification is pending at this commit. The next actual automatic short still requires inspection for conversational quality, performance and a satisfying ending; tests cannot guarantee human-like dialogue or subjective humor.

The existing GPU/voice/image/lip-sync services and Studio review/publishing decisions remain in place. The fifteen-minute Codex monitor stays deleted at the owner's request.

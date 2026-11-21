# Implementation plan and acceptance

## 0. Reconcile
Read live repository instructions/code/tests. Compare inventory hashes, identify canonical workflow/store and dependencies, confirm local ASR/FFmpeg/Adobe/bridge without exposing credentials. Preserve existing work.

## 1. Source map and decisions
Implement durable source-backed events, restore/rebuild, revision approvals and insertion-aware maps before production cuts.
Test bounds, rational FPS, frame edges, source-contiguous splits, room-tone additions, offsets, long-recording drift, deterministic reruns, restart persistence, stale approvals, cancellation/retry.

## 2. Native master
On copied reference projects implement supported effect read/write, framing/masks, native frame export and shared-nest route. Keep the shadow independent.
Test typed values/readback, actual pixels, hair/matte/motion, one-key-change across distant cut pieces, shadow preservation, sync, nesting/audio routing, save/reopen/relink. No generic preset assumed correct.

## 3. Decision policy and review
Integrate context/take reasoning with acoustic proposals. Protected spans override acoustic deletion. Build full transcript and event cards, plus original-versus-join clips.
Test retained pauses protected; cough beside soft word; intentional repeats; abandoned takes; missing ASR words; all removals discoverable; uncertain labels explicit. Compare both fixture datasets and manually listen to disagreements. CPU local fallback must work; missing model blocks rather than switches to paid cloud.

## 4. Apply approved cut
Check approval digest immediately before mutation. Generate new native sequence from immutable baseline. Backup/read back all tracks.
Test Restore, every-piece mic sync, no slivers/gaps/overlaps/camera audio, no flattened duplicate shadow, interruption recovery and manual-edit preservation. Compare actual render joins with approved preview/map.

## 5. Animations and final assembly
Connect existing deck/style/shot-list/render machinery to approved cut. Add creative notes and storyboard review. Use composite-aware PiP source.
Test script changes invalidate visual timing, notes persist, anchors match after room tone/cuts, alpha edges/resolution correct, mic maintained. Trigger local native export; verify file, metadata, representative playback and editable project reopen.

## 6. Optional external review
Only after local flow works, connect authorized Discord/Frame.io routes. Test recipient/project/revision, attachment accessibility, duplicates, cancellation, upload failure. Bot presence or API endpoint isn't operational proof. No new external upload audience during local testing.

## Done means demonstrated
Show one full test project where Josh can restore material, approve, generate the cut, adjust the master key and see changes everywhere, retain independent shadow, add animation notes, approve visuals, export locally and reopen the final native timeline.
Deliver code/test evidence, project/media manifest, decisions/maps, parameters, render receipts, output and remaining limitations. Label unit/mock/native/visual/listening checks separately. Don't collapse untested stages into "all passed."

## Boundaries
Target selected project folders and structured runners. No arbitrary whole-PC shell authority. No credentials/account/campaign/OBS/camera/mic changes. Do not close apps or bypass recording safeguards for tests. Do not silently install software or accept security prompts. Public publishing is separate.


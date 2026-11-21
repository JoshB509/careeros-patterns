# Existing system and integration
JoshOS: E:\Videos\DaJoshiResolve
Josh Cut Pro / DaJoshi Cut: E:\Videos\DaJoshiCut

Installed panel manifest inspected here is version 0.8.7, UXP manifest v5, ID com.careeros.dajoshicut, minimum Premiere 25.6.0. Prior native inspection reported Premiere 25.6.6. Recheck live versions before implementation.

## Code to study
- DaJoshiCut/helper/dajoshi_cut.py: server, jobs and processing orchestration.
- helper/transcribe_worker.py: isolated local faster-whisper process.
- helper/cleancut.py: energy and word-boundary planners.
- helper/layers.py: source anchors/output mapping.
- helper/deck.py, render.py, style.py, pip.py, prompts.py: animation pipeline.
- app/app.js, index.html, app.css: tools and transcript UI.
- panel/index.js and manifest.json: native Premiere UXP bridge.
- DaJoshiResolve/dajoshi/timing.py, clean_cut.py, staged_cut.py: revision-aware source maps, explicit removal and staged review.
- studio/workflow.py, jobs.py, server.py: app integration.
- studio/edit_review.py, render_edit_review.py: storyboard/press review.
- studio/discord_bridge.py: communications routing. Do not read/export secrets unnecessarily.
Hashes/size/existence are in source-code-inventory.json.

## Existing bridge
Commands observed: timeline, cut, layers, probe and XML import. It reads effect chains and internally changes Motion for PiP. It does not expose the complete Ultra Key/preset/still-export workflow.
Current cuts subtract source ranges from the open sequence after backup. Affected clips are rebuilt from fresh copies; retained parts are trimmed and moved, with fresh object lookup after edits. Preserve native timebase and post-edit readback practices. Do not assume old raw-camera editing also handles nested composites safely.

Current transcript selections and Claude retake proposals are separate from acoustic Clean cut. Pauses and nonverbal sounds are not first-class inline decisions. Current app startup supersedes prior choices, which conflicts with persistent new review.
Keep after a destructive cut does not restore media. New workflow needs immutable baseline regeneration.

## Nested composite risk
Current copyCamera matches the camera path across V1–V3 and copies matches to one destination track. Data has overlapping presenter and shadow uses of the same source. This is a static-code risk, not a reproduced failure. Explicitly select a designated composite/nest and preserve its layers; never flatten all matching camera clips to one track.

## Existing staged work
studio/workflow.py currently states visual assembly is not connected and final visual export is pending. staged_cut.py retains untranscribed sounds and protects word handles, but it does not solve semantic retakes/cough intent. Its thresholds are not a validated study-derived policy.
Review audio fades in this path are not necessarily represented in XML output. Ensure native output matches the reviewed joins.

## Local ASR verified
transcribe_worker.py imports faster_whisper, sets HF_HUB_OFFLINE=1 and constructs WhisperModel with local_files_only=True. It processes 16 kHz float PCM and returns word timestamps.
Saved Projects/whisper-ok.json inspected on 10 November selected CPU, int8, four threads, unbatched, beam 1. This proves a local backend is configured; no claim of successful GPU acceleration.
Repository guidance describes CUDA-batched then CPU-batched/plain fallbacks after native crashes. Verify actual installed dependencies/model/config. Do not copy historic "no CUDA" as a permanent PC fact and do not silently switch to paid cloud.

## Tests and user activity
Review tests/replay-cut.py, replay-orders.py, layers-flow.py, ui-inplace.py and panel mock. A mock cannot certify native key pixels, saved project roundtrip or playback.
Use isolated test folders/spare helper port. Do not restart apps, close OBS, modify the user's open sequence or reset live choices just to test. Coordinate real-app tests safely.


## Exact implementation entrypoints and high-priority hazard
In helper/dajoshi_cut.py inspect prepare(), whisper_attempts(), transcribe_in_child(), start_transcription(), ensure_transcript(), plan_cut(), run_silences(), run_flubs(), run_apply(), flubs_view() and fresh_start().
In helper/cleancut.py inspect db_profile(), levels(), acoustic_keeps() and word_cuts().
In app/app.js inspect renderFlubs(), loadFlubs() and runFlubs().
In panel/index.js inspect readTimeline(), cutInPlace(), copyCamera(), placeLayers() and COMMANDS.

ReadTimeline currently includes all matching camera-file clips on V1–V3, including Data's shadow and presenter. Helper timeline_mapping() does not deduplicate them, and layers.Cut.source_pieces() iterates them. copyCamera() clones matching clips to the same destination track/time without role selection or a composite nest. placeLayers() can fall back to raw media when copying fails, which loses the key/look.
The new path must explicitly designate source roles/nesting, reject overlapping duplicate source spans where inappropriate, and STOP with a useful error rather than silently fall back to unkeyed raw media. Preserve the original composite and verify PiP with a real Data-style shadow+presenter stack. This risk is established from static code inspection; no production failure was intentionally reproduced.

Additional JoshOS files:
- studio/workflow.py: status(), register_pass1(), import_cut(), import_map(), revise_cut(), approve(), handoff().
- studio/web/workflow.js: staged review UI.
- specs/CORE_EDITING_CAPABILITIES.txt: capability declarations to reconcile.
- studio/agent.py: apply_edit(), apply_edit_elsewhere(), _deck_job().
- studio/discord_bridge.py: Bridge and allowed(), routed via studio/server.py.
- studio/web/edit-review.js: animation review.
The latest config-metadata inspection found Sam configured, not Tariq. Do not read/copy the token-bearing config for documentation. No Frame.io code was found in the targeted inspection. These are setup/integration gaps, not permission to create accounts or expose credentials.


# Data and review contract
Proposed interfaces. Adapt them to the existing store/schema rather than create competing state.

## Identity/time
Stable IDs for project, media, transcript words, events and revisions. Store hash, duration, rational frame rate, audio sample rate/channels, model/config and origin. Preserve camera and mic clocks and their verified offset/mapping.
Use integer frames or native ticks for video and sample indices for audio. Inspected Premiere uses 254016000000 ticks/s; verify actual sequence timebase. Display seconds are not primary IDs. Preserve original→sync→nest→cut→final maps. Additions and holds need explicit provenance.

## Proposed event record
event_id, project_id, media_id, transcript_revision, parent_decision_revision, kind, source_clock, source_start/end, applied_frame_start/end, word_ids, text/label, measurements, evidence, proposed_action, proposed_bounds/target_duration, user_action, reason, uncertainty_reasons, reviewer/time, preview_ids, output_locations.
Kinds: speech, take_group, pause, cough, throat_clear, breath, other_sound, room_tone_insert, boundary_issue. Label confidence differs from confidence to remove.
Keep/Remove/Shorten/Restore act on source spans. Text correction must not silently alter timing.

## Revision state
Sources registered → Sync verified → Green candidate/checked → Edit proposal → Script approved → Native cut built → Visual proposal/approved → Final assembly validated → Export requested/completed/verified.
Blocked/failed/cancelled states preserve last-good outputs. Each approval stores digest and dependencies. Jobs check revisions before work and commit. Stale approvals cannot apply to a newer proposal.
Changing source/script/key invalidates relevant dependent previews, maps and approvals. Do not overwrite Josh's manual Premiere edits; make a new revision or an explicit merge decision.

## Transcript UI
Show all text, including removals; allow selection/drag, Keep/Remove/Restore, boundary adjustment, undo/redo and persistent notes. Important pauses and sound events appear inline with labels, durations and decisions.
The uncertainty queue prioritizes attention but never hides the full transcript. Each card shows surrounding words, source/output time, original context, proposed join playback, waveform, reason, editable boundaries and decisions. Context length is expandable.
Josh approves a revision as a whole, with unresolved hard errors blocked. Do not force all ordinary default decisions into individual approval clicks.

## Preview generation
Render short local proxies with a few seconds on both sides. For long retakes, show both ends and the proposed join, with a route to longer source context.
Use identical good-mic sync/cut/fades to intended output. Use native Premiere frames/clips for key fidelity, not Python key substitutes. Label lightweight approximations.
Cache by media hash, green/edit revisions, bounds, encoding and overlay version. Changed decisions invalidate previews. Avoid stale clip/new label combinations.
No mandatory full intermediate render.

## Reversibility
Uncut originals and decision history remain. Restore rebuilds from baseline; cannot merely reinsert text into a destructively cut sequence. Persist choices across restart instead of legacy startup superseding.
Handle concurrent JoshOS/Discord/manual changes with conflict checks. Never silently accept stale approval.

## Delivery manifest
Native project path/ID, sequence/master IDs, track roles, audio route, media references, Premiere version, map digest, export preset/version and verification receipts.
Verify variable frame rate and channel layouts explicitly when present. No unintended camera audio.


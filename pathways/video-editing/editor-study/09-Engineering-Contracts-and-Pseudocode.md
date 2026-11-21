# Engineering contracts and implementation pseudocode
These are proposed contracts, not a representation of currently implemented APIs. Preserve existing schema identity where possible.

## Planning must precede mutation
analyse(recording, baseline_revision):
    assert immutable media identities exist
    assert verified camera-to-mic mapping exists
    transcript = local_transcribe_or_cache(media_hash, model_hash, config)
    acoustic = local_measure_audio(selected_mic, declared_clock)
    candidates = discover_events(transcript, acoustic)
    editorial = propose_take_pause_sound_actions(candidates, context)
    decisions = combine_without_overriding_protected_speech(editorial, acoustic)
    validate_ranges_units_and_reasons(decisions)
    save_proposal(decisions, source_hashes, model_and_tool_versions)
    build_local_review_previews(decisions)
    return review_revision

approve(review_revision, expected_digest):
    assert current revision and exact digest match
    assert no unresolved invalid ranges, missing source or sync failures
    persist approval of this revision and dependencies

build_native_edit(approved_revision):
    check approval and dependency hashes again
    keep original project and uncut source master untouched
    create new output sequence from approved baseline
    map retained original source spans to shared master nest and good mic
    add separately represented room-tone spans when approved
    read back all native tracks and compare to expected map
    save native project under new revision
    report output and verification, never overwrite manual revision silently

restore(event_id):
    change source-anchored decision, create new revision
    invalidate dependent preview/cut/visual approvals as needed
    regenerate from original baseline after approval
    never pretend text insertion reverses a destructive timeline cut

## Suggested serialized event shape
All values below are illustrative, not measured source data.
{
  "schema_version": 1,
  "event_id": "stable-source-event-id",
  "kind": "pause",
  "source_media_id": "hash-backed-media-id",
  "coordinate_space": "source_mic_samples",
  "source_interval": {"start": 480000, "end_exclusive": 518400, "sample_rate": 48000},
  "word_ids_before": ["word-001"],
  "word_ids_after": ["word-002"],
  "proposed_action": "keep",
  "review_state": "proposed",
  "reason": "Possible rhetorical beat; preserve pending review",
  "uncertainty": {"label": "unverified", "editorial": "needs_review"},
  "decision_revision": 3,
  "preview_revision": 3
}
Use explicit half-open intervals. A word's stable ID is not its current position in the output list.
Do not fabricate scores. An uncertainty label can be categorical until calibrated data exists.

## Source and output operations
A retained span maps one original interval to output. A removed span has no output interval but remains recoverable. An inserted room-tone span references its own media interval, not the narration source.
The plan must allow more than one output location per source event if the same source is intentionally reused. Never assume every sequence split removes time.
Keep separate precise native ticks and rounded display/frame values. The study's nominal 30 fps does not authorize replacing the actual sequence frame duration (Executive reference ticks/frame 8467191533) with a rounded constant. Preserve original project units until deliberately conformed.

## Request/result boundary
Every queued command should carry project ID, expected revision/digest, selected sequence/master IDs, explicit input paths and output root. Validate path containment, reject stale jobs and return a durable receipt. Do not accept arbitrary model-generated shell commands as an editing API.
A model produces constrained decisions and creative content; deterministic local tools validate/apply them.

## Existing bridge transport to reuse
The helper uses localhost port 47820 by default. The app queues POST /bridge/call, the panel polls /bridge/poll and posts /bridge/result. Test on a spare port using existing configuration mechanisms. Validate exact routes in current code before implementation.
Add typed commands for native effect parameter read/write, frame/snippet export, nested-source construction and saved project verification as needed. Do not assume an Adobe documentation method translates directly to a complete installed command.

## Audio treatment and preview parity
If the review preview applies an audio fade/crossfade that the native sequence does not, the preview is misleading. Either represent the treatment natively or clearly expose it as uncommitted and block completion. Preserve the fixed output clock during fades. Do not hide slip by retiming voice arbitrarily.
If a source clock is outside available mic coverage, explicitly retain/correct the plan instead of padding with unlabelled silence.

## Creative assets
Store Josh's notes with the visual proposal, not only in a transient chat prompt. Bind scene/press IDs to stable source words, then map to output. Record renderer/style version and keep existing design system. Revisions of text, timing or green master must not silently pair with older previews.

## Recoverability
Write manifests atomically, use staging outputs, keep last-good artifacts and verify completed files before marking a stage ready. A process crash leaves a resumable job or failed candidate, never a partially approved edit. Retry uses idempotency keys rather than making another sequence/export each time.


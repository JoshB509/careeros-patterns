# Tariq editing workflow: Claude Code handover
Prepared 10 November 2026 for Josh. This is an implementation specification and evidence package, not a deployed editor.

## Your assignment
Implement a staged local-PC video editing workflow in JoshOS, reusing Josh Cut Pro / DaJoshi Cut and existing animation tools. Josh asks Tariq to edit a video, reviews a full editable transcript and short uncertain-event clips, approves the cut, gives animation notes and approves the storyboard, then receives a finished video and an editable native Premiere project. Preserve originals and make decisions reversible.

Read these documents in order, then the evidence:
1. 01-Product-and-Workflow.md
2. 02-Existing-System-and-Integration.md
3. 03-Premiere-Green-Pass.md
4. 04-Cut-Decision-Engine.md
5. 05-Data-and-Review-Contract.md
6. 06-Implementation-and-Acceptance.md
7. 07-Evidence-Guide.md
8. 08-Source-Conversation.md
9. 09-Engineering-Contracts-and-Pseudocode.md
10. 10-Data-Replay-Inspection-Record.md
11. verified-inputs.json, source-code-inventory.json and package-manifest.json.

CLAUDE-PROMPT.txt is a ready-to-paste starting request.

Read the live repository instructions at E:\Videos\DaJoshiResolve and E:\Videos\DaJoshiCut. Reconcile changes since the inventory. Reuse working subsystems rather than adding an unrelated second editor. Produce a bounded implementation plan, then build in separately testable stages on copies. A button, mock, schema or API definition is not proof of working native integration.

## Required outcome
- Native Premiere Ultra Key, not Python/FFmpeg/AI background replacement.
- A shared uncut keyed master referenced by cut pieces, so adjusting the presenter key propagates throughout the edit.
- A separate soft shadow may use a rough independent key. Latest direction does NOT require its key to match the presenter.
- Better microphone synchronized with camera, no camera-audio leakage and stable source maps.
- Full transcript including retained/removed events, restores, pause choices and uncertain coughs/retakes.
- Lightweight local review snippets, without forcing a full-length render between every stage.
- Approval tied to the exact script/cut revision; animation notes and storyboard approval; final editable native timeline and local export.
- Local transcription, acoustic analysis, timeline construction and rendering where supported. AI calls are for editorial and creative judgement. No silent paid-cloud fallback.
- No public publishing, credential changes, broad PC authority or unrelated modifications.

## Evidence and limits
Both studies measured real projects and waveforms. Neither included perceptual listening or manually verified cough/intent labels. These are development fixtures, not proof of a perfect classifier.
The folder contains reports, measurements, plots, source maps, review WAVs, analysis scripts and copied native reference projects. Large originals and decoded PCM caches stay at verified paths. No credentials/config secrets are included.
Historical scripts/reports are evidence, not instructions to revive an old baked green-screen route. This specification and the latest user direction govern the proposed workflow.

## Safety and preservation
Use structured arguments and scoped project runners. Do not give Tariq arbitrary shell/whole-PC access. Keep originals and manual edits intact. Do not close OBS or bypass real recording safeguards. Old mock-test instructions are not permission to bypass recording protection in production. Obtain any new sensitive access or external destination setup through the supported approval flow.


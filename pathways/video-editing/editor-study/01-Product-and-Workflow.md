# Product intent and staged workflow

## Intake and sync
Josh asks Tariq to edit the selected video. Resolve the camera and good-mic files explicitly; ambiguous similar filenames require clarification. Record immutable media identities, durations, frame rate/timebase, audio channel/sample rate and original paths. Detect and verify microphone synchronization near beginning, middle and end. Preserve an uncut baseline. Do not reuse a study's 3.7 s or 6 s offset for new footage.

## Green pass in Premiere
Build/copy a native composition with background, keyed presenter, framing/desk exclusion and the separate soft shadow duplicate. Start from the actual reference parameters and adjust to this recording. Export real Premiere frames to inspect hair and edges. A dozen distributed frames is an initial sample suggested by Josh, not full temporal proof; check motion and problem areas too.
Save an uncut reusable sequence. Do not bake a rendered keyed file as the only editable master.

## Proposed clean cut
Transcribe locally with word timestamps; cache by media/model/config. Use acoustic gaps, lexical alignment, abandoned takes and nonverbal events as separate inputs. Produce source-anchored decisions. Default Keep/Remove/Shorten choices are allowed, but they remain visible and reversible.
Retained meaningful pauses must appear in the transcript. A removed cough appears as a removed [cough] event; an uncertain one must say [possible cough] or similar rather than claim certainty.

## JoshOS transcript and review cards
Display the whole transcript, including removed text. Josh selects/drags wording to remove, restore or adjust boundaries. Original text remains available beneath the edited view.
Show a slideshow/card queue for questionable coughs, retakes, pauses and speech-adjacent cuts. Give short source context, proposed edited join, reason, waveform and controls. Start with a few seconds either side and allow expansion; do not require a full render.
Josh may approve the current script as a whole; no compulsory click for every trivial event. Hard validity issues, such as unverified sync, block approval. Early versions should expose all proposed pause shortenings, not hide them behind uncalibrated confidence scores.

## Apply the approved cut
Only apply the exact approved revision. Rebuild a new native sequence from the synchronized baseline and approved edit map. Restore must not depend on undoing many destructive edits. Reference the keyed master and route the good mic using the same source map. Read back every track, duration, gap/overlap and source range. Save a new revision.

## Animation stage
Give Josh a place for creative notes before generation. Reuse the existing style/deck/shot-list renderer and slideshow-like review. Bind animation beats to approved transcript/source word IDs and the current output map.
Josh edits/approves the storyboard. If script timing changes, mark affected visuals stale; preserve his notes and regenerate deliberately. Stand-in portraits must be labelled as previews, not proof of final compositing.

## Final assembly and export
After script and visual approvals, assemble the editable Premiere timeline and trigger local Premiere or Adobe Media Encoder through a supported tested route. Verify the actual exported file, duration, audio and representative playback, not merely the job's success flag. Save/reopen the native project with valid media links.
Define what approval means "render this version." Do not add redundant approval clicks or infer public publishing permission.

## Optional review destinations
JoshOS is the primary review interface. Discord can notify and carry transcript/snippet feedback through a configured authorized bot using the same project/revision checks. Frame.io is optional for longer review or flagged material. Neither was verified as an operational component of this workflow during the study. Build/verify each and obtain missing destination/account permission. A full intermediate render is no longer mandatory.

## Local processing and cost
Local faster-whisper, audio decoding, waveform analysis, timeline manipulation and rendering should use the PC. Adobe licensing/hardware are still required. AI analysis and creative generation may incur model usage. Display the actual backend. Missing GPU acceleration does not authorize cloud transcription. Avoid duplicating large renders when a short proxy answers the review question.


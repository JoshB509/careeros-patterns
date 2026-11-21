# Josh Cut Pro

Josh's Premiere Pro auto-editing tool, built on his DaJoshiResolve engine (`E:\Videos\DaJoshiResolve`). It lives in `E:\Videos\DaJoshiCut`. Josh runs a careers coaching business (CareerOS, "Promoted in 6") and films talking-head videos with a camera plus a separate mic WAV. This is a personal tool for his own machine, not a product (yet).

## How it fits together

Three parts talk over `http://127.0.0.1:47820`.

- **Helper** (`helper/dajoshi_cut.py`, Python). Does all the work: transcription, the acoustic clean cut, Claude calls, deck building and rendering, XMEML export. It also serves the app window at `/app/` and runs a bridge queue so the window can ask the Premiere panel to edit.
  - Run with `--serve` it is the server. Run without it, it is a supervisor that spawns `--serve` (output to `Projects\helper.log`), opens the window and restarts the server on a non-zero exit. If a server is already running it just asks it to reopen the window.
  - It uses the DaJoshiResolve venv. The python path is in `E:\Videos\DaJoshiResolve\settings.json`. There's no CUDA on this PC (cublas64_12 is missing), so Whisper runs on the CPU.
  - Transcription runs in a child process (`helper/transcribe_worker.py`) because faster-whisper has crashed natively. It tries cuda batched, then cpu batched, then cpu plain, and remembers what worked in `Projects/whisper-ok.json`. Only one transcription runs at a time. `KMP_DUPLICATE_LIB_OK` must be set.
  - Other helper modules are `layers.py` (word anchors, track plan, overlap planner), `style.py` (styles and PiP shapes as CSS), `deck.py` (assembles the deck with the style kit) and `render.py` (the engine's renderer plus alpha output).
- **App window** (`app/index.html`, `app.css`, `app.js`). This is the Josh Cut Pro program, opened in Edge app mode (`msedge --app=... --window-size=600,780`). Plain JS, no build step.
  - The home screen shows the open sequence plus a grid of tool tiles. The tools are Clean cut, Flubs and retakes, Animations and Styles. B-roll, Zooms and Your look are marked Soon.
  - It calls the helper with `api()`. It asks Premiere to do things with `bridge(cmd, args)`, which goes POST `/bridge/call`, then the plugin long-polls `/bridge/poll`, runs it and posts `/bridge/result`.
- **Premiere panel** (`panel/`, UXP manifest v5, id `com.careeros.dajoshicut`, keep this id so updates install over the top). This is a tiny status panel with an Open button. It runs commands from the bridge. `timeline` reads the open sequence (the recording's clips, every audio track and its offset). `cut` cuts the open sequence in place after saving a backup. `layers` puts the animations on V4 and V5. `probe` checks how this Premiere edits. `import` brings in the old separate animations XML.
  - Josh OS's editing workflow (Tariq's clean cut, `E:\Videos\DaJoshiResolve\studio\edit_flow.py`) uses its own commands, all starting `tq_`. `tq_probe` finds `GREEN_MASTER` and its keyed presenter and shadow tracks. `tq_master_read` and `tq_master_set` read and set the presenter's Ultra Key only. `tq_export_frames` exports real frames. `tq_build_cut` makes a NEW `CLEAN_CUT_rNN` from pieces of the master nest plus the good mic on A1, and refuses to overwrite. `tq_assemble`, `tq_export` and `tq_save` round it off. These never touch Josh's own sequences. If the keyed sequence was already cut (AutoCut), `tq_make_master` rebuilds the master as one uncut take, placing the whole recording, copying every effect setting from the first presenter clip and stretching the background over it. A shadow copy needs a free video track above the presenter, and the master goes on without one if Premiere won't add the track. `tq_ops` (0.9.0) runs a list of small fixed edit steps (make or open a project, import, sequence from media, place, place a sequence as a nest, copy, move, set end, in or out, remove, add an effect, set a setting including colours, read a sequence back, save), and only in a project inside a `Tariq` or `native-test` folder. Josh OS's `studio/edit_master.py` uses it to build Tariq's own project and GREEN_MASTER from the raw files, so the recipe can change without a new panel. Josh OS can start the helper (`--no-window`) and Premiere itself (`wake_premiere` in `studio/edit_flow.py`, never while OBS is open). Premiere loads the panel at launch, and the panel drops off the bridge for a second whenever a project opens, so Josh OS waits for it to come back. `tests/tq-native-stub.py` runs them against the stub with `tests/tq-stub-ext.js` (a mock, not proof in Premiere). The 0.8.7 and 0.8.8 packages are in `Backups`.
  - Package it by zipping the contents of `panel/` (manifest, index.html, index.js, styles.css, icons, not preview.html) into `DaJoshiCut_premierepro.ccx`, which Josh installs by double-clicking. Bump the version in `manifest.json` and `VERSION` in the helper together. Write the manifest without a BOM.
  - `panel/preview.html` plus a fake `ppro` stub lets the panel run in a normal browser for testing.

`Start Josh Cut Pro.bat` launches the supervisor with pythonw, so there's no console.

## Things learned the hard way

- **Clean cut is acoustic.** It uses a 10ms dB profile with an auto threshold (noise floor p10 + 5 dB), 50ms smoothing and phrase merge under 0.15s. It drops clicks under 0.08s and breaths under 1.2s that peak below speech p95 minus 11 dB, then bridges and pads. Whisper word timestamps stretch over breaths, so cutting from the transcript left breaths in. Flub cuts use word times snapped to the quietest 10ms point.
- **Cuts happen in the sequence Josh has open, like AutoCut.** Building a separate "Josh Cut" sequence from the source files put the mic out of sync and brought back camera audio Josh had deleted, so that was dropped in 0.8.0.
  - Each cut first clones the sequence into Josh Cut Pro > Backups. A cut can only take more out, so going back means opening a backup.
  - The helper returns source ranges of the recording to remove (`remove`). The panel maps them through the recording's clips on V1 to sequence time and takes that time out of every track.
  - UXP has no razor. Every clip that changes is rebuilt from fresh copies made past the end of the timeline, one per kept piece. Each copy is shrunk with its in and out points only, then slid into place with `createMoveAction` (negative ticks move it earlier), and the old clip is removed. Each track is worked left to right so nothing gets overwritten. Sliding existing clips along (what 0.8.0 to 0.8.4 did) left Premiere's timeline drawing gaps and blanks during a Flubs cut on an already cut sequence, while new clips draw correctly.
  - Cuts are snapped onto any clip edge within a frame, cuts less than a frame apart merge, and pieces under half a frame are dropped. Otherwise a flub ending next to a Clean cut join left a zero-length clip that got stacked on its neighbour.
  - The tools work in any order. Each one works out its cuts in the recording's own time and finds those moments wherever they sit on the timeline, so Flubs then Clean cut and Clean cut then Flubs come out the same.
  - Premiere hands back a new clip object after every edit, and using the old one fails with "Script action failed to execute". Clips are always looked up fresh by where they start (`findAt`). Trimming the in point moves the start by the same amount, and trimming the out point keeps it.
  - On Josh's Premiere 25.6.6, a set-start or set-end that reaches before the media start fails with "Invalid parameter", and so does putting several trims in one transaction. Nothing ever extends a clip. Copies don't bring linked audio, so a recording linked to its mic has to be unlinked first.
  - `probe` (Settings > Check Premiere, and run by itself before the first cut on a new Premiere version) tests each trim and move action on its own, then the whole shrink-then-slide recipe, then whether the recording is linked. The result is in `Projects/premiere-probe.json`. The cut checks every track against its plan afterwards and stops with the backup's name if anything is off.
  - After each cut the panel writes every clip on the sequence, plus any gaps or overlaps, to `last-cut.json` in the recording's project folder. It also reopens the sequence, because Premiere doesn't always redraw after many quick edits and the clips look like they've gone.
  - While a cut runs, the app shows a progress screen like AutoCut's. The panel posts its step to `/bridge/progress` and the app polls it. Premiere's API has no way to lock the timeline, so the screen asks Josh to leave it alone.
  - Clean cut removes silences only and Flubs removes the flub words only. Josh picks which audio track to listen to.
- **Claude's replies are kept and repaired.** Every raw reply is saved in `Projects/claude-replies` (newest 40). `claude_api.extract_json` repairs a reply that won't parse before giving up. It allows line breaks in strings, re-escapes SVG sketches (a double quote inside `sketch_svg` broke a $0.41 shot list), drops stray commas, then tries without the sketches. With `salvage`, it keeps every animation that still parses. The shot list prompt asks for single quotes inside SVG.
- **Every time the app window opens, each recording starts fresh.** Josh's choices (`project.json`, `flubs.json`, the shot list, the PiP preview) move into a `_superseded` folder. What's worked out from an unchanged file stays (decoded audio, transcript, Claude's read of it, renders), and the app says when it was made.
- **Layers sit on words.** Animations, angle shots and B-roll are planned against source word numbers and mapped through the timeline that's open now by `helper/layers.py`. The panel sends the recording's clips (`spans`) with every request, and the helper builds the cut map from them. A cut lifts our own clips off V4 and V5 first, then the `layers` job and the `layers` bridge command place them again (V5 animations, V4 camera copies under PiP and half-and-half shots). Josh can turn that off in Settings.
- **Styles and shot types.** `helper/style.py` turns a style (fonts, colours, motion, look) and the PiP shape into CSS for the kit in `templates/kit/`, and `helper/deck.py` applies it when assembling the deck. `helper/render.py` renders PiP, half-and-half, key word and lower third shots as ProRes 4444 with alpha. Scenes must use the kit's classes and colour variables, never raw fonts or colours. The extra font pairings are woff2 files in `templates/fonts/`.
- **UXP Premiere API gotchas.**
  - `Constants.ProjectItemType` only exists from Premiere 27.0. Find bins by casting with `FolderItem.cast` and calling `getItems`, and media by `ClipProjectItem.cast` and `getMediaFilePath`.
  - `createOverwriteItemAction` needs the `ProjectItem`, not the `ClipProjectItem`.
  - Use `createRemoveItemsAction(sel, false, MediaType.VIDEO)`.
  - Times are `TickTime.createWithTicks(String(BigInt))` at 254016000000 ticks a second.
  - Wrap every edit in `project.lockedAccess(() => project.executeTransaction(...))` and label errors so Josh can report them.
  - Motion Position is 0 to 1 across the frame.
- Range sliders don't drag in the UXP panel, which is one reason the controls moved to the Edge window.
- Mic sync uses `audio_offset = (micIn - micStart) - (vidIn - vidStart)` from the timeline.
- **Animations render at the sequence's size.** The panel reads the frame size (`getFrameSize`), and `render.py` draws the 1920 by 1080 deck at that scale (2 for Josh's 4K sequences) so it fills the frame and stays sharp. The PiP camera scale is multiplied by the same amount.
- **PiP.** The animation renders with a transparent hole in the chosen shape, and the camera copy on V4 is scaled and positioned to fill it. The copy is cloned from Josh's own V1 clips (`copyCamera`), so his key, look and edits come with it and the mic on A1 isn't touched. Placing it from the raw file lost his green screen key and overwrote his mic with camera sound. The Animations screen shows a still of him inside the shape, and dragging moves only him, using the same framing maths as `pip.py` (`camLayout` in app.js). The default tall box is `[1322,202,518,674]` with a 6px gold border and a drop shadow. The old separate-sequence route still uses Basic Motion plus a Crop filter in the XML.

## Design

- **Palette.** Ink and gold, with ink `#0c0d10` up through the ink scale, gold `#f5c21b`, gold-2 `#ffd54d`, red `#e2584c` and green `#43b37a`.
- **Fonts.** Outfit and Manrope, lifted as base64 from `templates/deck-template.html`.
- **Feel.** Editor-pro and compact, based on Refactoring UI principles. Use two-part shadows, a clear hierarchy and one gold primary button per screen. It should be inspired by AutoCut but never a clone.
- **Animations.** These use Josh's house deck style in `templates/`.

## Josh's writing rules (all UI copy, docs and replies)

- Write at a grade 12 reading level, conversational, like a smart person talking.
- Don't use em dashes.
- Don't use "it isn't X, it's Y" or any framing by negation.
- Never use the words quiet, quietly, land, landed, honest or honestly.
- Don't use colons to split sentences.
- Don't write fragment lists.
- Don't say why something matters or how surprising it is. Just say it.
- Don't guess where a setting lives in Premiere or Windows. Check the docs or say you're not sure.

## Testing

There's no Premiere in a test environment. Use the panel preview with a fake `ppro` stub, a mock Claude server (point `DAJOSHI_CLAUDE_URL` at it) and Playwright to drive `http://127.0.0.1:47820/app/`. On this PC, the real test is Josh using it in Premiere, with `Projects\helper.log`, each job's `process.log`, `Projects\premiere-probe.json` and each recording's `last-cut.json` for errors.

- Josh's own helper is usually running on 47820, so test on a spare port with `DAJOSHI_CUT_PORT`, an empty `DAJOSHI_CUT_PROJECTS` folder and an empty `DAJOSHI_CUT_STYLES` folder. The panel preview reads `window.JOSH_HELPER` for the port.
- The engine refuses media work while OBS is open. Don't close OBS. For tests, start the helper from a small launcher that puts a fake `worker` module with a no-op `guard_recording` in `sys.modules` first.
- The stub (`tests/ppro-stub.js`) models Josh's setup and his Premiere 25.6. The camera is on V1 with its sound deleted, and `sample-5min-mic.wav` is on A1 two seconds late. Trims that reach before the media start fail, and clip objects go stale after every edit.
- `tests/layers-flow.py` runs clean cut, flubs, animations and recuts through the helper, applying each cut to a list of spans the way the panel would. `tests/ui-inplace.py` drives the app and the stubbed panel through Clean cut, Flubs, Animations and a second cut on one sequence. It checks the mic stays in sync on every slice, that backups are saved, the progress screen and PiP dragging.
- `tests/replay-orders.py <project folder> <silences job> <apply job>` runs a real recording's Clean cut and Flubs in both orders from the untouched timeline and fails on any overlap, sliver or mic slip.
- `tests/replay-cut.py <last-cut.json> <job folder>` replays a real cut from Josh's PC through the panel code against the stub, with his sequence timebase (8467191533 ticks a frame, slightly off 30 fps), and lists any moment two clips overlap.
- Keep network calls out of the edit loop. The panel's progress updates are awaited and sent at most once a second. Firing them alongside every edit is the main suspect for Premiere going down during a long Flubs cut in 0.8.3. Playwright needs `channel='chrome'` here, since its bundled browser isn't installed.

## Roadmap

ROADMAP.md has the full plan Josh agreed, with detailed instructions for each phase. In order, the phases are the foundation (word anchors and a fixed track plan), animation styles and shot types, Angles (multi-camera cutting at natural breaks), Interview (assembling a cut from separate host and guest recordings using a rough script), B-roll, then Zooms, Your look and the one-file installer. Read it before starting any new feature, and keep it updated when Josh changes his mind.

New features planned elsewhere arrive as their own file, such as `ROADMAP-<feature>-addition.md`, with instructions for merging. Merge them into ROADMAP.md and CLAUDE.md keeping everything already there, note anything in them that has since changed, then delete the addition file.

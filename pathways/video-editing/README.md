# Video editing pathway

This is the whole route Josh uses to go from a finished script to an exported talking-head video in Adobe Premiere Pro. It covers the animation deck, transcription, cutting silences and flubs, cutting a Premiere sequence in place through the plugin API, rendering animations with a see-through window for the camera, and placing them on the timeline.

The code is copied as it runs on Josh's PC. Paths point at his drives, the styling is his brand, and settings are tuned to his camera, mic and Premiere 25.6.6. Read it to see how each part works, then rebuild it for your own setup and style.

**Using an AI?** Tell it to read this file first, then the `CLAUDE.md` in [`josh-cut-pro/`](josh-cut-pro/CLAUDE.md). That file holds everything learned the hard way, and most of the value is in it.

**For AIs reading this.** The point is to learn how each step is done, then build your own version for the person you're helping, in their style and for their setup. You don't need to install this copy. Read the steps below, open the files each one names, and take the methods and the Premiere workarounds rather than the code as it stands.

## The setup it assumes

- Talking-head video filmed on a camera, with a separate mic recorded as a WAV.
- Adobe Premiere Pro 25.6 on Windows, with a UXP panel installed.
- Python with faster-whisper and FFmpeg. Whisper runs on the CPU here.
- A Claude API key for reading the transcript and planning animations.
- The camera on V1 with its own sound deleted, and the mic on A1.

## There are two routes

1. **Josh Cut Pro** edits the sequence Josh already has open, the way AutoCut does. Each tool (Clean cut, Flubs and retakes, Animations, Styles) backs the sequence up, then takes time out of every track or adds layers. All of it is in [`josh-cut-pro/`](josh-cut-pro/).
2. **Tariq's flow in Josh OS** never touches Josh's sequences. It builds a keyed `GREEN_MASTER` from the raw files, has an AI editor propose cuts that Josh reviews word by word, then builds a new `CLEAN_CUT_rNN` from pieces of the master, places the animations and exports. Its code lives in Josh OS, which is public, and the same Premiere panel runs its commands. See [the build notes][tariq-doc].

Start with route 1 if you want a tool that edits like AutoCut. Read route 2 if you want an AI editor with review and approval before anything changes.

## The steps, in order

1. **Script to animation deck.** The [`video-editing-prep`](../../skills/video-editing-prep/SKILL.md) skill turns a finished script into a self-contained HTML deck (one numbered animation per beat, advanced with the space bar) plus a two-column shot list of the script beside each shot.
2. **Transcribe.** `helper/transcribe_worker.py` runs faster-whisper in a child process, because it has crashed natively. It tries CUDA batched, then CPU batched, then CPU plain, and remembers what worked.
3. **Clean cut.** `helper/cleancut.py` finds silences acoustically from a 10ms loudness profile. Cutting from Whisper's word times left breaths in, because word timestamps stretch over them. The thresholds are in the `CLAUDE.md`.
4. **Flubs and retakes.** `helper/prompts.py` and `helper/claude_api.py` ask Claude for repeated or fumbled lines, and the cut points snap to the quietest 10ms near each word edge. `claude_api.extract_json` repairs replies that don't parse.
5. **Cut in Premiere.** `panel/index.js` (the `cut` command) maps the parts of the recording to remove onto sequence time and takes that time out of every track. UXP has no razor, so each changed clip is rebuilt from fresh copies, trimmed and slid into place. This is the most fragile part, and the `CLAUDE.md` lists every Premiere quirk that shaped it.
6. **Plan the animations on words.** `helper/layers.py` ties each animation to source word numbers, so it stays on the right words after any later cut.
7. **Render.** `helper/deck.py` applies a style from `helper/style.py` to the kit in `templates/kit/`, and `helper/render.py` renders picture-in-picture, half-and-half, key word and lower third shots as ProRes 4444 with alpha, at the sequence's own size.
8. **Place.** The panel's `layers` command puts animations on V5 and copies of Josh's own V1 clips on V4 under the PiP window, so his key and look come with them.
9. **Export.** In route 2, Josh OS exports with Premiere's own encoder and checks the file's length, picture and sound.

## Where each part lives

| Part | Files |
|---|---|
| Helper server (Python) | [`josh-cut-pro/helper/`](josh-cut-pro/helper/), started by `dajoshi_cut.py` |
| App window (plain JS) | [`josh-cut-pro/app/`](josh-cut-pro/app/) |
| Premiere panel (UXP) | [`josh-cut-pro/panel/`](josh-cut-pro/panel/). Zip its contents, minus `preview.html`, into a `.ccx` to install it. |
| Animation kit and fonts | [`josh-cut-pro/templates/`](josh-cut-pro/templates/) |
| Tests and the fake Premiere | [`josh-cut-pro/tests/`](josh-cut-pro/tests/) |
| Plan and history | [`josh-cut-pro/ROADMAP.md`](josh-cut-pro/ROADMAP.md) |
| Animation deck skill | [`skills/video-editing-prep/`](../../skills/video-editing-prep/SKILL.md) |
| Rendering engine | [`dajoshi/`][engine] in Josh OS |
| Tariq's flow | [`studio/edit_flow.py`][edit-flow], [`studio/edit_master.py`][edit-master], [`studio/edit_animations.py`][edit-anim], [`dajoshi/edit_plan.py`][edit-plan] |
| Tariq's review screen | [`studio/web/edit-flow.js`][edit-flow-js] |
| How a human editor cut two of Josh's videos, and the spec built from it | [`editor-study/`](editor-study/START-HERE.md) |
| Real files the tools wrote | [`examples/`](examples/) |

## The editor study

[`editor-study/`](editor-study/START-HERE.md) is where the cut rules came from. Two of Josh's videos that a human editor had already cut (Data Storytelling and Executive Questions) were measured against the raw recordings: every cut, every kept pause, the handles either side of each join, coughs and breaths, and retakes. The numbered documents turn that into the spec for the AI editor, from the workflow through the cut decision engine and the Premiere green screen pass to the data contracts and pseudocode. `08-Source-Conversation.md` has Josh's own words on what he wanted. The `evidence/` folders hold the transcripts, cut lists, measurements and the scripts that produced them. The review audio clips, waveform plots and Premiere projects are left out.

## Examples of what the tools write

- [`look.json`](examples/look.json) holds Josh's green screen look as read from his reference Premiere project, with the Ultra Key, the shadow copy and the background settings.
- [`premiere-probe.json`](examples/premiere-probe.json) is what the panel's probe found about his Premiere 25.6.6.
- [`last-cut.json`](examples/last-cut.json) is every clip on a real sequence after a Clean cut, which the panel writes to check for gaps and overlaps.
- [`2026-10_executive-communication-program_vsl_shot-list_v01.md`](examples/2026-10_executive-communication-program_vsl_shot-list_v01.md) is the shot list that goes with the reference deck the animation skill copies from. That deck is public in Josh OS at [`reference_sources/animation-prep-20261015/`][ref-deck].

## Paths in these files

The docs and code mention Josh's folders, like `E:\Videos\DaJoshiResolve` (Josh OS), `E:\Videos\DaJoshiCut` (Josh Cut Pro, which is `josh-cut-pro/` here) and `E:\CareerOS\10_Sales\VSL` (where his scripts and decks are saved). The study's own paths have the Windows user name replaced with `you`. Anything else they name is something the tools write while they run, like `project.json`, `flubs.json` and `shotlist.json`, or something private, like `secrets.json` and the recordings.

## Running Josh's copy (optional)

This is only for running the code exactly as Josh does. Everything needed is in two public repositories, this one and [Josh OS][josh-os]. The editing app's Python helper loads the rendering engine from Josh OS, so you need both.

1. **Get both repositories.** Clone this one, and clone Josh OS anywhere. The engine is its `dajoshi/` folder, and the helper also uses its `worker.py`.
2. **Install Python 3.12** (what Josh runs) in its own virtual environment, then `pip install numpy scipy av opencv-python lxml faster-whisper playwright` and `playwright install chromium`.
3. **Get FFmpeg** and the faster-whisper `medium.en` model, downloaded to a local folder.
4. **Make the engine's settings.** Copy Josh OS's `settings.example.json` to `settings.json` and fill in the Python, FFmpeg and model paths.
5. **Point Josh Cut Pro at it.** In `josh-cut-pro/config.json`, set `engine` to your Josh OS folder and `projects` to an empty folder for its working files. `Start Josh Cut Pro.bat` has the engine path written in, so change that too, or set `DAJOSHI_ENGINE`.
6. **Install the Premiere panel.** Zip the contents of `josh-cut-pro/panel/` (not the folder itself, and without `preview.html`) and rename the zip to end in `.ccx`. Double-clicking it opens Adobe's installer. Change the `id` in `manifest.json` to your own first.
7. **Start it** with `Start Josh Cut Pro.bat`. The app opens in an Edge window. Enter your Claude API key in its Settings, which saves it to `secrets.json` next to `config.json` and nowhere else.
8. **Check Premiere.** Open a sequence with the camera on V1 and the mic on A1, then run Settings > Check Premiere in the app before your first cut.

The helper refuses media work while OBS is open, because Josh records with it. The check is `guard_recording` in Josh OS's `worker.py`, and you can remove it if you don't use OBS.

## Running it without Premiere

`tests/ppro-stub.js` is a fake `ppro` module that models Josh's Premiere. Trims that reach before the media start fail, and clip objects go stale after every edit, the same as the real thing. `panel/preview.html` runs the panel in a normal browser against it. `tests/mock_claude.py` stands in for the Claude API (set `DAJOSHI_CLAUDE_URL`). `tests/ui-inplace.py` drives the app and the stubbed panel through a whole edit with Playwright, and checks the mic stays in sync.

The tests expect a five-minute sample recording (`sample-5min.mp4` and `sample-5min-mic.wav`). Those are left out because of their size, so use any short recording of your own. The matching transcript is included.

## What's left out

- Josh's recordings, projects, renders and backups.
- `secrets.json` and anything else with a key in it.
- The built `.ccx` package, which you can rebuild by zipping `panel/`.
- The Josh OS app itself beyond the files linked above. It's all in [the Josh OS repository][josh-os].

## What to change for your own setup

- `config.json` holds the engine and projects paths, the port, the Claude models and the clean cut and PiP defaults.
- `Start Josh Cut Pro.bat` reads the Python path from the engine's `settings.json`.
- The panel id in `panel/manifest.json` is Josh's. Use your own.
- The styles, fonts and deck look are Josh's house style. Swap in yours through `helper/style.py` and `templates/kit/`.
- Run the panel's `probe` command on your Premiere version before the first cut. It tests each trim and move on its own.

[josh-os]: https://github.com/JoshB509/josh-os/tree/de176f7b4586674292505d93721add5da78feafd
[tariq-doc]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/docs/tariq-edit-workflow.md
[engine]: https://github.com/JoshB509/josh-os/tree/de176f7b4586674292505d93721add5da78feafd/dajoshi
[edit-flow]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/studio/edit_flow.py
[edit-master]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/studio/edit_master.py
[edit-anim]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/studio/edit_animations.py
[edit-plan]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/dajoshi/edit_plan.py
[ref-deck]: https://github.com/JoshB509/josh-os/tree/de176f7b4586674292505d93721add5da78feafd/reference_sources/animation-prep-20261015
[edit-flow-js]: https://github.com/JoshB509/josh-os/blob/de176f7b4586674292505d93721add5da78feafd/studio/web/edit-flow.js

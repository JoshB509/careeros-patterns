# Josh Cut Pro roadmap

This is the plan for what comes after 0.5. Josh planned it in conversation and it's written here as instructions for Claude Code. Read CLAUDE.md first for how the app works today.

Build in this order unless Josh says otherwise. Each phase should ship as something he can test in Premiere before the next one starts, and a fix for whatever he hits in 0.5 always comes before new work.

1. Foundation (word anchors and a track plan)
2. Animation styles and shot types
3. Angles (multi-camera cutting)
4. Interview (assembling a cut from separate host and guest recordings)
5. B-roll
6. Zooms, Your look and the one-file installer

**Changed in 0.8.0.** Josh asked for Clean cut and Flubs to work like AutoCut. They now cut the sequence he has open, after saving a backup copy, instead of building a separate "<name> - Josh Cut" sequence. Wherever the phases below say "the Josh Cut sequence", read "the open sequence". The track plan is the same. CLAUDE.md has the details, including what the Premiere check found on Josh's Premiere 25.6.6.

Keep to the house rules in CLAUDE.md for every screen and every line of copy. Each new tool gets a tile on the home grid, its own screen with the same stepper, review and apply pattern as Flubs and Animations, and one gold primary button.

---

## 1. Foundation

**Built in 0.6.0, reworked in 0.8.0 for cutting in place.** What's in it and what's still unproven:

- `helper/layers.py` holds the track plan, word anchoring (`Cut.locate`), the overlap planner (`resolve`) and the toast text. `angles.json` and `broll.json` load and save with a version number, and the shot list gets one when it's built.
- The cut map comes from the timeline that's open now. The panel sends the recording's clips (`spans`) with every request, so manual edits Josh makes in Premiere are followed too.
- A cut lifts our own clips off V4 and V5, cuts every other track, then the `layers` job puts the animations back on their words. Settings has "Put layers back after a recut" (on) and "Animations in their own sequence" (off), stored in `Projects/prefs.json`.
- Renders are cached by press without their length, and new ones get 2 seconds of slack on top of the 5 second hold, so most recuts reuse them.
- The panel adds tracks above V3 by inserting a placeholder after the end of the timeline, since Adobe only documents that an insert creates missing tracks. This hasn't run in real Premiere yet.
- Angle and B-roll placement is written but has nothing producing plans yet. Their sound goes on A4 and is removed unless the clip keeps its audio. Setting minus 20 dB is left for the B-roll phase.

Angles, B-roll and animations all add layers on top of the Josh Cut sequence, and Clean cut and Flubs rebuild that sequence from scratch. Without this phase every recut would wipe the layers.

### Word anchors

- Store every planned layer (an animation, an angle shot, a B-roll clip) against word indices in the **source** transcript, never against sequence seconds. Each item has a start word, an end word and optional offsets in seconds.
- At place time, map those words through the current cut map (`dajoshi.timing.map_interval`) to get sequence times. If the start word was cut, snap to the next kept word. If the whole stretch was cut, drop the item and tell Josh in the result toast ("2 B-roll clips were on words you've since cut").
- Keep these plans in the project folder as `angles.json`, `broll.json` and the existing `shotlist.json`, each with a version number.
- A cut can come from more than one recording (the Interview tool assembles several). So an anchor is always a pair, the source file's fingerprint plus a word index in that file's transcript, and the cut map is a list of pieces that each name their source. Build it this way from the start, even though Clean cut only uses one source today.
  - Not done yet. As built in 0.6.0 to 0.8.3, anchors are word indexes in one recording's transcript, and the project folder is keyed by that recording's path. The cut map comes from the clips of the main recording only. This needs reworking before Interview.

### Track plan

Use a fixed layout in the Josh Cut sequence so every tool knows where it writes and can clear only its own track.

| Track | What goes there |
| --- | --- |
| V1 | Main camera, cut by Clean cut and Flubs |
| V2 | Angle shots (alt and demo cameras) |
| V3 | B-roll |
| V4 | Camera copy for PiP and half-and-half shots, scaled into place |
| V5 | Animations |
| A1 | Mic (or main camera audio) |

B-roll and angle audio stay off by default. Animations move from their own "- Josh Cut Animations" sequence into V5 of the Josh Cut sequence. Check with Josh before removing the old separate-sequence option.

### Rebuild keeps the layers

After Clean cut or Flubs rebuilds the sequence, re-place every saved layer automatically from its word anchors and say so in the toast ("Put back 6 animations, 11 angle shots and 9 B-roll clips"). Settings get a switch to turn this off.

### Overlap rules

One small planner resolves clashes before anything is placed. The priority order is full-screen animation, then half-and-half or PiP animation, then demo camera, then B-roll, then alt angle. Lower items get trimmed or dropped where they clash with higher ones, and the review screens show what was dropped.

---

## 2. Animation styles and shot types

**Built in 0.7.0, apart from the template library below, which came into the plan afterwards and isn't built yet.** What's in it and what's still unproven:

- **The spike.** `helper/render.py` is the engine's renderer with an alpha option. PiP, half and half, key word pop and lower third shots render as ProRes 4444 `.mov` with alpha, and full screen, title and end screen shots stay H.264. The PiP hole is a CSS mask cut from the shape, and the gold frame and shadow are drawn around it. Renders checked out over a green background. Premiere importing the `.mov` files and the panel setting Scale and Position on the V4 camera copy haven't been tried in Premiere yet. The Premiere check confirmed Position takes values from 0 to 1.
- **No crop needed.** The animation on V5 covers everything outside the hole, so the V4 copy only needs Scale and Position.
- **Shot types, how often and how rich** are on the Animations screen and go into `prompts.shot_system`. The plan is checked against the target, and Claude is asked once to add or trim if it's far off. Only one end screen is kept, and it's moved into the last 20 seconds.
- **The style kit** lives in `templates/kit/`. `kit.css` handles layout, with one file per motion and one per look, plus a small `kit.js`. The helpers this plan names as JS functions became CSS classes (`k-em`, `k-under`, `k-box`, `k-pop`, `k-lower`, `k-title`, `k-panel`), because scenes can't contain scripts. The template's fixed fonts and colours are pointed at the style's variables when the deck is assembled, so older scenes follow the style too. There's no separate `tokens.css`, since `helper/style.py` writes the variables.
- **Re-renders.** Each press is keyed by its own scene, the style and only the layout it depends on. A new PiP shape re-renders only PiP presses, a new style re-renders everything, and neither calls Claude.
- **Styles** save to `styles/<name>.json`. "Josh house" is built in (house fonts, Ink and Gold, formal, editorial). The editor warns when text contrast is under 4.5 to 1.
- **Fonts.** All five pairings work. Josh OK'd the download, and the woff2 files are in `templates/fonts/` (Latin subset, from Fontsource, OFL). The README there lists where they came from.
- **PiP framing.** The PiP card has the shape picker with a live sample screen, finer nudge steps and dragging on the preview picture.
- **The old separate-sequence route** only handles full screen and boxed PiP. Other types are skipped there with a marker.

Today Claude picks freely between full screen and PiP in one house style. This phase lets Josh choose which shot types are allowed, how often animations appear, how rich they are and how they look. The Styles tile on the home screen opens the style editor, and the Animations screen gets the shot type and amount controls above the notes box.

### Shot types

Josh switches on the types he wants with toggle chips. Claude only plans types that are switched on.

1. **Full screen.** The animation covers the camera.
2. **Half and half.** A panel slides in from one side and content builds on it while Josh sits in the other half. Its options are which side the panel comes from (left by default).
3. **Picture in picture.** Josh sits in a shape over the animation. It has its own sub menu, shown below.
4. **Watch next end screen.** Claude finds the call to action near the end of the video ("watch this video next" and similar). The shot builds a branded end card with empty frames where Josh adds the YouTube end screen elements in YouTube Studio (one video frame and a subscribe circle by default). Keep it inside the last 20 seconds, since YouTube end screens can only run that long.
5. **Key word pop.** Big text appears over the camera with no panel, for single-word emphasis. (Suggested, off by default.)
6. **Title card.** A short section or chapter opener. (Suggested, off by default.)
7. **Lower third.** Names a topic, a framework or a person. (Suggested, off by default.)

Josh can drop 5 to 7 if he doesn't want them. If more than four types are switched on, or Heavy is combined with Explainer, show a gentle warning under the chips ("This many could feel busy. Claude will still keep it to what you picked.").

#### PiP sub menu

- **Shapes.** Small circle, large circle, small box, large box, tall box (today's default) and square.
- **Side.** Left or right, with top or bottom as a later option.
- **Border and shadow.** Keep the gold border and soft drop shadow by default. Both come from the style's colours.
- **Live preview.** Above the options, a small 16 by 9 sample screen shows a mock slide with Josh's camera shape. When he picks a shape or side, the shape animates to its new spot with a CSS transition. The existing nudge pad and zoom stay underneath for fine-tuning his framing inside the shape.

#### How the shapes are built (spike this first)

The current PiP uses a Crop filter, which can only make rectangles. For circles the recommended approach is to render the animation with transparency, leaving a transparent hole the shape and size of the PiP. The camera copy on V4 sits underneath, scaled and positioned so Josh fills the hole. The gold border and shadow are drawn by the animation around the hole.

- Render with Playwright screenshots using `omitBackground: true` and encode to ProRes 4444 with alpha.
- Before building the rest, test on Josh's PC that Premiere imports the alpha clip correctly through the bridge.
- Test that the camera copy's Motion scale and position can be set, either natively through the UXP component parameters or through XML.

If that fails, fall back to compositing the camera into the clip with ffmpeg (a circle mask, border and shadow). Josh then can't reframe himself in Premiere, so tell him before choosing it.

Half and half uses the same camera copy on V4, scaled and cropped to the open half.

### How often

This is a three-step control on the Animations screen. It goes straight into the shot list prompt as a target and rules.

- **Light.** Only the hook promise at the start, the key lessons or scene changes, and the end screen. Roughly one every 90 seconds at most.
- **Medium.** Adds the deeper explainers. Roughly one every 45 seconds.
- **Heavy.** Something on screen often. Roughly one every 20 to 25 seconds, with no gap longer than about 40 seconds.

Code checks the plan against the target and asks Claude to trim or add once if it's far off.

### How rich

This is a second three-step control.

- **Text.** Words only, with the odd accent such as one key word highlighted.
- **Designed.** Text plus icons, shapes, simple cards and layout.
- **Explainer.** Small animated explainers that build over several presses, like Josh's own slides (diagrams building up, steps appearing, comparisons).

### Style editor (the Styles tile)

A style is saved as a named file in `styles/<name>.json`. The Animations screen has a dropdown to pick one, and the default is "Josh house" (ink and gold, Outfit and Manrope, formal motion, editorial look). The editor shows a live preview at the top: a looping sample scene rendered from the real template with the chosen style, so what he sees is what renders. Controls sit underneath.

1. **Fonts.** Pick a pairing (heading plus body).
   - House: Outfit and Manrope
   - Editorial: Fraunces and Inter
   - Modern: Space Grotesk and Inter
   - Bold: Anton and Work Sans
   - Friendly: Poppins and Nunito

   Bundle the woff2 files in `templates/fonts/` (all are OFL licensed) because rendering is offline.
2. **Colours.** Pick a preset or set your own.
   - Presets: Ink and Gold, Paper (cream, ink, red), Midnight (navy, coral), Mono (white, black, one accent) and Newsprint (yellow, black)
   - Custom pickers: background, surface, text, primary and accent
   - Shades are generated from those, and a warning shows if text contrast against the background falls under 4.5 to 1.
3. **Motion.** This sets how things come and go.
   - Formal: short fades and small slides, around 300ms, ease out
   - Floaty: slow drifts with a slight scale, 600 to 800ms, ease in and out
   - Bouncy: spring overshoot and pops, staggered
4. **Look.** This sets how things are emphasised and built, for text and for everything else.
   - **Editorial.** A highlighter swipe behind key words, hand-drawn underlines, paper texture and cards like clippings.
   - **Modern.** Key words change colour or get a soft pill fill, with clean lines, soft shadows and sliding panels.
   - **Bold.** Thick underlines and boxes that draw on, stamps, hard shadows and big type.

### Keep animations light on tokens (template library)

Josh cares about token cost first and render time second. Rendering is local and cheap (screenshots of a web page), so the saving has to come from what Claude writes. At 0.5 a 10-animation video costs roughly $1.50 on Opus, mostly from the SVG sketches in the shot list and the HTML Claude writes for every scene. The target is under 50 cents.

- **Scene templates.** Build a library of ready-made scene templates in `templates/scenes/`. Each has named slots, a set number of presses (or a range, like 2 to 6 points) and works inside any frame that suits it (full screen, half and half, PiP). The shot type decides where the animation sits, and the template decides what's on it. Each template is written once against the style kit, so it restyles with fonts, colours, motion and look automatically. The starting library is listed below, grouped by what the moment in the video is doing.
  - **Words.**
    - Key word. One big word or phrase lands, with the emphasis from the look.
    - Quote card. A line Josh says, or someone else's, with key words emphasised.
    - Question card. A question on screen that opens a curiosity gap ("Why did they say no?").
    - Message. A chat bubble, email line or Slack message, for what a boss or colleague said.
  - **Structure.**
    - List build. 2 to 6 points appear one per press, numbered or with ticks.
    - Three things. Three cards side by side, each with an icon and a short label.
    - Steps. Numbered steps joined by arrows, across or down.
    - Comparison. Two columns (before and after, wrong and right, them and you) with crosses and ticks.
    - Myth and truth. The wrong belief gets struck through and replaced by the right one.
    - Checklist. Items tick off one press at a time.
  - **Numbers.**
    - Big stat. A number counts up with a label underneath.
    - Bar compare. Two or three bars grow side by side (a 3% raise against a 20% one).
    - Scale. A line with a marker that moves along it (from doer to leader, say).
  - **Story.**
    - Timeline. Points along a line, such as years or career stages.
  - **Frames that are also templates.**
    - Title card
    - Lower third
    - Watch-next end card
- **Templates first, never templates only.** Claude reuses a template wherever one fits, because it costs almost nothing and stays consistent. When nothing fits, or a moment deserves more, Claude marks the animation `custom` and gives a one-line reason, and that one gets a build call. At Explainer level most animations will be custom, and that's expected. A custom scene can still use the kit's building blocks (cards, chips, arrows, icons) inside it, so it matches the rest.
- **Variety.** Don't use the same template twice in a row, and use any one template no more than about three times in a video unless the content calls for it. Code checks this and tells Claude once if it's over.
- **Growing the library.** If Josh likes a custom scene, a "Save as a template" button on its review card asks Claude (one cheap call) to turn it into a template with slots. That way the library grows from his real videos.
- **Shot list returns data only.** For every animation that uses a template, Claude picks it and fills its slots in the shot list JSON. The slots are the words for each press, which word to emphasise and an icon name from a fixed icon set. It returns no HTML and no SVG, so each animation is a few hundred output tokens.
- **The PC draws the sketches.** The review card preview is the template rendered locally with the slots filled in (the final frame, as a still). Drop `sketch_svg` from the prompt. This alone removes most of the shot list's output cost.
- **Custom HTML only where it's needed.** Only animations marked `custom` go to a build call. The build call gets a short style kit reference (class names, helpers and variables, about 1 to 2 thousand tokens) and never the full house CSS.
- **Models.** Shot list planning stays on the strongest model. Custom Explainer builds go to `models.deck`, which can be Sonnet. Flubs use Sonnet (already the default from 0.5.1). B-roll scans use Haiku.
- **Check the result.** Use the cost meter (below) on the same test video before and after, and report the numbers to Josh.

### Cost meter (added in 0.5.1, for Josh's own use)

- Every Claude call records its token usage from the API.
  - Each job's toast ends with "Claude cost about $x".
  - The job log shows the token counts.
  - A row goes into `Projects/claude-costs.csv`.
  - Settings has a Claude spend card showing this month, all time and per video.
- Prices live in `PRICES` in `helper/claude_api.py`. Update them if Anthropic's pricing page changes.
- Set `"show_costs": false` in `config.json` to hide the meter. The installer build should ship with it off.

### How to build styles (important for consistency)

- Make a style kit in `templates/kit/` with these parts:
  - `tokens.css`, which holds CSS variables for fonts and colours
  - one CSS file per motion style
  - one CSS file per look
  - a small JS helper set the scenes call, such as `kit.enter(el)`, `kit.exit(el)`, `kit.emphasise(span)`, `kit.underline(span)`, `kit.panel(side)` and `kit.pipHole(shape, side)`
- Claude's deck prompt is told to write scenes using only the kit helpers and variables, never raw colours, fonts or keyframes. Switching style then needs no new code from Claude, and the same shot list can be re-rendered in a different style.
- The deck template animates with CSS keyframes under the deterministic Playwright clock. The kit must use CSS animations the same way so rendering stays frame-exact.
- Re-render only the clips whose style or content changed, using the existing cache.

---

## 3. Angles (multi-camera cutting)

Working name "Angles". Josh hasn't named it, so ask before finalising. It cuts between extra cameras automatically. Josh sets up the cameras, Claude plans the switches, Josh reviews and applies.

### Setup step

- Read every video clip in the open sequence through the bridge and list them with a thumbnail. Each gets a role dropdown.
  - **Main.** The presenter camera.
  - **Alt angle.** Another view of the presenter, used to keep shots interesting.
  - **Demo camera.** Shows what's being explained, such as a top-down desk, an iPad screen recording or fingers on a guitar neck.
  - **Ignore.**
- Each demo camera gets a one-line description box ("top-down of my hands on the fretboard"). Claude uses it to decide when that camera is relevant.
- By default the cameras are assumed to be lined up on the timeline already. A "Line them up by sound" button cross-correlates each camera's scratch audio with the mic (DaJoshiResolve's `media.sync` already does this) and stores each camera's offset.
- Save the roles and offsets in the project so it only happens once per recording.

### Where a cut is allowed

Every switch between cameras (alt or demo) happens at a natural break in the speech, never in the middle of a word or a phrase. Code builds a list of good cut points first and Claude can only choose from that list.

- **Best.** The end of a sentence followed by a pause, or the start of a new point.
- **Good.** A clause break, such as after a comma or before "and", "but", "so" or "because", where there's a small gap in the audio.
- **Allowed.** The gap just before a key word as a point lands, so the new angle arrives with the emphasis.
- **Never.** Inside a word, between words with no gap, or in the middle of a stumble or retake.

Use the transcript's punctuation and word timings together with the acoustic profile from Clean cut. A cut point is the quietest 10ms spot in the gap between two words, the same snapping Flubs uses. Each point gets a score (best, good, allowed) so Claude can prefer the strongest breaks.

### Alt angle rules

Alt angles keep the shots interesting. Claude picks which cut points to use from the clean transcript, favouring the start of new points and the moments where a point lands.

- Hold each alt shot for 3 to 8 seconds, then return to main at the next good cut point.
- Never cut in the first 2 seconds of the video or within 1.5 seconds of another cut.
- Never use an alt angle during an animation that shows the camera (PiP, half and half).
- "How often" uses Light, Medium and Heavy, at roughly 10, 20 and 35 percent of the runtime on alt.
- With several alt cameras, rotate between them and avoid using the same one twice in a row.

Code enforces the hold times, the gaps and the cut point list afterwards, and moves any switch Claude places off a cut point to the nearest one.

### Demo camera rules

- Claude finds the stretches where Josh is talking about what the demo camera shows. It uses the transcript, the camera descriptions and phrases like "look at this", "here", "watch my hand" and "on the screen".
- Each demo stretch starts and ends on cut points from the list above and lasts at least 2 seconds.
- A "Show me in PiP over the demo" switch puts the presenter in the chosen PiP shape over the demo. It reuses the PiP shape picker and preview from phase 2, placing the presenter copy on V4 above the demo on V2.
- Later option, worth trying only if transcript-based picking misses moments: sample demo frames to see when something is actually happening (an iPad screen changing, hands moving).

### Review step

Reuse the Flubs script view. Words are underlined in the colour of the camera that will show (main in plain text, alt in gold, demo in a second accent), with a thin strip above showing the blocks across the video. Josh highlights words and presses Main, Alt or Demo (with a camera picker if there are several). A Reset to Claude's picks button sits at the top, the same as Flubs.

### Apply step

- For each shot, map its word range to sequence time.
- Split it wherever it crosses a Clean cut boundary.
- For each piece, work out the matching source time in the main camera and add that camera's offset to get the alt or demo source time.
- Overwrite those pieces onto V2 with their audio off.
- Josh can then trim, extend or delete any of them in Premiere like normal clips.

---

## 4. Interview

This builds a new edit from separate recordings, in the order of a rough script. The typical case is a host who records intros and questions as separate clips, plus a recording of each guest. Angles doesn't fit, because it assumes every camera captured the same moment. Here the pieces come from different times and get put in order one after another.

People recorded together on camera at the same moment are an Angles job (cut to whoever is talking), not this one.

### Setup step

- The Interview tile opens a People list. Each person has a name, a role (Host or Guest) and the clips they're in.
  - It starts with one Host and one Guest.
  - Add guest adds another person.
  - Every person can be renamed or removed.
- **Pick clips.** This opens a picker of every video in the Premiere project (read through the bridge by walking the project bins, not just the timeline). It has thumbnails, durations and a search box. A clip can belong to one person only.
- **Script.** A box to paste or open a plain text file. The script is rough on purpose. Lines usually start with a name, like "Host: so I spoke with Daniel" or "Daniel: the bit where he talks about his first promotion". Lines in brackets are notes. The text can be exact words, a paraphrase or a description, and Claude interprets it.
- Save the people, clips and script with the project so Josh can come back to it.

### Transcribe

- Transcribe every picked clip on the PC with the existing transcription queue. Show progress per clip on the setup screen, and reuse transcripts that already exist.
- Run the acoustic profile on each clip too, so every piece can be cleaned and every boundary snapped to a natural break.

### Plan (one Claude call)

To keep tokens down, Claude never sees word-level transcripts.

- Code first splits each transcript into numbered sentences, each with its speaker, clip and time. An hour of guest audio is roughly 15 thousand tokens this way.
- Claude gets the script, the people and the sentence-level transcripts. It returns an ordered list of pieces, each with these fields:
  - the speaker
  - the clip
  - the first and last sentence
  - an optional trim note ("drop the first clause")
  - a confidence (high, medium, low)
  - the script line it answers
- For host lines recorded several times, Claude picks the last complete take unless the script says otherwise.
- Use `models.interview`, default Sonnet. The cost meter shows the result, and a long interview should come in at a few cents.
- **Free shortcut.** Before calling Claude, code tries to match script lines that are near-exact quotes with a fuzzy word match. Lines that match strongly are sent to Claude as already placed, so it only has to work out the rest.

### Tidy each piece (on the PC)

- Turn sentence ranges into word ranges, apply any trim notes and snap both ends to the best natural break, using the cut point rules from Angles.
- Run Clean cut inside each piece with the current pace settings, so pauses and breaths go.
- Add a short pad at each join.
- A **Match loudness** switch (on by default) sets each piece's clip gain so every speaker sits at the same level, measured with the existing dB profile.

### Review step

- Show the result as a script. Each piece is a row with the speaker's name, a thumbnail and the words that will be heard.
  - Low-confidence rows are marked red. Medium rows get a small amber dot.
  - The original script line shows faintly underneath, so Josh can see what Claude was answering.
- Each row has these controls:
  - Other take (for host lines with several takes)
  - Edit (opens that clip's transcript with the current piece highlighted, so Josh can highlight different words, reusing the Flubs selection code)
  - Move up, Move down and Remove
- An Add line box at the bottom sends one new script line to Claude for just that piece.
- The footer shows the total length and the number of pieces.

### Build

- Build "<name> - Josh Cut Interview" in a Josh Cut Pro bin, with each piece placed end to end on V1 and A1 in order.
- Rebuilding replaces it in place, the same as Clean cut.
- Save the piece list and its anchors. From then on the sequence counts as a cut with several sources, and Animations, B-roll, Zooms and Angles all work on top of it through the multi-source anchors from the foundation.

Note added when this was merged. Since 0.8.0 Clean cut no longer rebuilds a sequence. It cuts the open sequence in place after saving a backup, because rebuilding from the source files put the mic out of sync and brought back deleted camera audio. Interview still has to build a new sequence, since it assembles pieces that aren't on any timeline yet. Before building it, confirm how Josh wants a rebuild handled (replace the sequence, or back it up and build a fresh one). Place each piece's mic and camera from the timeline offsets the way the in-place cut keeps them, so the sync bug doesn't come back. The Premiere findings in CLAUDE.md apply (no extending trims, fresh clip lookups after every edit).

### Later options (only if Josh asks)

- A J-cut or L-cut switch that lets the next speaker's audio start a moment before the picture changes.
- A lower third with each guest's name the first time they appear, using the Lower third template.

---

## 5. B-roll

### Library

- In Settings, Josh points at his B-roll folder and confirms the library file name. The default is `broll-library.csv` inside that folder.
- The CSV opens in Excel and has these columns:
  - `file` (path relative to the folder)
  - `description`
  - `tags`
  - `mood`
  - `best_for`
  - `keep_audio` (yes or no)
  - `written_by` (scan or you)
- Two ways to fill it. Josh can write it himself, or press Scan.
- Scanning only happens when he asks. The B-roll screen has Scan all, Scan new files (anything in the folder not yet in the list) and Pick files.

### How a scan works

- For each clip, ffprobe it, pull 4 frames at 10, 35, 60 and 85 percent (640px JPEG) and send them with the file name to Claude.
- Ask for a description, tags, mood and what it's best for. Batch about 5 clips per call to save cost.
- The scan model is set in `config.json` under `models.broll_scan`. Default to a cheaper model than the deck model.
- Write rows marked `written_by = scan`. Never overwrite a row marked `you`, and if Josh edits a scanned row, flip it to `you` the next time the file is read.
- Show progress in the toast ("Described 14 of 40 clips"). It can be cancelled, and everything already described is kept.

### Auto B-roll plan

- Claude gets the clean transcript, the library descriptions (never the video) and the settings below.
  - **How often.** Light (about one a minute), Medium (about every 30 seconds) or Heavy (about every 15 seconds).
  - **Clip length.** 2 to 5 seconds, default 3.
- Claude returns placements, each with a start and end word, a file, a short reason and two alternates.
- Code checks that the clip is long enough and picks the source in-point (start 1 second in, or the middle for short clips).
- It avoids repeating a clip within 2 minutes and respects the overlap rules.

### Review step

Cards like the Animations screen, each with the frame at the chosen in-point, the quote it covers and the file name. Each card has Swap (cycles through the alternates), Longer, Shorter and Remove.

### Apply step

Place the clips on V3 in the Josh Cut sequence with their audio off, unless `keep_audio` is yes, in which case set them to minus 20 dB. They are ordinary clips Josh can cut around however he wants.

---

## 6. Later (already agreed with Josh)

- **Zooms.**
  - Slow push-ins on talking-head stretches longer than about 12 seconds.
  - Small punch-ins (about 110 percent) on emphasis words picked from the transcript.
  - Done as Motion scale keyframes on V1. Check whether the UXP API can set keyframes natively. Otherwise apply them through XML.
  - Light, Medium and Heavy, like the others.
- **Your look.**
  - Josh's own preset of Ultra Key, drop shadow, motion and a pre-made mask, applied to his camera.
  - Ask him to export it from Premiere as an effect preset first, then check what UXP can apply. If presets can't be applied, rebuild the same settings through component parameters.
  - This is for his setup only, with no general version.
- **One-file installer.**
  - A single installer that brings its own Python, ffmpeg, Playwright Chromium and the Whisper model, installs the .ccx and makes a Start menu shortcut.
  - The API key is entered on first run.
  - This is for when Josh gives the tool to someone else.
  - Ship with `show_costs` off.

Josh doesn't want features beyond these unless he asks.

---

## Testing

There's a basic harness in `tests/`.

- `mock_claude.py` is a fake Claude API. Point `DAJOSHI_CLAUDE_URL` at it.
- `ppro-stub.js` fakes the Premiere UXP API so `panel/preview.html` runs in a browser.
- `ui-flow.py` drives the panel preview and the app with Playwright.
- A sample recording and transcript are included.

The scripts were written on Linux, so adjust paths for Windows. Add a mock response for every new Claude prompt, and screenshot every new screen at 600 by 780 before handing it to Josh.

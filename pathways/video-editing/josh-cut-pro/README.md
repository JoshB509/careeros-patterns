# Josh Cut Pro 0.5

Josh Cut Pro has two parts. A small panel docks in Premiere and shows whether it's linked and which sequence is open. Everything else happens in the Josh Cut Pro window, which sits beside Premiere and edits the sequence you have open. Transcription, sound detection and rendering happen on this PC, and the only thing that leaves it is text sent to Claude.

## The tools

The home screen shows your open sequence at the top and a box for each tool. Zooms, Your look, Styles and B-roll are marked Soon.

1. **Clean cut.** Works from the audio alone, so it's ready in seconds. The waveform shows what goes in red and the silence level as a dashed gold line. Pick a pace (Calm, Measured, Paced, Energetic) or drag the sliders for the silence level, the longest pause kept and the margin after words. Breaths and noises that never get near your speaking level go too. The first cut makes one sequence called "<your sequence> - Josh Cut" in a Josh Cut Pro bin, and every recut rebuilds that same sequence from your original, whichever of the two you have open.
2. **Flubs and retakes.** The transcript is made in the background as soon as Josh Cut Pro sees your sequence. Claude reads it and marks abandoned takes, stumbles, repeated words and fillers in red. Highlight any words with the mouse and press Cut or Keep. Remove flubs rebuilds the same Josh Cut sequence with those words gone and your silence settings kept.
3. **Animations.** Add any notes, then Plan the animations. Each one shows as a card with a sketch of how it ends up. Change sends a note back to Claude for that one, and you can flip it between full screen and picture in picture or remove it. The PiP preview shows you in the gold box, with arrows and zoom to nudge yourself. Approve and build writes the deck in your house style, renders every press and brings in a sequence called "<your sequence> - Josh Cut Animations".

## Setting it up (once)

1. Double-click **DaJoshiCut_premierepro.ccx** and click Install in the Creative Cloud window. This updates the old DaJoshi Cut panel in place.
2. Restart Premiere and open **Window > UXP Plugins > Josh Cut Pro**. Dock the small panel wherever you like.
3. Double-click **Start Josh Cut Pro.bat**. The Josh Cut Pro window opens. Press the gear and paste your Claude API key, which is stored in `secrets.json` in this folder and nowhere else.

## Every time

Double-click **Start Josh Cut Pro.bat**, or press **Open Josh Cut Pro** in the Premiere panel once the helper has been started. No console window stays open. Closing the Josh Cut Pro window leaves the helper running so Premiere stays linked, and **Quit Josh Cut Pro** in Settings stops it completely. If it ever stops on its own it restarts itself, and `Projects\helper.log` has the details.

## Tuning

`config.json` holds the defaults for the camera box position (`pip.box`), which Claude model does each job (`models`) and how many animations are built at once (`parallel_builds`). Quit and restart Josh Cut Pro after changing it, or after editing `helper\prompts.py`, which holds the instructions Claude follows.

## Good to know

- Transcription uses your graphics card if your PC has a supported NVIDIA one, otherwise every processor core. `whisper` in `config.json` can force one or the other.
- Rendered animation clips are cached, so changing one animation only rebuilds that one.
- Like DaJoshiResolve, the helper pauses if OBS is open, to protect a recording in progress.
- `window` in `config.json` sets the window size, 600 by 780 by default.
- The window opens in Microsoft Edge app mode, so it has no tabs or address bar.
- Each recording gets its own folder in `E:\Videos\DaJoshiCut\Projects` with the transcript, the cuts, the shot list, the sketches, the deck and every sequence file.

# Cut decision engine

## Evidence summary
Executive: 15 kept clips, 14 internal deletions plus outer trims; native 408.732925 s. Retained 82 low-energy runs >= 300 ms, 21 >= 450 ms. A 1.07 s gap became about 670 ms; current default acoustic replay left 370 ms. Some retake handles measure around 90 ms incoming and 130–150 ms outgoing. These are examples, not universal padding.
Data: 44 narration pieces plus 6 room-tone inserts, 50 items, 987.432346 s. Only 38 source-removal regions. Added room tone 4.499996 s. Later 9 changes remove 31.733302 s, including script changes rather than silence alone. Retained 210 low-energy runs >= 300 ms, 73 >= 450 ms.
Thresholds/binning are recorded in datasets. Retention does not prove dramatic intent.

Data current-tool baseline reported 9/210 retained pauses shortened, 3.55 s lost. 810 ms and 780 ms became 240 ms. All 7 kept sound candidates survived; only 3/6 removed candidates were caught. This was 48 kHz cached PCM/10 ms acoustic replay, not production 16 kHz decoding, Claude decisions or native rendering. Preserve/reproduce the receipt, not a semantic accuracy claim.
No study listening pass occurred. Nonverbal candidates are NOT confirmed coughs. Missing ASR words do not establish silence. ASR word-count differences are not exact deletions.

## Decision pipeline
1. Decode chosen good mic locally, preserving all timestamps.
2. Transcribe/align words; retain confidence and gaps, protect soft onset/final consonants.
3. Detect candidate gaps/sounds using noise/energy, optional VAD, spectral evidence and lexical coverage. Generate measurements, not destructive edits.
4. Propose take groups. Distinguish abandoned restarts from intentional repetition, emphasis, lists, paraphrase and separate sentences. Repeated strings alone are insufficient.
5. Label nonverbal candidates separately: cough, throat_clear, breath, click, rustle, speech, other, uncertain. Untranscribed sound may overlap a word.
6. Decide Keep/Remove/Shorten with reasons and separate acoustic, alignment and editorial uncertainty. Do not invent calibrated percentages.
7. Refine safe boundaries after semantic decisions. Retake handles are not desired durations for meaningful pauses.
8. Present all decisions and uncertainties; construct the final edit only from the approved revision.

## Pauses
Keep ordinary same-take pauses unless there is evidence to shorten. Evaluate thought boundaries, rhetorical questions, setup/payoff, emphasis and delivery. Context/prosody rules are hypotheses still needing validation.
The early 700 ms review trigger is not a hard maximum or an automatic cut rule. No single dB/duration setting reproduces both edits.
Show retained significant pauses and proposed shortenings. Capture Josh's explicit choices as labels without retroactively editing approved work.

## Coughs/throat clears
Clearly classified isolated coughs may default to Remove, staying visible as removed [cough]. Uncertain ones must be labelled [possible cough] or [unclassified sound] and reviewed if speech may be damaged. Do not delete every breath.
Executive event around 257.70–257.99 s was removed in the reference yet survived threshold variants. It is a useful listening fixture, still not a verified cough label.
Review full event bounds and nearby words, not only its loud core. Detecting absence of words is not detecting a cough.

## Boundaries
Use source clocks and sufficient lookahead/lookbehind. Store measured subframe bounds and applied frame bounds. Round once at a defined layer, protect words, prevent zero-length pieces/slivers/gaps/overlaps. Define microfades in the actual native output, not only temporary WAV previews.
Compare original and proposed joins. Optimize cadence and semantic completeness, not maximum removed duration.

## Room tone
Represent insertion separately. Source-contiguous seams with inserted room tone remove nothing. Store inserted media ID, in/out, output range, track and reason. Map transcript through inserted intervals without advancing original narration time. Expose [room tone added] when relevant. Never infer removed source from output gaps alone.

## Evaluation
Both videos are development fixtures. Manually label ambiguous sounds/pauses and use additional footage as held-out validation. Separate false speech removal, damaged boundaries, wrongly shortened natural pauses, missed unwanted material, wrong take/meaning, sync errors and review workload.
Audit disagreements instead of copying every historic edit. Record config/model/source hashes. Do not invent a pass-rate or "perfect" claim. Conservative suggestions and efficient review can deliver value before a validated classifier exists.


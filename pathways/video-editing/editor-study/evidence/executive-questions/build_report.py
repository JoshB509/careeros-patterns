from pathlib import Path
import json, statistics, html, math
import sys
sys.dont_write_bytecode=True
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Preformatted, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import inch

OUT=Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis')
M=json.loads((OUT/'measurements.json').read_text())
CUTS=json.loads((OUT/'every_cut.json').read_text())
REPLAY=json.loads((OUT/'acoustic_replay_summary.json').read_text())
SUP=json.loads((OUT/'report_supplement.json').read_text()) if (OUT/'report_supplement.json').exists() else {}
nodes=[]
def title(t): nodes.append(('title',t))
def h(t): nodes.append(('h',t))
def p(t): nodes.append(('p',t))
def bullet(t): nodes.append(('b',t))
def table(headers,rows,widths=None): nodes.append(('table',(headers,rows,widths)))
def code(t): nodes.append(('code',t))
def fig(file,caption,width=7.0): nodes.append(('fig',(file,caption,width)))
def page(): nodes.append(('page',None))

title('Executive questions clean cut analysis')
p('Empirical reference study and repeatable process specification | Josh | 10 November 2026')
p('The final edit of What to Say to Tough Executive Questions shows that the main task is choosing complete takes, then placing safe joins. Silence trimming alone cannot reproduce it. The proposed process should preserve a source time map, synchronize the good microphone, transcribe and align speech, remove abandoned takes, treat nonverbal events separately, and review uncertain joins before rendering.')
h('What the reference establishes')
table(['Measurement','Observed result'],[
 ['Good microphone source','553.646 s'],['Retained timeline audio','408.733 s across 15 clips'],['Decoded export audio','408.704 s'],['Internal source discontinuities','14 cuts removing 124.333 s'],['Head and tail trims','15.433 s and 5.147 s'],['Total source removed','144.913 s or 26.17%'],['Transcript-bearing removal regions','11 regions totaling 110.233 s'],['Source to export validation','45 sampled correlations across all 15 clips; minimum 0.9517']],[2.6,4.4])
p('Eleven internal regions contain repeated or abandoned speech. That is 88.66% of internally deleted duration, including the pauses inside those regions. The three remaining regions need more careful interpretation: an absence of Premiere transcript words does not establish silence or a cough.')
p('The asymmetric boundary pattern is useful as a starting point: approximately 90 ms before incoming activity and 130 to 150 ms after outgoing activity on the 11 retake joins, depending on threshold. It is not a universal phonetic rule or a validated production preset.')
p('Recommendation: build a conservative proposal pipeline with a review queue. Do not globally raise the acoustic threshold to -50 or -45 dBFS, and do not treat the current sounds switch as a cough classifier. No production files or settings were changed for this study.')

page(); h('Reference and measurement method')
p('Reference selection matters. The current project and export map to 15 retained clips and 408.733 s of timeline audio. Older notes describing 14 clips or roughly 413 s are not the current reference. The analysis uses the direct A1 source discontinuities in the final Premiere project, rather than inferring edit decisions from overall duration.')
p('The source is the enhanced Wireless PRO WAV used in the final A1 edit, not a separately verified raw microphone recording. Source PCM was read at 48 kHz. Its 10 ms RMS p10 is -87.61 dBFS and p95 is -21.00 dBFS; these describe an enhanced signal, not the physical room noise floor. Calibrate again if the raw recording or enhancement chain changes.')
p('Premiere stores 254016000000 ticks per second and approximately 8467191533 ticks per nominal 30 fps video frame. Preserve tick and sample coordinates; do not repeatedly round through displayed seconds. The sub-millisecond timing approximations do not justify adding or deleting content.')
bullet('For every retained clip, three independent positions were correlated against the export, for 45 total windows. Correlation windows were up to 1.4 s and evaluated at 16 kHz effective sampling. The matching export lag was 21.302 to 21.373 ms. This validates correspondence throughout the sequence but is not an exhaustive sample-by-sample or perceptual review.')
bullet('The 28.925 ms difference between timeline end and decoded export duration is recorded explicitly. It is not used to invent a missing edit or to rescale all source timestamps. Container, codec and final-sample behavior require separate checking when implementing export verification.')
bullet('Acoustic offsets use nonoverlapping 10 ms RMS windows in the native microphone PCM. At each source cut, the method searches up to two seconds backward or forward for a window above a stated level. Outgoing offset is the time from the last active window end to source out. Incoming offset is the time from source in to the next active window start.')
bullet('Offsets therefore measure threshold-level acoustic activity, not speech onset, consonant completion or word alignment accuracy. A 10 ms measurement grid, enhancement artifacts, breaths and quiet consonants affect them. Zero means activity reached the boundary at that threshold, not proof of an audible fault.')
bullet('Premiere words were associated with intervals by word midpoint. The mapped final transcript is the retained subset of source words, not an independently transcribed export. Independent source and export ASR should be retained separately and reconciled, not silently substituted for ground truth.')
page(); h('Synchronization and evidence quality')
h('Camera and microphone synchronization')
p('The project places microphone source time 3.6999963 s ahead of camera source time. Six 10 s speech-envelope checks using a 5 ms grid and 25 ms smoothing find 3.705 to 3.710 s, with correlations 0.830 to 0.886. This corroborates the project offset within one nominal 30 fps frame. Different processing creates about 5 to 10 ms acoustic ambiguity; these checks do not prove lip sync, establish drift or justify retiming.')
p('This approximately 3.7 s camera/microphone relationship is separate from the approximately 21.3 ms microphone/export decoded-audio lag. The two offsets must never be substituted for each other.')
h('Evidence classes')
table(['Class','How this report uses it'],[
 ['Measurement','Project intervals, durations, RMS offsets, source/export correlations and replay interval intersections.'],['Inference','Repeated or abandoned take interpretation from text sequence and source chronology.'],['Proposal','Architecture, candidate padding, event safeguards and acceptance tests that still need evaluation.'],['Unresolved','Exact phonetic boundaries, cough/throat-clear labels, subjective pacing and generalization to other recordings.']],[1.2,5.8])
p('A transcript can omit nonverbal events, hallucinate short words in noise, or place word boundaries outside a kept clip. Negative transcript-based lead values in the raw data are a warning about the proxy, not evidence that the editor intentionally cut through a syllable.')

page(); h('What silence means in this recording')
p('Three different questions must be kept separate. An amplitude detector can answer only the first one directly. The requested clean cut needs all three, with positive protection for quiet consonants and natural pauses.')
table(['Concept','Meaning and decision'],[
 ['Acoustic low level','Energy below a declared threshold in a declared window. It can include quiet speech or enhancement tails; it is not automatically removable.'],
 ['Non speech sound','A breath, cough, throat clear, room noise or click. The sound needs an event label and context. Low level is neither necessary nor sufficient.'],
 ['Editorial removable pause','A pause whose shortening improves this delivery without changing meaning, emphasis or pace. This is a contextual editorial judgment.']],[1.6,5.4])
p('Within intervals the editor retained, there are 82 fully retained runs at least 300 ms long with every 10 ms RMS bin below -50 dBFS. Together they total 32.32 s. Their median is 370 ms, p75 is 445 ms, p90 is 509 ms and maximum is 680 ms. Twenty-one last at least 450 ms and eleven at least 500 ms. These are level-defined quiet runs, not manually verified semantic pauses.')
p('At source 334.40 to 335.08 s, the editor keeps 680 ms after what are you hoping to see from it and before And now they get to explain. At 19.33 to 19.89 s, 560 ms remains after do not have the answer. Cut 7 shortens an approximately 1.07 s acoustic gap by 400 ms while retaining about 670 ms. The reference does not support cutting every pause over 450 ms.')
p('For a pilot on the same recording chain, a same-take quiet run over 700 ms could be a conservative review-candidate gate. It is an unvalidated starting point, not a universal cut threshold or permission to shorten the pause automatically. Retake joins need their own rules.')
fig('source_overview.png','Figure 1. Complete enhanced microphone source. Green regions are retained in the reference; white regions are removed. Source seconds are shown.',6.2)

page(); h('Every internal cut')
p('Source out is the end of the earlier retained interval. Source in is the beginning of the later one. Lead and tail below are acoustic offsets at -50 dBFS, in milliseconds. Times are rounded for reading; JSON retains precision. Final times refer to the Premiere timeline, before the observed export lag.')
rows=[]
for r in CUTS:
    rows.append([str(r['cut']),f"{r['final_s']:.3f}",f"{r['source_out_s']:.3f} to {r['source_in_s']:.3f}",f"{r['removed_s']:.3f}",f"{r['lead_ms_m50']:.1f}",f"{r['tail_ms_m50']:.1f}"])
table(['Cut','Final s','Source removal s','Removed s','Lead ms','Tail ms'],rows,[.4,.8,2.4,1.05,1.15,1.2])

page(); h('What was removed and why it matters')
labels={1:'Repeated opening claim',2:'Several abandoned attempts',3:'Short abandoned start',4:'Several scenario restarts',5:'Long gap with uncertain boundary speech',6:'Short repeated start',7:'Quiet pause shortening',8:'Repeated CEO reaction',9:'Repeated sentence start',10:'Abandoned wording',11:'Repeated sentence start',12:'Rephrased sentence',13:'Nonverbal candidate region',14:'Several closing restarts'}
for r in CUTS:
    if r['removed_words']:
        p(f"Cut {r['cut']} {labels[r['cut']]}. Premiere removed text: "+r['removed_words'].replace('  ',' '))
    else:
        p(f"Cut {r['cut']} {labels[r['cut']]}. No Premiere word midpoint falls in this removal interval. This is not a verified sound-event label.")
    if r['cut']==5:
        p('Independent source ASR places And across this region boundary. The cut may include an abbreviated or restarted word; a cough label would be unsupported.')
    if r['cut']==7:
        p('The removed 0.400 s is very quiet: whole-region RMS is -83.96 dBFS and no 10 ms bin exceeds -45 dBFS. This supports a quiet-pause interpretation, while subjective pacing still requires listening.')
    if r['cut']==13:
        p('A low-level burst near source 485.5 to 486.0 s makes this a review candidate. Waveform shape alone cannot distinguish a throat clear, breath, click or quiet speech.')
p('Independent offline medium.en ASR produced 1508 words for the original and 1331 for the export. It supports the eleven retake or abandoned-speech regions. It also retains you struggle to one, know: one appears to function as a list number in context and should not be deleted by a global repeated-word rule. The word-count difference is not an exact count of words deleted because recognition outcomes differ.')
p('The text above is preserved as ASR evidence, including awkward wording and errors. It is not a corrected editorial transcript. See the waveform atlas for all 14 intervals with full removed regions and both boundary handles.')

page(); h('Current cutter audit and replay')
p('The current path is helper/dajoshi_cut.py plan_cut into cleancut.acoustic_keeps. Its acoustic stage is an energy-based interval rule, not semantic take selection and not an event classifier.')
bullet('It computes 10 ms RMS, smooths power over 50 ms, estimates a p10 noise level and sets auto threshold to p10 + 5 dB, clamped between -65 and -20 dBFS. On this enhanced source the effective automatic threshold is -65 dBFS. It uses p95 as a reference speech level.')
bullet('Above-threshold runs separated by less than 150 ms are merged before filtering. All events shorter than 80 ms are dropped even when the optional sounds switch is off. With the switch on, events shorter than 1.2 s and quieter than p95 minus 11 dB are also dropped. These features do not identify coughs.')
bullet('Later pause merging and padding can reinclude an event that was previously dropped. Event protection and deletion therefore need an explicit interval representation that survives later stages.')
bullet('Defaults are maximum pause 450 ms, lead 80 ms and tail 100 ms. The UI sets lead to 0.8 times tail. The older 150 ms min_cut parameter is not the active algorithm.')
bullet('The flubs path uses transcript-word deletion ranges and generic language-model instructions to keep the final complete take while preserving emphasis. It has not learned this editor style, and does not automatically run acoustic cleanup afterward. Its boundary snap searches plus or minus 80 ms for low RMS with 20 ms word guards; its threshold parameter is unused.')
h('Replay against this reference')
p('All rows below use a 450 ms maximum pause and the optional sounds heuristic. The baseline rows use 80 ms lead and 100 ms tail. These are geometric disagreements with the reference, not proven speech loss or semantic errors.')
rows=[]
for v in REPLAY['variants']:
    if v['settings']['pad_before']==.08:
        rows.append([f"{v['threshold_db']:.0f}",str(v['internal_cuts']),f"{v['predicted_kept_s']:.2f}",f"{v['human_kept_removed_s']:.3f}",f"{v['human_removed_kept_s']:.3f}",str(v['cuts_entirely_inside_human_kept'])])
table(['Level dBFS','Cuts','Kept s','Reference kept removed s','Reference removed kept s','New gaps'],rows,[.8,.5,.8,1.6,1.7,1.2])
p('At the automatic threshold, the one wholly new gap inside retained material is 0.370 s. At -50, 14 such gaps total 4.840 s. At -45, 22 total 7.520 s. Raising the threshold finds more gaps but also moves further from the editor reference.')
p('Changing to 100 ms lead and 190 ms tail reduces reference-kept time removed to 0.742 s at -65, 4.105 s at -50 and 6.011 s at -45. Cut counts do not change. Across all nine tested variants, 59 to 67 s of reference-removed material remains. Padding or threshold tuning cannot replace take selection.')

p('Exact event overlap exposes a specific gap in the heuristic. Event 04 at source 257.70 to 257.99 s is fully retained at -65, -50 and -45 dBFS, although the editor removed it. Event 11 at 485.59 to 485.72 s is fully retained at automatic -65 and removed at -50 and -45. These remain unverified event candidates, not confirmed coughs. Raising the threshold does not reliably resolve event removal.')
p('Cut 7 also exposes the pause-policy difference. Its low-level source gap is 345.23 to 346.30 s, or 1.07 s. The editor retains 0.67 s. The default automatic replay, with 450 ms maximum pause, 80/100 ms padding and sounds enabled, removes 345.50 to 346.20 s and leaves 0.37 s. The -50 and -45 variants leave only 0.21 and 0.20 s. More aggressive thresholds shorten a pause that the reference preserves. This calls for a separate contextual pause policy, not just a different energy threshold.')


page(); h('Repeatable pipeline specification')
p('The output of this work is a design and testable process, not a deployed edit. The order below preserves enough evidence to explain and reverse every proposed deletion.')
h('1 Ingest and preserve coordinates')
p('Register original camera and microphone files with hashes, channel count, sample rate, rational frame rate, frame count, duration and time-base metadata. Preserve the originals. Define source camera time, microphone PCM sample time and edited output time as distinct coordinates; do not use rounded displayed timecode as the interchange format.')
h('2 Run the green screen pre step without retiming')
p('Background replacement should preserve source timestamps, rational frame rate, frame count and audio. The pre-step emits the processed video plus a sidecar describing its source and timing. If any frames are removed, repeated or retimed, it must emit an explicit piecewise map back to source. Reject a silently retimed result. Image-only processing is not permission to change recording duration.')
h('3 Choose and synchronize the good microphone')
p('Select the intended good mic explicitly or propose it for review. Match multiple separated speech anchors to camera audio, estimate offset and test affine drift. Model camera time as a + b times microphone time. Validate residuals near the beginning, middle and end; use a piecewise map or manual review if residuals exceed a stated tolerance. This recording\'s 21.3 ms source-to-export lag is not the camera-to-microphone offset and must not be reused as one.')
h('4 Transcribe and align the source')
p('Transcribe the full good-mic source, with word times and uncertainty. Align text back to PCM and retain raw ASR separately from corrected text. Keep short uncertain tokens and nonverbal spans as reviewable evidence. Use camera audio only as a sync or fallback source, rather than replacing a verified mic with mixed export audio.')
h('5 Propose repeated take removal')
p('Group nearby restarts using lexical overlap, syntax, repeated meaning and acoustic pauses. Propose retaining the last complete usable take, but check that earlier material adds no unique fact, qualification or intentional emphasis. The rule is a candidate-generation default, not always keep the last take. Record exactly what is removed and why. Send partial words, mixed complete takes and meaning changes to review.')
h('6 Build a separate event and pause track')
p('Before phrase merging, mark candidate breaths, coughs, throat clears, clicks, silence and uncertain speech on the source time axis. Keep event classification confidence separate from speech alignment confidence. Remove a nonverbal event only when its class and surrounding speech safety meet the approved pilot criteria. Otherwise retain and queue it.')
h('7 Refine joins then export proposals')
p('After semantic deletions, refine the outgoing and incoming sides independently using speech and event evidence. Preserve natural intra-phrase pauses and emphasis. Produce conservative EDL and JSON with source mappings, reason codes, confidence, uncertainty and review snippets. Apply only reviewed proposals to copies, then render and validate the result.')

page(); h('Boundary and event rules to test')
h('Boundary sensitivity')
rows=[]
for t in (60,55,50,45,40,35):
    rows.append([f'-{t}',f"{statistics.median(r[f'lead_ms_m{t}'] for r in CUTS):.2f}",f"{statistics.median(r[f'tail_ms_m{t}'] for r in CUTS):.2f}"])
table(['RMS threshold dBFS','Median incoming ms','Median outgoing ms'],rows,[2.2,2.4,2.4])
p('For only the 11 transcript-bearing retake regions, median incoming offset is 90.53 ms at both -50 and -45 dBFS. Median outgoing offset is 129.98 ms at -50 and 149.98 ms at -45. The all-cut median outgoing value of 189.71 ms at -45 includes longer pause-like joins. It should not become a universal 190 ms tail.')
p('The head trim keeps 46.68 ms before -50 dBFS activity or 56.68 ms at -45. The tail trim keeps 279.45 ms after -50 dBFS activity or 359.45 ms at -45. These end conditions differ from internal retake joins and are included in the head and tail evidence atlas.')
p('Cut 3 has only 3.5 ms before -50 dBFS activity. Cuts 5 and 13 have 20.3 and 10.5 ms. Cut 7 keeps about 670 ms of combined below-threshold lead and tail despite removing 400 ms. A fixed maximum pause across the whole recording would not preserve this pattern reliably.')

p('Use asymmetric 100 ms incoming and 150 ms outgoing padding as the first conservative candidate for a pilot, not as a measured optimum. Test 80/100, 100/150 and 100/190 side by side. Do not normalize every pause to their sum. The reference includes short leads, longer outgoing margins and a retained pause around 670 ms at cut 7.')
page(); h('Choosing a clean join')
p('Speech detection and boundary search serve different purposes. A speech-detection threshold helps propose protected speech intervals; a boundary-search level helps evaluate candidate edges only inside a region already judged safe. Do not use one global amplitude number to perform both jobs.')
p('Estimate local noise from validated non-speech windows rather than equating global p10 with the room floor. Use separate onset and offset thresholds, or hysteresis, plus agreement between ASR, voice activity detection, spectral cues and energy to protect speech. These are proposed engineering rules, not evaluated improvements in this study.')
h('Boundary search')
bullet('Use alignment to identify the first and last intended phonemes, then extend into safe background. A low-energy valley inside a fricative or quiet syllable is not a safe boundary just because RMS is low.')
bullet('Set a bounded search around each proposed word boundary and return multiple scored candidates. Treat short cut leads such as cut 3, and the ambiguous incoming regions at cuts 5 and 13, as required review cases. A 20 ms transcript guard does not establish phonetic safety.')
bullet('Separate join placement from pause policy. Between continuous intended phrases, retain the source pause unless a contextual rule proposes shortening it. A numerical ceiling alone cannot decide whether a pause is rhetorical, cognitive or an interruption.')
bullet('Keep any confirmed event removal as an explicit excluded interval. Later padding and phrase merging must not reinclude it silently. If safe padding would cross an excluded event or word, flag the conflict rather than overriding one stage invisibly.')
bullet('Quantize only at the output stage. Preserve sample-accurate audio ranges internally, derive video boundaries using the verified time map, and report any frame-rounding displacement. Audio and video edit lists must refer to the same intended content.')
p('Refine only within an approved safe non-speech band. Within that band, prefer a low-energy sample crossing and small amplitude discontinuity, while preserving sufficient handles. If needed, test an optional 2 to 5 ms fade confined to non-speech. That duration is a proposed engineering safeguard, not a measured editor preference. Never crossfade syllables or erase breaths implicitly.')
p('The largest measured raw source hard-splice sample jump across the 14 reference joins is -49.25 dBFS, at cut 13. This makes seam discontinuities measurable, but does not establish that a click is or is not audible. A zero-jump case is recorded as -200 dBFS in the diagnostic file; this is a numerical sentinel, not a physical noise reading. Listening and rendered-output checks remain necessary.')

page(); h('Cough and throat clear handling')
p('The current short-and-quiet heuristic is insufficient: coughs can be loud or adjacent to speech, while short quiet events can be legitimate words, consonants or breaths. Merging before classification can absorb an event into speech; later expansion can undo a removal. A separate event track and post-merge exclusion check are required.')
p('A candidate detector may combine event-model scores, transient shape, spectral features, speech probability and ASR alignment. These are proposed inputs, not a trained or evaluated classifier in this study. Keep a configurable policy for natural breaths rather than treating every non-speech event as unwanted.')
p('Build a human-labeled pilot with coughs, throat clears, breaths, clicks, quiet words and clean pauses, including examples adjacent to speech. Tune for preserving intended speech. Select a threshold only after estimating event precision, recall and false deletion rates on held-out recordings. A single reference edit cannot establish reliability.')
h('Candidate events found in this source')
p('Thirteen detectable acoustic events were at least 70% outside Premiere lexical timestamps. Eight fall in removed material and five in retained material. This is deliberately weak candidate selection, not thirteen coughs. Recognition and timing errors or quiet speech can explain some retained candidates.')
p('Priority event 04 has an above-threshold core at source 257.70 to 257.99 s and peak 10 ms RMS -27.14 dBFS. Event 11 has a core at 485.59 to 485.72 s and peak -36.17 dBFS. Both were removed in the reference and are not silence by energy. Neither is a validated cough or throat clear. Event 11 has weak energy extending toward 486.05 s, beyond its core and into the kept side before fuller speech around 486.10 s. Never cut only the detected core and assume the complete event is gone.')
p('Use the thirteen review WAVs and candidate spectrogram atlas to label these sounds by listening. Event labels remain provisional until then.')
h('Review queue fields')
p('For each candidate include source range, camera range, proposed output join, reason, raw transcript context, alignment confidence, event scores, old and proposed padding, threshold sensitivity, competing boundaries, and a short before-and-after audio snippet. Never replace an uncertain label with silence merely because ASR returned no words.')

page(); h('Implementation pseudocode')
p('The following is a proposed contract, not executable production code. Intervals are half-open and source sample indices are authoritative for audio. Every stage emits evidence and reversible decisions.')
code('''manifest = inspect_and_hash(camera, good_mic)
green = greenscreen_copy(camera, preserve_timestamps=True)
require_timing_match(green, camera)  # or explicit time map

anchors = match_speech_anchors(good_mic, camera.audio)
sync = fit_offset_and_drift(anchors)
if not sync_passes(sync): queue_sync_review(); stop_edit_apply()
time_map = compose_mic_camera_green_map(sync, green.map)

raw_asr = transcribe(good_mic)
aligned = align_with_uncertainty(raw_asr, good_mic)
events = detect_events_before_phrase_merge(good_mic, aligned)

retakes = propose_restarts(aligned, nearby_context=True)
for proposal in retakes:
    check_complete_take(proposal)
    check_unique_information_and_intentional_emphasis(proposal)
    proposal.boundaries = refine_both_sides(
        good_mic, aligned, events, candidate_pads=[(.10,.15)])
    route_uncertainty_to_review(proposal)

pauses = propose_contextual_pause_changes(aligned, retakes)
event_edits = propose_only_high_confidence_safe_events(events)
plan = combine_intervals(retakes, pauses, event_edits)
plan = resolve_overlap_and_protected_speech(plan)
assert_no_reintroduced_excluded_events(plan)
assert_no_unreviewed_uncertain_speech_deletion(plan)

edl, audit = export_plan(plan, time_map, retain_raw_times=True)
review = export_original_and_proposed_join_snippets(plan)
# Apply only approved plan to copies; originals remain unchanged.
rendered = render_copy(approved(plan), camera, good_mic, green)
validate_content_timing_joins_and_event_policy(rendered, audit)
''')
h('Minimum plan record')
p('Each decision needs an ID, source asset hash, microphone sample start/end, rational time base, mapped camera frame or timestamp range, retained take ID, reason code, evidence references, confidence and review status. Store measured boundary features separately from proposed settings. Include the exact algorithm version and parameter set so a later run can reproduce the plan.')
p('Suggested reason codes are RETAKE, ABANDONED_START, PAUSE_SHORTEN, COUGH_CANDIDATE, THROAT_CLEAR_CANDIDATE and MANUAL_REVIEW. Only confirmed labels should drop the CANDIDATE suffix. A rejection, keep decision or manual override should also remain in the audit log.')

page(); h('Quality assurance and acceptance')
h('Structural and synchronization checks')
bullet('Verify all 15 reference clip mappings and all 14 reference deletions from the saved intervals before changing algorithms. Assert chronological, nonoverlapping ranges and equality between kept plus removed durations and source duration, allowing only documented rounding.')
bullet('Check green-screen frame count and timestamps against the original. Test multiple mic/camera anchors and drift residuals. After rendering, compare known speech anchors across the entire output, not just its beginning.')
bullet('Report final sample count, audio duration, video duration and cumulative time-map error independently. Do not hide a mismatch by stretching or reinterpreting all timestamps.')
h('Content and listening checks')
bullet('Listen to original context and proposed joins at every candidate cut. Check clipped consonants, plosives, repeated fragments, unnatural breath transitions, clicks and pace. The waveform and ASR work in this study cannot certify these perceptual outcomes.')
bullet('Confirm that every removed repeated take is redundant and that the retained version is complete. Preserve meaningful hesitation and intentional repetition. Verify no unique fact, qualifier or instruction disappeared.')
bullet('Audit every event deletion separately. Review both detected events and a sample of retained material to catch false negatives. Label coughs and throat clears by listening, not transcript absence.')
h('Evaluation design')
p('Use this video for development and explanation, then evaluate on additional held-out raw recordings with different delivery pace, background noise and enhancement settings. Split by recording, not neighboring snippets, to avoid overfitting to one source. Report event precision and recall, false deletions of intended speech, missed retakes, join ratings, reference interval disagreement and review workload separately.')
p('A pilot acceptance gate should require zero confirmed intended-speech deletions in the reviewed pilot, all flagged cases resolved, no unexplained sync drift, and satisfactory listening checks. Zero errors in a finite sample is not a reliability guarantee. Select quantitative tolerance and confidence requirements with the human labels before production deployment.')
h('What is not established')
p('All 14 internal cuts were measured and their raw boundary waveforms inspected, along with both head and tail waveform plots, RMS and event evidence. No full perceptual listening pass was performed in this runtime. Cough and throat-clear classifications remain unverified. RMS offsets are not phonetic labels: uncertainty includes the 10 ms grid, threshold choice and output frame rounding. ASR boundaries can be uncertain by 100 ms or more. ASR can be wrong. Replay disagreements are not definitive semantic errors. The proposed settings, event model and green-screen integration have not been implemented or validated on held-out recordings. No claim of fully automatic editor-quality output follows from this single example.')
if SUP.get('asr_findings'):
    h('Independent transcription cross check'); p(SUP['asr_findings'])

page(); h('Evidence package and reproducibility')
p('The report is accompanied by machine-readable measurements and waveform evidence, so future implementation can compare decisions rather than rely on prose alone. Source seconds, final timeline seconds and frame indices are labeled explicitly.')
table(['File','Purpose'],[
 ['measurements.json','Source and reference paths, durations, method, sample rate and hashes.'],['clips.json','All 15 retained source and final timeline intervals, including Premiere ticks.'],
 ['reference_edl.json','15 validated monotonic keep ranges in source ticks, PCM samples, camera coordinates and contiguous output coordinates.'],['every_cut.csv and every_cut.json','Every internal cut, source removal range, text context and threshold-dependent lead and tail measurements.'],['correlation_checks.json','45 sampled source/export correspondence checks and observed lags.'],['every_cut_waveforms.pdf','Complete source overview plus one full evidence page for each of 14 internal cuts.'],['raw_waveform_boundaries.pdf','Actual PCM min/max at 1 ms resolution around every internal boundary.'],
 ['head_tail_trims.json and head_tail_waveforms.pdf','Measured head and tail trims and their waveform context.'],
 ['retained_pause_summary.json and retained_pauses.json','82 retained level-defined quiet runs and text context.'],
 ['camera_mic_sync.json','Six camera/microphone envelope checks, distinct from export lag.'],['acoustic_replay_summary.json','Nine current-cutter threshold and padding variants with geometric reference disagreements.'],
 ['acoustic_replay_ranges.json','Exact replay keep ranges, event overlaps, and implementation and configuration hashes.'],['premiere_source_words.json and mapped_final_words.json','Raw Premiere word evidence and retained-word mapping.'],['asr_original and asr_final JSON and TXT','Independent offline source and export transcription evidence.'],
 ['nonverbal_candidates JSON and CSV','13 provisional event candidates, not confirmed cough labels.'],
 ['review_audio and nonverbal_candidate_spectrograms.pdf','Review WAV snippets and spectrograms for human event verification.'],['video_asset_hashes.json','SHA256 identifiers for the original camera recording and final export.'],
 ['reference_splice_jumps.json','Raw hard-splice sample-jump diagnostic; not an audible-click verdict.'],
 ['measure_cuts.py','Measurement and waveform-generation source for the reference study.']],[2.7,4.3])
page(); h('Source integrity and next step')
h('Original assets')
p('Microphone: '+M['source'])
p('Final export: '+M['final'])
p('Premiere project: '+M['project'])
h('Integrity checks')
for path,digest in M['sha256'].items():
    p(Path(path).name+' SHA256 '+digest)
p('The source WAV and project hashes were rechecked after analysis and were unchanged, as recorded in originals_unchanged_check.json. SHA256 identifiers for the original camera recording and final export are also recorded in video_asset_hashes.json. Together, these identify the measured assets for a formal regression fixture.')
for asset in json.loads((OUT/'video_asset_hashes.json').read_text()):
    p(Path(asset['path']).name+' SHA256 '+asset['sha256'])
h('Next implementation step')
p('Create a test-only planner that consumes preserved source timing, good-mic PCM and aligned transcripts, then outputs a reviewable JSON/EDL without altering the original project. Reproduce the 14-cut evidence fixture first. Add the separate event track and conservative boundary candidate ranking, then evaluate on a human-labeled pilot and held-out recordings before making production settings changes.')
if SUP.get('closing_note'): p(SUP['closing_note'])

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportTitle',fontName='Helvetica-Bold',fontSize=22,leading=26,spaceAfter=12,textColor=colors.black))
styles.add(ParagraphStyle(name='ReportHeading',fontName='Helvetica-Bold',fontSize=13,leading=16,spaceBefore=10,spaceAfter=6,textColor=colors.black,keepWithNext=True))
styles.add(ParagraphStyle(name='ReportBody',fontName='Helvetica',fontSize=9.5,leading=13.0,spaceAfter=7,textColor=colors.black))
styles.add(ParagraphStyle(name='ReportBullet',parent=styles['ReportBody'],leftIndent=11,firstLineIndent=-7))
styles.add(ParagraphStyle(name='ReportCell',fontName='Helvetica',fontSize=8.6,leading=10.8,spaceAfter=0))
styles.add(ParagraphStyle(name='ReportCellHead',parent=styles['ReportCell'],fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='ReportCaption',fontName='Helvetica',fontSize=8.5,leading=11,spaceAfter=8,textColor=colors.HexColor('#444444')))
styles.add(ParagraphStyle(name='ReportCode',fontName='Courier',fontSize=8.1,leading=11,spaceAfter=8))
story=[]; txt=[]; htmlparts=[]
E=lambda t: html.escape(str(t)).replace('\n','<br/>')
for kind,data in nodes:
    if kind=='title':
        story.append(Paragraph(E(data),styles['ReportTitle'])); txt.extend([data.upper(),'']); htmlparts.append('<h1>'+E(data)+'</h1>')
    elif kind=='h':
        story.append(Paragraph(E(data),styles['ReportHeading']));txt.extend(['',data.upper(),'']);htmlparts.append('<h2>'+E(data)+'</h2>')
    elif kind in ('p','b'):
        prefix='- ' if kind=='b' else ''
        story.append(Paragraph(E(prefix+data),styles['ReportBullet' if kind=='b' else 'ReportBody']));txt.extend([prefix+data,'']);htmlparts.append('<p>'+E(prefix+data)+'</p>')
    elif kind=='table':
        heads,rows,widths=data; cells=[[Paragraph(E(x),styles['ReportCellHead']) for x in heads]]+[[Paragraph(E(x),styles['ReportCell']) for x in r] for r in rows]
        t=Table(cells,colWidths=[v*inch for v in widths] if widths else None,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef2')),('TEXTCOLOR',(0,0),(-1,-1),colors.black),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#7a8b96')),('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#c8d1d7'))]))
        story.extend([t,Spacer(1,9)]);txt.append(' | '.join(heads));txt.extend(' | '.join(str(c) for c in r) for r in rows);txt.append('')
        htmlparts.append('<table><thead><tr>'+''.join('<th>'+E(x)+'</th>' for x in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+E(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table>')
    elif kind=='fig':
        name,cap,width=data
        from PIL import Image as PILImage
        im=PILImage.open(OUT/name); w,hg=im.size; iw=width*inch
        story.extend([Image(str(OUT/name),width=iw,height=iw*hg/w),Paragraph(E(cap),styles['ReportCaption'])]);txt.extend(['['+name+']',cap,'']);htmlparts.append('<figure><img src="'+html.escape(name)+'"><figcaption>'+E(cap)+'</figcaption></figure>')
    elif kind=='code':
        story.append(Preformatted(data,styles['ReportCode']));txt.extend([data,'']);htmlparts.append('<pre>'+E(data).replace('<br/>','\n')+'</pre>')
    elif kind=='page': story.append(PageBreak());txt.extend(['','-'*72,'']);htmlparts.append('<div class="break"></div>')

def footer(canvas,doc):
    canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#555555'));canvas.drawString(0.65*inch,.35*inch,'Executive questions clean cut analysis');canvas.drawRightString(7.85*inch,.35*inch,str(doc.page));canvas.restoreState()
pdf=OUT/'executive_questions_clean_cut_report.pdf'
doc=SimpleDocTemplate(str(pdf),pagesize=(8.5*inch,11*inch),leftMargin=.65*inch,rightMargin=.65*inch,topMargin=.58*inch,bottomMargin=.58*inch,title='Executive questions clean cut analysis',author='dot',subject='Reference measurements and proposed repeatable clean cut process')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
(OUT/'executive_questions_clean_cut_report.txt').write_text('\n'.join(txt),encoding='utf8')
css='''body{font-family:Arial,sans-serif;max-width:1050px;margin:45px auto;padding:0 32px;color:#111;line-height:1.5}h1{font-size:30px;line-height:1.2}h2{font-size:20px;margin-top:28px}p{margin:12px 0}table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0}th{background:#e8eef2}td,th{text-align:left;padding:8px;vertical-align:top;border-bottom:1px solid #c8d1d7}img{max-width:100%}figcaption{color:#444;font-size:13px}pre{background:#f4f6f7;padding:18px;white-space:pre-wrap;font-size:13px}.break{margin:42px 0}@media print{body{margin:0;max-width:none}.break{break-before:page}h2{break-after:avoid}tr,figure{break-inside:avoid}}'''
(OUT/'executive_questions_clean_cut_report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Executive questions clean cut analysis</title><style>'+css+'</style><body>'+''.join(htmlparts)+'</body></html>',encoding='utf8')
print(json.dumps({'pdf':str(pdf),'paragraph_nodes':len(nodes),'text_characters':len('\n'.join(txt))}))

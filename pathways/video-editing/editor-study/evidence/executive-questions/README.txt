EXECUTIVE QUESTIONS: CLEAN-CUT STUDY AND IMPLEMENTATION SPECIFICATION
10 November 2026

START HERE
1. Read executive_questions_clean_cut_report.pdf (full technical report).
2. every_cut.csv gives every internal edit; reference_edl.json gives all 15 kept source spans and synchronized camera/output coordinates.
3. every_cut_waveforms.pdf shows the complete deleted region and both boundary handles for all 14 internal cuts. raw_waveform_boundaries.pdf shows actual PCM min/max near every cut. head_tail_waveforms.pdf covers the two outer trims.
4. retained_pause_summary.json and retained_pauses.json contain the pauses that the editor chose to KEEP, essential counterexamples to aggressive silence removal.
5. For sound-event labels, listen to review_audio/*.wav while referring to nonverbal_candidates.json and fill event_annotation_template.csv. These are candidates, not verified coughs. A timestamped ASR gap is not proof of silence or a nonverbal sound.

WHAT THIS PACKAGE IS
A measured reference dataset and a proposed repeatable pipeline: preserve timestamps through green-screen preprocessing; synchronize the good microphone; transcribe and align; propose abandoned-take removals; classify nonverbal events separately; preserve contextual pauses; refine independent leads/tails; emit a reversible edit plan and review queue; render copies and verify.

WHAT IT IS NOT
It is not a deployed automatic editor, a validated cough classifier, or proof that every join sounds good. No perceptual listening pass was possible in this runtime. All 14 internal boundaries and the head/tail boundaries were measured and their waveform plots visually inspected. Event labels require human verification, and reliability requires additional held-out recordings. No production settings or original media were changed.

EVIDENCE
The measured current edit is 408.732925 seconds in Premiere and 408.704 decoded audio seconds in export.mp4, from a 553.646333-second enhanced Wireless PRO source. It contains 15 kept clips, 14 internal cuts, and head/tail trims. Do not use historical 413-second edit notes as this reference. Asset SHA256 values are in measurements.json and video_asset_hashes.json. Integrity checks are in originals_unchanged_check.json.

asr_original.json/.txt and asr_final.json/.txt are independent local faster-whisper medium.en results, with word timestamps. They are not manually corrected transcripts. asr_cut_comparison.json contains aligned cut context. premiere_source_words.json and mapped_final_words.json preserve a separate Premiere-derived evidence source. Do not treat differences in ASR word counts as exact deleted-word counts.

acoustic_replay_summary.json compares nine existing-tool parameter variants against the editor's reference. acoustic_replay_ranges.json stores exact ranges and candidate event intersections plus code/config hashes. These are geometric disagreements, not semantic error rates.

REPRODUCIBILITY
The measurement Python scripts retain the verified local asset paths and assume NumPy, SciPy, Matplotlib, the bundled FFmpeg, and the existing Premiere XML parser in the original project's reproducibility folder. They are analysis scripts, not production clean-cut implementation. The report supplies the proposed interfaces and pseudocode for that future implementation. The original media and large decoded PCM arrays are intentionally not included in this package; the asset manifest identifies them. HTML is an editable report source and uses source_overview.png alongside it. The TXT version is also editable.

ANNOTATION
For each event, label cough / throat_clear / breath / speech / click / rustle / silence / other / uncertain. Record the full event bounds, not only the above-threshold core. Check the supplied neighboring context and expand the listening window in the original if needed. A sound just before a word can overlap its onset; retain and flag uncertain speech-adjacent cases rather than truncating the word.

Use recording-level train/development/test splits. Protect intended speech and natural pauses as first-class negative examples. The one source in this package is a development reference, not a held-out reliability evaluation.

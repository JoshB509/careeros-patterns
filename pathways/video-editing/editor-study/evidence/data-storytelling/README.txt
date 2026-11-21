DATA STORYTELLING: MEASURED STUDY EVIDENCE
10 November 2026

This is a research dataset, not final process instructions or a deployed editor. No original media or project was changed by these scripts.

measurements.json: numerical summary and evidence limits.
base_every_cut.csv/json and final_every_cut.csv/json: all38 source discontinuities in each edit, with exact original/output coordinates, before/removed/after Premiere transcript and energy-derived handles at six comparison thresholds.
base_to_final_changes.json: all9 later removals, 31.7333s total, plus6 added room-tone beats,4.5000s total. Later script edits are separate from original clean-cut decisions.
every_final_cut_waveforms.pdf: source overview plus38 actual final source removals.
retained_pauses.csv/json: all210 quiet runs >=300ms retained in final narration at -50dBFS,10ms RMS. shortened_quiet_gaps.json contrasts five edited quiet intervals.
nonverbal_candidates.csv/json and nonverbal_candidate_spectrograms.pdf:13 acoustic events mostly outside guarded lexical ASR words,7 kept/6 removed. These are NOT verified coughs.
boundary_review_flags.json:23 energy/timestamp review flags, not confirmed lost syllables.
review_audio/:13 event excerpts,12 longest retained-pause excerpts,and8 boundary excerpts.
head_tail_trims.json: outer cuts and ASR-overlap caveat.
correlation_checks.json:132 final-export/narration correspondence windows, minimum0.9586, median0.9927, constant decoded-audio lag~21.3ms.
camera_mic_sync.json: independent seven-point amplitude-envelope check supports mic clock= camera clock+6s, not visual lip-sync validation.
source_integrity_hashes.json: SHA256 identities for source mic,base/current projects and export.

Current final is987.432346s in Premiere and987.413333s decoded export audio. Historical1019.532s receipts are stale.44 narration pieces plus6 room-tone pieces are50 audio items across A1/A2, but only38 source deletions.5 narration seams are continuous-source splits (4 straddle room-tone insertions).

No perceptual listening pass or manual transcript correction was performed. Energy gaps do not establish editorial intent,and missing ASR words do not prove silence. Source overview PNG was visually inspected; Both PDF atlases had their first and last pages rendered with Poppler at 90 dpi and visually checked: no clipped labels, blank pages, missing glyphs or unreadable plots found. This is limited four-page QA, not full-page review. No universal threshold or performance accuracy claim is established.

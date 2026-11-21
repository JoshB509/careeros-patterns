# Data acoustic baseline replay: inspection record
This document records the earlier read-only inspection report. No machine-readable replay receipt was saved because that inspection was instructed not to modify files. It is not a newly executed test.

Inputs:
- C:\Users\you\Documents\Codex\2026-11-10\storytelling-cut-analysis\source_mono.npy
- retained_pauses.json in the same folder
- nonverbal_candidates.json in the same folder
- final_clips.json in the same folder
- E:\Videos\DaJoshiCut\helper\cleancut.py

Reported pure-function calls:
db = db_profile(x, 48000)
threshold, speech = levels(db)  # Verify actual return shape before reproducing.
keeps = acoustic_keeps(db, threshold, speech, {
    "max_pause": 0.45,
    "pad_before": 0.08,
    "pad_after": 0.10,
    "cut_sounds": true
})
These settings were taken from the installed config during that read-only inspection. Do not assume they remain current. No production settings were changed.

Reported results:
- 9 of 210 reference-retained pauses shortened, 3.55 seconds total.
- 0.81-second and 0.78-second retained gaps became 0.24 seconds each.
- All seven reference-kept nonverbal candidates survived.
- Three of six reference-removed nonverbal candidates were removed.

Limits:
Cached 48 kHz audio and 10 ms bins were used, not a full production 16 kHz decode. No Claude retake pass, native Premiere edit or perceptual listening occurred. Candidates are not verified cough labels. Reproduce with exact code/config/input hashes and save a full receipt before using these figures as automated regression assertions.


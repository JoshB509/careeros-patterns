# Evidence and provenance

## Executive Questions
Read evidence/executive-questions/README.txt and executive_questions_clean_cut_report.pdf. Full 14-cut dataset, outer trims, mapped transcripts, reference EDL, retained pauses, events, review WAVs, waveforms and scripts are included.
Native duration 408.732925 s; decoded export 408.704 s. Older 413 s notes are stale. Sync roughly 3.7 s mic-minus-camera is specific to this recording and not visual lip-sync proof.
Historical green-preprocessing suggestions are superseded by native Premiere direction.

## Data Storytelling
Read evidence/data-storytelling/README.txt, measurements.json and base_to_final_changes.json. final_nonremoval_seams.json identifies seams without deletion. Six room-tone inserts add 4.50 s. Current duration 987.432346 s, not historical 1019.532 s.
Key evidence includes exact native parameters/masks and paired source/export images, not a new key recreation. Recording-specific mic-camera offset is about 6 s.
Both source footage and final reference are represented by verified paths and provenance.

## Current-tool comparison
Executive acoustic replay JSON files are included.
Data replay was reported in plugin inspection:9/210 retained pauses shortened, 3.55 s total, and 3/6 removed nonverbal candidates caught. If a machine-readable Data receipt is absent, reproduce it before treating as a regression fixture. It used 48k/10 ms acoustic replay, not complete production 16k/Claude/native pipeline.
Geometric disagreement is not semantic classifier accuracy.

## Study limitations
No perceptual listening pass or manual transcript correction. Candidate cough/intent labels require review. Energy gaps and missing ASR words are insufficient. Acoustic correlations validate correspondence, not aesthetics.
Executive boundary plots were inspected; Data atlases had limited first/last-page QA. Existing hair samples are not proof of full-motion quality.
Review WAVs and annotation CSVs are intended to help establish actual labels.

## Included/excluded
Copies include study outputs and native reference projects. Excluded large camera/audio/export files and .npy PCM arrays remain local; transfer metadata/duplicate ZIPs/transient progress are excluded. No secrets.json, settings.json, Discord tokens or private credentials are copied.
Do not overwrite original reference projects. Copied .prproj files may still link original media; use safe new test revisions.
Copy manifest records source/destination hashes. Package manifest covers payload files. Verification proves readback integrity, not every editorial inference.


## Reproduction scripts
The original measurement scripts are copied unchanged. They contain hard-coded original output locations and import inspect_project.py from each original video's reproducibility folder. A dependency copy is included under each evidence/dependencies directory. For a new reproduction, copy/adapt the script to a new test output directory and resolve its dependency explicitly. Do not blindly rerun it over original study results.
The parser's standalone default project may refer to a different historical video; import its Project class with the explicitly verified input path instead of running its default main routine.
FFmpeg was referenced at E:\Videos\DaJoshiResolve\tools\ffmpeg.exe. NumPy, SciPy and Matplotlib were used for measurement. No new dependencies were installed during packaging.

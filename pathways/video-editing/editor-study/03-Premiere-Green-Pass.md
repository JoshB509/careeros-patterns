# Native Premiere green pass

## Proposed sequence hierarchy
- SOURCE_SYNC: original camera and good mic, documented synchronization.
- GREEN_MASTER: background, visible keyed presenter with mask/framing, separate shadow-only duplicate.
- CLEAN_CUT_rNN: pieces referencing GREEN_MASTER, with controlled synchronized mic routing.
- FINAL_ASSEMBLY_rNN: approved cut plus animations and final audio.

Names are proposed; adapt to current project IDs. Either carry the good mic through a controlled nest or place it in the cut sequence using the same map. Prove the route. Avoid nested audio duplication/camera audio leakage.

Use a single shared presenter-key source, not independently copied masters per cut. Changing Ultra Key in the master should propagate throughout the edit. Avoid Render and Replace or baked files that break propagation. Invalidate previews and queued renders after master changes.

## Latest shadow direction
Josh says the soft background shadow only needs a rough independent key. Do not require it to match the detailed presenter key or update its hair settings together. Preserve a separately adjustable duplicate. Large leftward offset comes from composition, not necessarily Drop Shadow Distance.

## Measured references, not universal presets
Exact serialized parameters/masks are in evidence/data-storytelling/key-evidence/native_effects_readback.json and copied projects.
Data presenter: Transparency 45; Highlight 52.04545; Shadow 50.22727; Tolerance 65.45454; Pedestal 100; Choke 7.72727; Soften 0; Contrast 0; Mid Point 50; Desaturate 25; Spill Range/Spill/Luma 50/50/50; Saturation/Hue/Luminance 100/0/100.
Executive presenter: Transparency 45; Highlight 5.28302; Shadow 46.79245; Tolerance 52.45283; Pedestal 61.50944; Choke 0; Soften 0. Other listed cleanup/adjustment parameters match Data.
Serialized key colors differ; use the correct typed API rather than guessing packed RGB semantics.

Data at 3840x2160 has background V1, shadow V2, presenter V3. Presenter position 1770, 1141 and scale 115%. Shadow position 826, 1376 and scale 100.8888855%; shadow opacity 52.7, direction 135, distance 5, softness 121.1111, Shadow Only true. Both have 17-node garbage masks in that reference.
Executive presenter position 1920, 1143, scale 116%; no full-head duplicate wall shadow. Its PiP frame shadow is a separate purpose.
Standard Motion bottom crop is zero in both references. Desk exclusion uses framing/masks; no verified universal crop percentage exists.

A native preset called Green Screen exists in the 25.0 profile, but differs materially from finished projects and includes Ultra Key only. It is not the entire desired composition.

## Native API route
Adobe documents frame export, effect creation and component parameter read/write on supported Premiere versions:
https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/exporter
https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/componentparam
https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/videofilterfactory
https://helpx.adobe.com/premiere/desktop/add-video-effects/apply-video-effects/create-effect-presets.html

Availability does not prove this effect's typed parameters, masks or render equivalence. Build/test the bridge on copied native projects. Prefer supported native operations over hand-editing compressed project XML. XMEML import alone is not proof that editable Ultra Key/masks/nests survive.

## Visual inspection loop
Export actual Premiere frames. Do not approximate Ultra Key through FFmpeg chromakey. Inspect full-frame and hair/hand/shoulder crops, dark edges, side poses, stray hairs and motion. Use matte views/checker backgrounds where supported.
Check holes in hair, aggressive choke, spill, halos, flicker and clipped hands. Change limited settings each iteration and record parameter values, source/frame times and render provenance.
Use a bounded iteration policy. If doubtful, show Josh examples rather than repeatedly stripping hair detail. Existing evidence is sampled exports, not full temporal proof.

## Native proof before completion
Save/reopen a test project. Change presenter Ultra Key once and verify at least three distant cut pieces update. Confirm shadow remains intact/independent and audio/durations/maps do not change. Compare preview and native export. Verify final project remains editable and media links resolve.


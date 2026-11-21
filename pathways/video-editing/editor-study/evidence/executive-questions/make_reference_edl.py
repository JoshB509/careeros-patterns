import sys,pathlib,json,numpy as np,gzip,xml.etree.ElementTree as E
p=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis');c=json.loads((p/'clips.json').read_text());x=np.load(p/'source_mono.npy');sr=48000;off=3.699996300087396;cuts=json.loads((p/'every_cut.json').read_text())
items=[]
for i,v in enumerate(c):
 items.append({'clip_id':i+1,'source_audio_start_tick':v['inp_ticks'],'source_audio_end_tick_exclusive':v['out_ticks'],'source_audio_start_sample':round(v['inp']*sr),'source_audio_end_sample_exclusive':round(v['out']*sr),'camera_source_start_s':v['inp']-off,'camera_source_end_s':v['out']-off,'camera_nominal_start_frame':round((v['inp']-off)*30),'camera_nominal_end_frame_exclusive':round((v['out']-off)*30),'output_start_tick':v['start_ticks'],'output_end_tick_exclusive':v['end_ticks'],'output_nominal_start_frame':round(v['start']*30),'output_nominal_end_frame_exclusive':round(v['end']*30),'label_status':'reference_kept_from_final_project_not_a_new_edit'})
result={'schema_version':1,'purpose':'Measured reference EDL only. This does not edit any media.','source_audio_sample_rate':sr,'premiere_ticks_per_second':254016000000,'nominal_export_frame_rate':{'num':30,'den':1},'reference_sequence_frame_ticks':8467191533,'camera_to_mic_offset_s':off,'intervals':'half-open [start,end)','clips':items,'validation':{'clips':len(items),'strictly_monotone_source':all(a['source_audio_end_tick_exclusive']<=b['source_audio_start_tick'] for a,b in zip(items,items[1:])),'contiguous_output':all(a['output_end_tick_exclusive']==b['output_start_tick'] for a,b in zip(items,items[1:]))}}
(p/'reference_edl.json').write_text(json.dumps(result,indent=2))
seams=[]
for r in cuts:
 left=x[round(r['source_out_s']*sr)-1];right=x[round(r['source_in_s']*sr)];seams.append(dict(cut=r['cut'],source_hard_splice_sample_jump_dbfs=float(20*np.log10(max(abs(right-left),1e-10))),left_sample=float(left),right_sample=float(right)))
(p/'reference_splice_jumps.json').write_text(json.dumps(seams,indent=2))
project=pathlib.Path(json.loads((p/'measurements.json').read_text())['project']);root=E.fromstring(gzip.decompress(project.read_bytes()));tags={e.tag for e in root.iter() if 'Transition' in e.tag};print('Transition tags',tags);print('JUMPS',[(s['cut'],round(s['source_hard_splice_sample_jump_dbfs'],2)) for s in seams]);print('EDL',result['validation'])

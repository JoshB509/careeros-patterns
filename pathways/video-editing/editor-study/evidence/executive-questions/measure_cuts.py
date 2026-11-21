import sys,json,pathlib,subprocess,wave,hashlib,csv,io
sys.dont_write_bytecode=True
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
OUT=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis')
ROOT=pathlib.Path(r'E:\CareerOS\12_YouTube\answering-exec-questions')
REPRO=ROOT/'video/Animation-Edit-v01-20261105/reproducibility'
sys.path.insert(0,str(REPRO))
from inspect_project import Project,T
FF=r'E:\Videos\DaJoshiResolve\tools\ffmpeg.exe'
SRC=ROOT/'Recorded/Input/00111_Wireless_PRO-esv2-50p-bg-10p-music-10p.wav'
FINAL=ROOT/'video/export.mp4'
PROJ=REPRO.parent/'Answering-Exec-Questions-Animation-Edit-v03.prproj'
proj=Project(PROJ);audit=proj.dump();seq=audit[0]
clips=next(t['items'] for t in seq['tracks'] if t['type']=='AudioTrackGroup' and t['index']==0)
for c in clips:
 for k in ['start','end','inp','out']:c[k+'_ticks']=c[k];c[k]=c[k]/T
with wave.open(str(SRC)) as w:sr=w.getframerate();x=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768
proc=subprocess.run([FF,'-hide_banner','-v','error','-nostdin','-i',str(FINAL),'-vn','-ac','1','-ar',str(sr),'-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=0x08000000)
y=np.frombuffer(proc.stdout,dtype='<f4').astype(np.float64)
np.save(OUT/'source_mono.npy',x.astype(np.float32));np.save(OUT/'final_mono.npy',y.astype(np.float32))
words=json.loads((REPRO/'source-words-0.json').read_text())
# Preserve extracted ASR as evidence, not corrected ground truth.
(OUT/'premiere_source_words.json').write_text(json.dumps(words,indent=2))
kept=[]
for i,c in enumerate(clips):
 for w in words:
  mid=(w['start']+w['end'])/2
  if c['inp']<=mid<c['out']:
   kept.append(dict(word=w['word'],source_start=w['start'],source_end=w['end'],start=max(w['start'],c['inp'])-c['inp']+c['start'],end=min(w['end'],c['out'])-c['inp']+c['start'],clip=i+1))
(OUT/'mapped_final_words.json').write_text(json.dumps(kept,indent=2))
for name,ws in [('premiere_original_transcript.txt',words),('mapped_final_transcript.txt',kept)]:
 (OUT/name).write_text('\n'.join(f"{w['start']:.3f}\t{w['end']:.3f}\t{w['word']}" for w in ws),encoding='utf8')
# Direct acoustic correspondence at three independent positions in every retained clip.
corr=[];hop=3
for i,c in enumerate(clips):
 dur=c['end']-c['start'];win=min(1.4,dur/4)
 for fraction in [.15,.5,.85]:
  off=max(.15,min(dur-win-.15,dur*fraction-win/2));ss=c['inp']+off;tt=c['start']+off
  a=x[round(ss*sr):round((ss+win)*sr):hop]
  lo=max(0,round((tt-.12)*sr));hi=min(len(y),round((tt+win+.12)*sr))
  b=y[lo:hi:hop];a=a-a.mean()
  cross=signal.correlate(b,a,mode='valid',method='fft'); cs=np.concatenate([[0],np.cumsum(b*b)]); sums=np.concatenate([[0],np.cumsum(b)])
  energy=cs[len(a):]-cs[:-len(a)]-(sums[len(a):]-sums[:-len(a)])**2/len(a)
  r=cross/np.sqrt(np.maximum(energy,1e-20)*np.sum(a*a));j=int(np.argmax(r))
  lag=(lo+j*hop)/sr-tt
  corr.append(dict(clip=i+1,source_s=ss,final_expected_s=tt,lag_ms=lag*1000,correlation=float(r[j])))
# 10 ms nonoverlapping RMS; source native full-scale reference.
step=480;bin_t=(np.arange(len(x)//step)+.5)*step/sr
rms=np.sqrt(np.mean(x[:len(bin_t)*step].reshape(-1,step)**2,axis=1));db=20*np.log10(np.maximum(rms,1e-10))
def acoustic_padding(t,side,threshold):
 # Threshold-level acoustic activity, not a phonetic speech label. Look back/forward at most 2s.
 sel=np.where((bin_t>=t-2)&(bin_t<t) if side=='tail' else (bin_t>=t)&(bin_t<t+2))[0]
 active=sel[db[sel]>=threshold]
 if not len(active):return None
 return round(max(0,(t-(bin_t[active[-1]]+.005)) if side=='tail' else (bin_t[active[0]]-.005-t))*1000,3)
def text_range(a,b):return ' '.join(w['word'] for w in words if a<=(w['start']+w['end'])/2<b).strip()
rows=[]
for i,(left,right) in enumerate(zip(clips,clips[1:]),1):
 a=left['out'];b=right['inp'];t=right['start'];mask=(bin_t>=a)&(bin_t<b)
 row=dict(cut=i,final_s=t,final_frame_30=round(t*30),source_out_s=a,source_in_s=b,removed_s=b-a,left_words=text_range(max(left['inp'],a-2.5),a),removed_words=text_range(a,b),right_words=text_range(b,min(right['out'],b+2.5)),removed_rms_dbfs=float(20*np.log10(np.sqrt(np.mean(x[round(a*sr):round(b*sr)]**2))+1e-20)),removed_active_fraction_m45=float(np.mean(db[mask]>=-45)),tail_word_proxy_ms=None,lead_word_proxy_ms=None)
 prior=[w for w in words if left['inp']<=(w['start']+w['end'])/2<a and w['word'].strip()]
 nxt=[w for w in words if b<=(w['start']+w['end'])/2<right['out'] and w['word'].strip()]
 if prior:row['tail_word_proxy_ms']=round((a-prior[-1]['end'])*1000,3)
 if nxt:row['lead_word_proxy_ms']=round((nxt[0]['start']-b)*1000,3)
 for th in [-60,-55,-50,-45,-40,-35]:
  row[f'tail_ms_m{abs(th)}']=acoustic_padding(a,'tail',th);row[f'lead_ms_m{abs(th)}']=acoustic_padding(b,'lead',th)
 rows.append(row)
with (OUT/'every_cut.csv').open('w',newline='',encoding='utf8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'every_cut.json').write_text(json.dumps(rows,indent=2))
(OUT/'clips.json').write_text(json.dumps(clips,indent=2))
(OUT/'correlation_checks.json').write_text(json.dumps(corr,indent=2))
(OUT/'timeline_all_sequences.json').write_text(json.dumps(audit,indent=2))
metadata=dict(source=str(SRC),final=str(FINAL),project=str(PROJ),source_duration_s=len(x)/sr,decoded_final_duration_s=len(y)/sr,timeline_end_s=clips[-1]['end'],sample_rate=sr,ticks_per_second=T,clips=len(clips),internal_cuts=len(rows),trim_start_s=clips[0]['inp'],trim_end_s=len(x)/sr-clips[-1]['out'],kept_duration_s=sum(c['out']-c['inp'] for c in clips),internal_removed_s=sum(r['removed_s'] for r in rows),source_words=len(words),mapped_words=len(kept),db_rms_quantiles={str(q):float(np.percentile(db,q)) for q in [1,5,10,25,50,75,90,95,99]},minimum_correlation=min(c['correlation'] for c in corr),lag_ms_range=[min(c['lag_ms'] for c in corr),max(c['lag_ms'] for c in corr)],sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SRC,PROJ]},method='Every internal source discontinuity from final Premiere A1. RMS 10ms native microphone PCM. 45 acoustic validation windows (3 per clip). No perceptual listening or cough labels implied.')
(OUT/'measurements.json').write_text(json.dumps(metadata,indent=2))
# All source edits visible on overview; detail pages show exact discarded region and both handles.
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
with PdfPages(OUT/'every_cut_waveforms.pdf') as pdf:
 fig,ax=plt.subplots(figsize=(12,6));ax.plot(bin_t,db,color='#384e65',lw=.4)
 for c in clips:ax.axvspan(c['inp'],c['out'],color='#66b57e',alpha=.25)
 ax.set(ylim=(-100,0),xlabel='Original enhanced Wireless PRO audio (seconds)',ylabel='10 ms RMS (dBFS)',title='Complete source: green = retained in final export, white = removed')
 fig.tight_layout();pdf.savefig(fig);fig.savefig(OUT/'source_overview.png',dpi=150);plt.close(fig)
 for row in rows:
  a=row['source_out_s'];b=row['source_in_s'];fig,axes=plt.subplots(3,1,figsize=(12,8.5),gridspec_kw={'height_ratios':[1.1,1,1]})
  for ax,(lo,hi,label,boundary) in zip(axes,[(a-1.4,b+1.4,'Full deleted region with context',None),(a-.8,a+.4,'Outgoing tail: cut line at source out',a),(b-.4,b+.8,'Incoming lead: cut line at source in',b)]):
   mask=(bin_t>=lo)&(bin_t<=hi);ax.plot(bin_t[mask],db[mask],color='#28435a',lw=.8);ax.axvspan(a,b,color='#dc6a54',alpha=.18);ax.axhline(-45,c='#999',ls='--',lw=.6)
   if boundary is not None:ax.axvline(boundary,c='#be3c2b',lw=1)
   ax.set(xlim=(lo,hi),ylim=(-100,-5),ylabel='RMS dBFS',title=label)
  axes[-1].set_xlabel('Source audio seconds, not final timeline time')
  title=f"Cut {row['cut']:02d} | Final {row['final_s']:.3f}s / frame {row['final_frame_30']} | Removed {row['removed_s']:.3f}s"
  fig.suptitle(title,fontweight='bold');fig.text(.06,.016,'Removed transcript: '+row['removed_words'][:180]+'\nThreshold line = -45 dBFS, a comparison level, not a validated speech/cough classifier.',fontsize=8)
  fig.tight_layout(rect=(0,.06,1,.96));pdf.savefig(fig);fig.savefig(OUT/f"cut_{row['cut']:02d}.png",dpi=130);plt.close(fig)
print(json.dumps(metadata,indent=2));print('CUTS')
for r in rows: print({k:r[k] for k in ['cut','final_s','removed_s','removed_words','tail_ms_m45','lead_ms_m45']})

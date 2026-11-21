import sys,json,pathlib,subprocess,wave,hashlib,csv,base64,struct
sys.dont_write_bytecode=True
import numpy as np
from scipy import signal
from scipy.ndimage import binary_closing
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
OUT=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\storytelling-cut-analysis')
ROOT=pathlib.Path(r'E:\CareerOS\12_YouTube\show-data-like-this')
REPRO=ROOT/'video/Animation-Edit-v01-20261102/reproducibility'
sys.path.insert(0,str(REPRO))
from inspect_project import Project,T
FF=r'E:\Videos\DaJoshiResolve\tools\ffmpeg.exe'
SRC=ROOT/'Recorded/Input/00108_Wireless_PRO-esv2-50p-bg-10p-music-10p.wav'
FINAL=ROOT/'video/Data Storytelling - Animation Edit v01.mp4'
BASE=ROOT/'video/Data storytelling.prproj'
PROJ=REPRO.parent/'Data-Storytelling-Animation-Edit-v01.prproj'
def save(name,data): (OUT/name).write_text(json.dumps(data,indent=2,default=lambda v:v.item()),encoding='utf8')
def csvsave(name,rows):
 if not rows:return
 with (OUT/name).open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def decode_words(p):
 d=base64.b64decode(p.root.find('.//TranscriptData').text)
 def fields(pos):
  v=pos-struct.unpack_from('<i',d,pos)[0]
  return {i:pos+o for i,o in enumerate(struct.unpack_from('<'+'H'*((struct.unpack_from('<H',d,v)[0]-4)//2),d,v+4)) if o}
 def target(v):return v+struct.unpack_from('<I',d,v)[0]
 def vector(v):
  v=target(v);return [target(v+4+i*4) for i in range(struct.unpack_from('<I',d,v)[0])]
 def string(v):
  v=target(v);n=struct.unpack_from('<I',d,v)[0];return d[v+4:v+4+n].decode()
 doc=fields(target(fields(struct.unpack_from('<I',d,0)[0])[0]));raw=[]
 for seg in vector(doc[0]):
  sf=fields(seg)
  for word in vector(sf[3]):
   wf=fields(word);s=struct.unpack_from('<q',d,wf[0])[0]/T;dur=struct.unpack_from('<q',d,wf[1])[0]/T
   raw.append(dict(word=string(wf[2]),start=s,end=s+dur))
 return raw
p=Project(PROJ);bp=Project(BASE);words=decode_words(bp);save('premiere_source_words.json',words)
audit=p.dump();baudit=bp.dump();save('final_all_sequences.json',audit);save('base_all_sequences.json',baudit)
def clips_of(seq):
 clips=[]
 for t in seq['tracks']:
  if t['type']!='AudioTrackGroup':continue
  for cc in t['items']:
   c=cc.copy();c['track']=t['index'];c['room_tone']='room tone' in c['name'].lower()
   for k in ['start','end','inp','out']:c[k+'_ticks']=c[k];c[k]=c[k]/T
   clips.append(c)
 return sorted(clips,key=lambda c:(c['start'],c['track']))
clips=clips_of(audit[0]);base=clips_of(baudit[0]);narr=[c for c in clips if not c['room_tone']]
save('final_clips.json',clips);save('base_clips.json',base)
with wave.open(str(SRC)) as w:
 sr=w.getframerate();channels=w.getnchannels();width=w.getsampwidth();frames=w.getnframes()
 assert width==2
 x=np.frombuffer(w.readframes(frames),dtype='<i2').reshape(-1,channels).mean(axis=1)/32768
proc=subprocess.run([FF,'-hide_banner','-v','error','-nostdin','-i',str(FINAL),'-vn','-ac','1','-ar',str(sr),'-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=0x08000000)
y=np.frombuffer(proc.stdout,dtype='<f4').astype(np.float64)
np.save(OUT/'source_mono.npy',x.astype(np.float32));np.save(OUT/'final_mono.npy',y.astype(np.float32))
step=round(sr*.01);n=len(x)//step;tt=(np.arange(n)+.5)*step/sr
rms=np.sqrt(np.mean(x[:n*step].reshape(-1,step)**2,axis=1));db=20*np.log10(np.maximum(rms,1e-10))
def text(a,b):return ' '.join(w['word'] for w in words if a<=(w['start']+w['end'])/2<b and w['word'].strip())
def padding(t,side,threshold=-45):
 sel=np.where((tt>=t-2)&(tt<t) if side=='tail' else (tt>=t)&(tt<t+2))[0];ac=sel[db[sel]>=threshold]
 if not len(ac):return None
 return round(max(0,t-tt[ac[-1]]-.005 if side=='tail' else tt[ac[0]]-.005-t)*1000,3)
def cuts(cs):
 rows=[];seams=[]
 for left,right in zip(cs,cs[1:]):
  a,b=left['out'],right['inp'];gap=b-a
  if gap<.0001:
   seams.append(dict(final_s=right['start'],source_gap_s=gap,timeline_gap_s=right['start']-left['end']));continue
  row=dict(cut=len(rows)+1,final_s=right['start'],source_out_s=a,source_in_s=b,removed_s=gap,timeline_gap_s=right['start']-left['end'],left_words=text(max(left['inp'],a-3),a),removed_words=text(a,b),right_words=text(b,min(right['out'],b+3)),removed_rms_dbfs=float(20*np.log10(np.sqrt(np.mean(x[round(a*sr):round(b*sr)]**2))+1e-20)))
  for th in [-60,-55,-50,-45,-40,-35]:row[f'tail_ms_m{abs(th)}']=padding(a,'tail',th);row[f'lead_ms_m{abs(th)}']=padding(b,'lead',th)
  rows.append(row)
 return rows,seams
bc,bs=cuts(base);fc,fs=cuts(narr)
save('base_every_cut.json',bc);csvsave('base_every_cut.csv',bc);save('final_every_cut.json',fc);csvsave('final_every_cut.csv',fc);save('final_nonremoval_seams.json',fs)
# Exact union/subtraction separates narration deletions from inserted room tone and edit splits.
def union(cs):
 spans=[]
 for a,b in sorted((c['inp'],c['out']) for c in cs):
  if spans and a<=spans[-1][1]+1e-7:spans[-1][1]=max(b,spans[-1][1])
  else:spans.append([a,b])
 return spans
def subtract(A,B):
 out=[]
 for a,b in A:
  pieces=[(a,b)]
  for c,d in B:
   nxt=[]
   for e,f in pieces:
    if d<=e or c>=f:nxt.append((e,f));continue
    if e<c:nxt.append((e,c))
    if d<f:nxt.append((d,f))
   pieces=nxt
  out.extend(pieces)
 return [dict(source_start=a,source_end=b,duration_s=b-a,words=text(a,b)) for a,b in out if b-a>1e-6]
changes={'removed_after_base':subtract(union(base),union(narr)),'restored_after_base':subtract(union(narr),union(base)),'room_tone_inserts':[c for c in clips if c['room_tone']]};save('base_to_final_changes.json',changes)
kept=np.zeros(n,dtype=bool);bkept=np.zeros(n,dtype=bool)
for c in narr:kept[(tt>=c['inp'])&(tt<c['out'])]=True
for c in base:bkept[(tt>=c['inp'])&(tt<c['out'])]=True
pauses=[];v=np.diff(np.r_[False,db<-50,False].astype(int))
for a,b in zip(np.where(v==1)[0],np.where(v==-1)[0]):
 if b-a<30:continue
 if np.all(kept[a:b]):
  ss=a*.01;ee=b*.01;c=next(c for c in narr if c['inp']<=ss+.005 and c['out']>=ss+.005)
  pauses.append(dict(source_start_s=ss,source_end_s=ee,duration_s=(b-a)*.01,final_start_s=c['start']+ss-c['inp'],threshold_dbfs=-50,left_words=text(max(0,ss-3),ss),right_words=text(ee,ee+3)))
save('retained_pauses.json',pauses);csvsave('retained_pauses.csv',pauses)
# Candidate events are solely acoustic energy outside guarded lexical timings, not perceptual diagnoses.
active=binary_closing(db>=-50,structure=np.ones(4));v=np.diff(np.r_[False,active,False].astype(int));spoken=np.zeros(n,dtype=bool)
for w in words:
 if w['word'].strip():spoken[max(0,int((w['start']-.05)/.01)):min(n,int(np.ceil((w['end']+.05)/.01)))]=True
cands=[];(OUT/'review_audio').mkdir(exist_ok=True)
for a,b in zip(np.where(v==1)[0],np.where(v==-1)[0]):
 if b-a<8 or float(np.mean(~spoken[a:b]))<.7:continue
 xx=x[a*step:b*step];k=float(np.mean(kept[a:b]));state='removed' if k<.05 else 'kept' if k>.95 else 'partly_removed';freq,power=signal.welch(xx,sr,nperseg=min(1024,len(xx)))
 c=dict(id=len(cands)+1,start_s=a*.01,end_s=b*.01,duration_s=(b-a)*.01,peak_10ms_dbfs=float(db[a:b].max()),rms_dbfs=float(20*np.log10(np.sqrt(np.mean(xx*xx)))),untranscribed_fraction=float(np.mean(~spoken[a:b])),retained_fraction=k,reference_decision=state,spectral_centroid_hz=float(np.sum(freq*power)/np.sum(power)),class_label='unreviewed_nonverbal_candidate',left_words=text(max(0,a*.01-3),a*.01),right_words=text(b*.01,b*.01+3))
 lo=max(0,c['start_s']-.6);hi=min(len(x)/sr,c['end_s']+.8);name=f"event_{c['id']:02}_{state}_{c['start_s']:.2f}s.wav"
 with wave.open(str(OUT/'review_audio'/name),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(x[round(lo*sr):round(hi*sr)],-1,.999969)*32768).astype('<i2').tobytes())
 c['review_file']='review_audio/'+name;c['review_context_start_s']=lo;cands.append(c)
save('nonverbal_candidates.json',cands);csvsave('nonverbal_candidates.csv',cands)
# Three acoustic correspondence windows per narration clip. Exclude room-tone inserts.
corr=[]
for i,c in enumerate(narr):
 dur=c['end']-c['start'];win=min(1.4,dur/4)
 for fraction in [.15,.5,.85]:
  off=max(.1,min(dur-win-.1,dur*fraction-win/2));ss=c['inp']+off;ts=c['start']+off;hop=3
  a=x[round(ss*sr):round((ss+win)*sr):hop];lo=max(0,round((ts-.15)*sr));hi=min(len(y),round((ts+win+.15)*sr));b=y[lo:hi:hop];a=a-a.mean()
  if len(b)<len(a):continue
  cross=signal.correlate(b,a,mode='valid',method='fft');cs=np.r_[0,np.cumsum(b*b)];sums=np.r_[0,np.cumsum(b)];energy=cs[len(a):]-cs[:-len(a)]-(sums[len(a):]-sums[:-len(a)])**2/len(a)
  rr=cross/np.sqrt(np.maximum(energy,1e-20)*np.sum(a*a));j=int(np.argmax(rr));corr.append(dict(clip=i+1,source_s=ss,expected_final_s=ts,lag_ms=((lo+j*hop)/sr-ts)*1000,correlation=float(rr[j])))
save('correlation_checks.json',corr)
kept_words=[]
for i,c in enumerate(narr):
 for w in words:
  if c['inp']<=(w['start']+w['end'])/2<c['out']:kept_words.append(dict(word=w['word'],source_start=w['start'],source_end=w['end'],start=max(w['start'],c['inp'])-c['inp']+c['start'],end=min(w['end'],c['out'])-c['inp']+c['start'],clip=i+1))
save('mapped_final_words.json',kept_words)
for name,ww in [('premiere_original_transcript.txt',words),('mapped_final_transcript.txt',kept_words)]:
 (OUT/name).write_text('\n'.join(f"{w['start']:.3f}\t{w['end']:.3f}\t{w['word']}" for w in ww),encoding='utf8')
summary=dict(source=str(SRC),final=str(FINAL),base_project=str(BASE),final_project=str(PROJ),sample_rate=sr,channels=channels,source_duration_s=len(x)/sr,export_decoded_audio_duration_s=len(y)/sr,base_duration_s=max(c['end'] for c in base),final_duration_s=max(c['end'] for c in clips),base_narration_clips=len(base),final_narration_clips=len(narr),room_tone_inserts=len(clips)-len(narr),room_tone_duration_s=sum(c['out']-c['inp'] for c in clips if c['room_tone']),base_internal_removals=len(bc),final_internal_removals=len(fc),base_narration_duration_s=sum(c['out']-c['inp'] for c in base),final_narration_duration_s=sum(c['out']-c['inp'] for c in narr),extra_narration_removed_s=sum(c['duration_s'] for c in changes['removed_after_base']),extra_narration_restored_s=sum(c['duration_s'] for c in changes['restored_after_base']),retained_pauses_count=len(pauses),retained_pauses_at_least_450ms=sum(c['duration_s']>=.45 for c in pauses),retained_pauses_at_least_700ms=sum(c['duration_s']>=.7 for c in pauses),longest_retained_pauses=sorted(pauses,key=lambda c:-c['duration_s'])[:12],candidate_events=len(cands),candidate_states={s:sum(c['reference_decision']==s for c in cands) for s in ['kept','removed','partly_removed']},correlation_min=min(c['correlation'] for c in corr),correlation_median=float(np.median([c['correlation'] for c in corr])),correlation_windows=len(corr),lag_ms_range=[min(c['lag_ms'] for c in corr),max(c['lag_ms'] for c in corr)],source_rms_dbfs_quantiles={str(q):float(np.percentile(db,q)) for q in [1,5,10,25,50,75,90,95,99]},method='All timeline source ranges examined; 10 ms native PCM RMS. Energy-defined pauses and ASR-gap event candidates are NOT verified intentional pauses or coughs. No perceptual listening pass. Room-tone inserts excluded from narration source deletion math.')
save('measurements.json',summary);print(json.dumps(summary,indent=2,default=lambda v:v.item()),flush=True)
# Evidence atlases for every actual final source removal and all nonverbal candidates.
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
with PdfPages(OUT/'every_final_cut_waveforms.pdf') as pdf:
 fig,ax=plt.subplots(figsize=(12,6));ax.plot(tt,db,lw=.35)
 for c in narr:ax.axvspan(c['inp'],c['out'],color='#66b57e',alpha=.25)
 ax.set(ylim=(-100,0),xlabel='Source microphone seconds',ylabel='10 ms RMS dBFS',title='Data Storytelling source: green = retained narration');fig.tight_layout();pdf.savefig(fig);fig.savefig(OUT/'source_overview.png',dpi=120);plt.close(fig)
 for r in fc:
  a,b=r['source_out_s'],r['source_in_s'];fig,axes=plt.subplots(3,1,figsize=(12,8.5))
  for ax,(lo,hi,label) in zip(axes,[(a-1.4,b+1.4,'Entire removal'),(a-.8,a+.4,'Outgoing tail'),(b-.4,b+.8,'Incoming lead')]):
   m=(tt>=lo)&(tt<=hi);ax.plot(tt[m],db[m],lw=.7);ax.axvspan(a,b,color='#dc6a54',alpha=.2);ax.axhline(-45,c='#999',ls='--',lw=.6);ax.set(xlim=(lo,hi),ylim=(-100,-5),ylabel='RMS dBFS',title=label)
  fig.suptitle(f"Cut {r['cut']:02d} | Final {r['final_s']:.3f}s | Source {a:.3f}-{b:.3f}s | Removed {b-a:.3f}s")
  fig.text(.05,.015,'Removed ASR context: '+r['removed_words'][:200]+'\nThreshold is a comparison level, not a speech/cough classification.',fontsize=8);fig.tight_layout(rect=(0,.06,1,.96));pdf.savefig(fig);plt.close(fig)
with PdfPages(OUT/'nonverbal_candidate_spectrograms.pdf') as pdf:
 for c in cands:
  a=max(0,c['start_s']-.4);b=min(len(x)/sr,c['end_s']+.6);fig,ax=plt.subplots(2,1,figsize=(11,6));m=(tt>=a)&(tt<b);ax[0].plot(tt[m],db[m]);ax[0].axvspan(c['start_s'],c['end_s'],color='#e8b75a',alpha=.3);ax[0].set(ylim=(-100,0),ylabel='10ms RMS dBFS');f,t,z=signal.stft(x[round(a*sr):round(b*sr)],sr,nperseg=1024,noverlap=768);ax[1].pcolormesh(t+a,f,20*np.log10(np.maximum(abs(z),1e-7)),vmin=-100,vmax=-20,shading='auto',cmap='magma');ax[1].set(ylim=(0,8000),xlabel='Source microphone seconds',ylabel='Hz');fig.suptitle(f"Event {c['id']}: {c['start_s']:.2f}-{c['end_s']:.2f}s | {c['reference_decision']} | UNREVIEWED, not a cough label");fig.tight_layout();pdf.savefig(fig);plt.close(fig)
save('source_integrity_hashes.json',{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [SRC,BASE,PROJ,FINAL]})
print('FINISHED',str(OUT),flush=True)

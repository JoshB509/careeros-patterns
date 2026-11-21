import sys,json,pathlib,numpy as np,subprocess,csv,wave
sys.dont_write_bytecode=True
from scipy import signal
from scipy.ndimage import binary_closing
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
P=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis');x=np.load(P/'source_mono.npy');y=np.load(P/'final_mono.npy');sr=48000
clips=json.loads((P/'clips.json').read_text());cuts=json.loads((P/'every_cut.json').read_text());words=json.loads((P/'premiere_source_words.json').read_text())
step=480;n=len(x)//step;t=(np.arange(n)+.5)*.01;rms=np.sqrt(np.mean(x[:n*step].reshape(-1,step)**2,axis=1));db=20*np.log10(np.maximum(rms,1e-10))
# Nonverbal candidates: above -50dBFS for >=80ms, bridge no more than 30ms, >=70% outside timestamped lexical words (with 50ms guards).
active=binary_closing(db>=-50,structure=np.ones(4));v=np.diff(np.r_[False,active,False].astype(int));starts=np.where(v==1)[0];ends=np.where(v==-1)[0]
spoken=np.zeros(n,dtype=bool)
for w in words:
 if w['word'].strip():spoken[max(0,int((w['start']-.05)/.01)):min(n,int(np.ceil((w['end']+.05)/.01)))]=True
kept=np.zeros(n,dtype=bool)
for c in clips:kept[(t>=c['inp'])&(t<c['out'])]=True
cands=[]
for a,b in zip(starts,ends):
 if b-a<8:continue
 uncovered=float(np.mean(~spoken[a:b]))
 if uncovered<.7:continue
 xx=x[a*step:b*step];freq,power=signal.welch(xx,sr,nperseg=min(1024,len(xx)))
 k=float(np.mean(kept[a:b]));state='removed' if k<.05 else 'kept' if k>.95 else 'partly_removed'
 cands.append(dict(id=len(cands)+1,start_s=a*.01,end_s=b*.01,duration_s=(b-a)*.01,peak_10ms_dbfs=float(db[a:b].max()),rms_dbfs=float(20*np.log10(np.sqrt(np.mean(xx*xx)))),untranscribed_fraction=uncovered,retained_fraction=k,reference_decision=state,spectral_centroid_hz=float(np.sum(freq*power)/np.sum(power)),class_label='unreviewed_nonverbal_candidate',reason='Lexical ASR gap plus detectable acoustic event; not a confirmed cough or throat clear.'))
(P/'nonverbal_candidates.json').write_text(json.dumps(cands,indent=2))
if cands:
 with (P/'nonverbal_candidates.csv').open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=cands[0].keys());w.writeheader();w.writerows(cands)
# Review short, non-destructive candidate excerpts locally. No original modifications.
(P/'review_audio').mkdir(exist_ok=True)
for c in cands:
 a=max(0,c['start_s']-.6);b=min(len(x)/sr,c['end_s']+.8);name=f"event_{c['id']:02d}_{c['reference_decision']}_{c['start_s']:.2f}s.wav"
 with wave.open(str(P/'review_audio'/name),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(x[round(a*sr):round(b*sr)],-1,.999969)*32768).astype('<i2').tobytes())
 c['review_file']='review_audio/'+name;c['review_context_start_s']=a
(P/'nonverbal_candidates.json').write_text(json.dumps(cands,indent=2))
# Raw PCM envelope (1ms min/max) for every boundary.
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
with PdfPages(P/'raw_waveform_boundaries.pdf') as pdf:
 for r in cuts:
  fig,axes=plt.subplots(2,2,figsize=(12,7),sharex='col')
  for col,key,label in [(0,'source_out_s','Outgoing tail'),(1,'source_in_s','Incoming lead')]:
   boundary=r[key];lo=boundary-.65;hi=boundary+.65;i0=max(0,round(lo*sr));i1=min(len(x),round(hi*sr));z=x[i0:i1];num=len(z)//48;zz=z[:num*48].reshape(-1,48);tt=i0/sr+(np.arange(num)+.5)*.001
   axes[0,col].fill_between(tt,zz.min(1),zz.max(1),color='#39596c');axes[0,col].set_title(label+' | raw PCM min/max per 1ms');axes[0,col].set_ylabel('Linear amplitude (full scale=1)')
   mask=(t>=lo)&(t<=hi);axes[1,col].plot(t[mask],db[mask],lw=.8);axes[1,col].set(ylim=(-100,-5),ylabel='10ms RMS dBFS',xlabel='Source mic seconds')
   for ax in axes[:,col]:ax.axvline(boundary,c='#be3c2b');ax.axvspan(r['source_out_s'],r['source_in_s'],color='#dc6a54',alpha=.15);ax.set_xlim(lo,hi)
  fig.suptitle(f"Cut {r['cut']:02d}: final {r['final_s']:.3f}s | deleted {r['source_out_s']:.3f} to {r['source_in_s']:.3f}s",fontweight='bold');fig.tight_layout(rect=(0,0,1,.94));pdf.savefig(fig);fig.savefig(P/f"raw_{r['cut']:02d}.png",dpi=120);plt.close(fig)
with PdfPages(P/'nonverbal_candidate_spectrograms.pdf') as pdf:
 for c in cands:
  a=max(0,c['start_s']-.4);b=min(len(x)/sr,c['end_s']+.6);fig,ax=plt.subplots(2,1,figsize=(11,6))
  m=(t>=a)&(t<b);ax[0].plot(t[m],db[m]);ax[0].axvspan(c['start_s'],c['end_s'],color='#e8b75a',alpha=.3);ax[0].set(ylim=(-100,0),ylabel='10ms RMS dBFS')
  f,tt,z=signal.stft(x[round(a*sr):round(b*sr)],sr,nperseg=1024,noverlap=768);ax[1].pcolormesh(tt+a,f,20*np.log10(np.maximum(abs(z),1e-7)),vmin=-100,vmax=-20,shading='auto',cmap='magma');ax[1].set(ylim=(0,8000),xlabel='Source microphone seconds',ylabel='Hz')
  fig.suptitle(f"Event {c['id']}: {c['start_s']:.2f}-{c['end_s']:.2f}s | {c['reference_decision']} | UNREVIEWED, not a cough diagnosis");fig.tight_layout();pdf.savefig(fig);fig.savefig(P/f"event_{c['id']:02d}.png",dpi=110);plt.close(fig)
# In-file level-defined silent runs retained by final editor.
retained_pauses=[]
mask=db<-50;vv=np.diff(np.r_[False,mask,False].astype(int))
for a,b in zip(np.where(vv==1)[0],np.where(vv==-1)[0]):
 if b-a<30:continue
 if np.all(kept[a:b]):
  retained_pauses.append(dict(source_start_s=a*.01,source_end_s=b*.01,duration_s=(b-a)*.01,threshold_dbfs=-50))
(P/'retained_pauses.json').write_text(json.dumps(retained_pauses,indent=2))
print('CANDIDATES',json.dumps(cands,indent=2));print('RETAINED_PAUSES',len(retained_pauses),sorted(retained_pauses,key=lambda a:-a['duration_s'])[:12])

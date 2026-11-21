import pathlib,json,numpy as np,wave,subprocess,sys
sys.dont_write_bytecode=True
from scipy import signal
from scipy.ndimage import uniform_filter1d
P=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\storytelling-cut-analysis');x=np.load(P/'source_mono.npy');y=np.load(P/'final_mono.npy');sr=48000
words=json.loads((P/'premiere_source_words.json').read_text());cuts=json.loads((P/'final_every_cut.json').read_text());cs=json.loads((P/'final_clips.json').read_text());narr=[c for c in cs if not c['room_tone']]
n=len(x)//480;tt=(np.arange(n)+.5)*.01;db=20*np.log10(np.maximum(np.sqrt(np.mean(x[:n*480].reshape(-1,480)**2,axis=1)),1e-10));v=np.diff(np.r_[False,db<-50,False].astype(int));runs=[(a*.01,b*.01) for a,b in zip(np.where(v==1)[0],np.where(v==-1)[0])]
def save(name,obj):(P/name).write_text(json.dumps(obj,indent=2),encoding='utf8')
def excerpt(name,arr,a,b):
 with wave.open(str(P/'review_audio'/name),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(arr[round(max(a,0)*sr):round(min(b,len(arr)/sr)*sr)],-1,.999969)*32768).astype('<i2').tobytes())
short=[];flags=[]
for c in cuts:
 a,b=c['source_out_s'],c['source_in_s']
 covers=[(s,e) for s,e in runs if s<=a+.005 and e>=b-.005]
 for s,e in covers:
  short.append(dict(cut=c['cut'],final_s=c['final_s'],source_gap_start=s,source_gap_end=e,original_quiet_s=e-s,removed_s=b-a,remaining_source_quiet_s=(a-s)+(e-b),added_timeline_gap_s=c['timeline_gap_s'],left_words=c['left_words'],right_words=c['right_words']))
 for side,key in [('tail','source_out_s'),('lead','source_in_s')]:
  t=c[key];cross=[w for w in words if w['word'].strip() and w['start']+.01<t<w['end']-.01]
  if cross or c[f'{side}_ms_m45']<40:
   flags.append(dict(cut=c['cut'],side=side,source_boundary_s=t,final_s=c['final_s'],rms45_padding_ms=c[f'{side}_ms_m45'],crossing_asr_words=cross,status='unreviewed_boundary_candidate_not_confirmed_clipping'))
for i in [6,21,31,32]:
 c=next(c for c in cuts if c['cut']==i);excerpt(f'boundary_{i:02}_final_context.wav',y,c['final_s']-2,c['final_s']+2);excerpt(f'boundary_{i:02}_source_lead.wav',x,c['source_in_s']-1,c['source_in_s']+2)
for i,p in enumerate(sorted(json.loads((P/'retained_pauses.json').read_text()),key=lambda z:-z['duration_s'])[:12],1):excerpt(f'pause_{i:02}_{p["source_start_s"]:.2f}s_source.wav',x,p['source_start_s']-2,p['source_end_s']+2)
save('shortened_quiet_gaps.json',short);save('boundary_review_flags.json',flags)
headtail=dict(head_trim_s=narr[0]['inp'],tail_trim_s=len(x)/sr-narr[-1]['out'],head_asr_overlap=[w for w in words if w['word'] and w['start']<narr[0]['inp']<w['end']],tail_asr_overlap=[w for w in words if w['word'] and w['start']<narr[-1]['out']<w['end']],warning='ASR overlap is a review flag, not proof that a syllable was cut.')
save('head_tail_trims.json',headtail)
# Independently compare camera and processed mic amplitude envelopes at widely spaced points.
f=r'E:\CareerOS\12_YouTube\show-data-like-this\Recorded\Input\2026-11-02 17-26-15.mp4';FF=r'E:\Videos\DaJoshiResolve\tools\ffmpeg.exe'
b=subprocess.run([FF,'-v','error','-nostdin','-i',f,'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=0x08000000).stdout;camera=np.frombuffer(b,dtype='<f4');mic=signal.resample_poly(x,1,3)
def env(z):
 n=len(z)//80;v=np.sqrt(np.mean(z[:n*80].reshape(-1,80)**2,axis=1));return uniform_filter1d(v,size=5)
a=env(mic);z=env(camera);checks=[]
for s in [20,200,400,600,800,1000,1180]:
 w=a[s*200:(s+10)*200];expected=s-5.999994000141724;lo=round((expected-.3)*200);zz=z[lo:round((expected+10+.3)*200)];w=w-w.mean();cc=signal.correlate(zz,w,mode='valid',method='fft');s2=np.r_[0,np.cumsum(zz*zz,dtype=np.float64)];s1=np.r_[0,np.cumsum(zz,dtype=np.float64)];e=s2[len(w):]-s2[:-len(w)]-(s1[len(w):]-s1[:-len(w)])**2/len(w);r=cc/np.sqrt(np.maximum(e,1e-20)*np.sum(w*w));j=int(np.argmax(r));checks.append(dict(mic_start_s=s,camera_start_s=(lo+j)/200,mic_minus_camera_s=s-(lo+j)/200,envelope_correlation=float(r[j])))
save('camera_mic_sync.json',dict(project_offset_s=5.999994000141724,method='Seven 10-second windows; 5ms RMS envelopes smoothed25ms; +/-300ms search. Not perceptual/lip-sync validation.',checks=checks))
print('SHORTENED',json.dumps(short,indent=2));print('HEADTAIL',headtail);print('CAMERA',checks);print('FLAGS',len(flags))

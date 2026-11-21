import json,pathlib,numpy as np,subprocess
from scipy import signal
from scipy.ndimage import uniform_filter1d
p=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis');x=np.load(p/'source_mono.npy');sr=16000
f=r'E:\CareerOS\12_YouTube\answering-exec-questions\Recorded\Input\2026-11-05_answering-exec-questions_recording_v02.mp4'
b=subprocess.run([r'E:\Videos\DaJoshiResolve\tools\ffmpeg.exe','-v','error','-nostdin','-i',f,'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1'],capture_output=True,check=True,creationflags=0x08000000).stdout
camera=np.frombuffer(b,dtype='<f4');mic=signal.resample_poly(x,1,3);checks=[]
def env(x):
 n=len(x)//80;v=np.sqrt(np.mean(x[:n*80].reshape(-1,80)**2,axis=1));return uniform_filter1d(v,size=5)
a=env(mic);y=env(camera)
for s in [20,100,200,300,400,500]:
 w=a[s*200:(s+10)*200];expected=s-3.6999963;lo=round((expected-.3)*200);z=y[lo:round((expected+10+.3)*200)];w=w-w.mean();cc=signal.correlate(z,w,mode='valid',method='fft');s2=np.r_[0,np.cumsum(z*z,dtype=np.float64)];s1=np.r_[0,np.cumsum(z,dtype=np.float64)];e=s2[len(w):]-s2[:-len(w)]-(s1[len(w):]-s1[:-len(w)])**2/len(w);r=cc/np.sqrt(np.maximum(e,1e-20)*np.sum(w*w));j=int(np.argmax(r));checks.append(dict(mic_start_s=s,camera_start_s=(lo+j)/200,mic_minus_camera_s=s-(lo+j)/200,envelope_correlation=float(r[j])))
result=dict(project_offset_s=3.699996300087396,method='10-second 5ms RMS amplitude envelopes smoothed 25ms, six speech windows, +/-300ms search about project offset; not lip-sync validation.',checks=checks,offset_resolution_ms=5,comment='Different processing creates acoustic timing ambiguity. Do not infer drift or retime from this small envelope difference without additional anchors.')
(p/'camera_mic_sync.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

import sys,json,hashlib,subprocess,io,base64,struct,collections
from pathlib import Path
from PIL import Image,ImageDraw
sys.dont_write_bytecode=True
sys.path.insert(0,r'E:\CareerOS\12_YouTube\show-data-like-this\video\Animation-Edit-v01-20261102\reproducibility')
from inspect_project import Project,T,E
OUT=Path(r'C:\Users\you\Documents\Codex\2026-11-10\storytelling-cut-analysis\key-evidence')
FF=r'E:\Videos\DaJoshiResolve\tools\ffmpeg.exe'
ROOT=Path(r'E:\CareerOS\12_YouTube')
paths={'data_base':ROOT/'show-data-like-this/video/Data storytelling.prproj','exec_base':ROOT/'answering-exec-questions/video/Exec questions.prproj','data_final':ROOT/'show-data-like-this/video/Animation-Edit-v01-20261102/Data-Storytelling-Animation-Edit-v01.prproj','exec_final':ROOT/'answering-exec-questions/video/Animation-Edit-v01-20261105/Answering-Exec-Questions-Animation-Edit-v03.prproj'}
results={}
for key,path in paths.items():
 p=Project(path);sequences=[]
 for s in p.dump():
  if 'AutoCut-Backup' in s['name']:continue
  tracks=[]
  for tr in s['tracks']:
   if tr['type']!='VideoTrackGroup' or not tr['items']:continue
   signatures=collections.Counter()
   for c in tr['items']:
    chain=p.ref(p.ids[c['item_id']].find('ClipTrackItem/ComponentOwner/Components'));fx=[]
    for rr in chain.findall('ComponentChain/Components/Component'):
     comp=p.ref(rr);params={p.ref(pr).findtext('Name'):p.ref(pr).findtext('StartKeyframe','') for pr in comp.findall('Component/Params/Param')};fx.append({'effect':comp.findtext('Component/DisplayName'),'match_name':comp.findtext('MatchName'),'serialized_parameters':params})
    signatures[json.dumps(fx)]+=1
   tracks.append({'index':tr['index'],'muted':tr['muted'],'clip_count':len(tr['items']),'variants':[{'clip_count':n,'effects':json.loads(k)} for k,n in signatures.items()]})
  sequences.append({'name':s['name'],'uid':s['uid'],'tracks':tracks})
 results[key]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sequences':sequences}
(OUT/'native_effects_readback.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
data_export=ROOT/'show-data-like-this/video/Data Storytelling - Animation Edit v01.mp4';exec_export=ROOT/'answering-exec-questions/video/export.mp4';data_source=ROOT/'show-data-like-this/Recorded/Input/2026-11-02 17-26-15.mp4';exec_source=ROOT/'answering-exec-questions/Recorded/Input/2026-11-05_answering-exec-questions_recording_v02.mp4'
def frame(path,t,vf):
 r=subprocess.run([FF,'-hide_banner','-loglevel','error','-nostdin','-ss',str(t),'-i',str(path),'-frames:v','1','-vf',vf,'-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,check=True,creationflags=0x08000000)
 return Image.open(io.BytesIO(r.stdout)).convert('RGB')
records=[]
for name,path,t,vf in [('data-source-hair',data_source,15.399993,'scale=1920:1080,crop=348:348:851:149,scale=400:400'),('data-export-hair',data_export,8,'crop=400:400:760:120'),('exec-source-hair',exec_source,12.733322,'scale=1920:1080,crop=345:345:788:151,scale=400:400'),('exec-export-hair',exec_export,1,'scale=1920:1080,crop=400:400:760:120'),('data-source-full',data_source,15.399993,'scale=1280:720'),('data-export-full',data_export,8,'scale=1280:720'),('exec-source-full',exec_source,12.733322,'scale=1280:720'),('exec-export-full',exec_export,1,'scale=1280:720')]:
 im=frame(path,t,vf);im.save(OUT/(name+'.png'));records.append({'file':name+'.png','source':str(path),'seconds':t,'filter':vf,'scope':'Actual source or existing export. No key recreation, no native project edit.'})
can=Image.new('RGB',(800,850),'white');d=ImageDraw.Draw(can)
for j,label in enumerate(['data-source-hair','data-export-hair','exec-source-hair','exec-export-hair']):
 can.paste(Image.open(OUT/(label+'.png')),(j%2*400,j//2*425+25));d.text((j%2*400+3,j//2*425+3),label,fill='black')
can.save(OUT/'hair-source-versus-export.png')
for t in [8.1,8.2,910]:
 im=frame(data_export,t,'scale=1280:720');name=f'data-export-{t:.1f}s.png';im.save(OUT/name);records.append({'file':name,'source':str(data_export),'seconds':t,'filter':'scale=1280:720','scope':'Actual existing export sample; no temporal playback judgment.'})
(OUT/'frame-provenance.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps({'output':str(OUT),'project_snapshots':len(results),'image_samples':len(records)},indent=2))

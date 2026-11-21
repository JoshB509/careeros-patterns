from pathlib import Path
import gzip,xml.etree.ElementTree as E,json,base64,struct,hashlib
T=254016000000
ROOT=Path(r'E:\CareerOS\12_YouTube\the-secret-to-selling-your-ideas-to-executives')
PROJECT=ROOT/'Recorded/Input/Selling Ideas Project.prproj'
class Project:
 def __init__(self,path):
  b=Path(path).read_bytes();self.root=E.fromstring(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
  self.ids={x.get('ObjectID'):x for x in self.root if x.get('ObjectID')};self.uids={x.get('ObjectUID'):x for x in self.root if x.get('ObjectUID')}
 def ref(self,x):
  if x is None:return None
  return self.ids.get(x.get('ObjectRef')) if x.get('ObjectRef') else self.uids.get(x.get('ObjectURef'))
 def tracks(self,seq):
  for ref in seq.findall('TrackGroups/TrackGroup/Second'):
   g=self.ref(ref)
   if g.tag not in ['VideoTrackGroup','AudioTrackGroup']:continue
   for tr in g.findall('TrackGroup/Tracks/Track'):
    track=self.ref(tr);items=[]
    for cr in track.findall('ClipTrack/ClipItems/TrackItems/TrackItem'):
     item=self.ref(cr);it=item.find('ClipTrackItem')
     if it is None:continue
     s=self.ref(it.find('SubClip'));c=self.ref(s.find('Clip'));source=self.ref(c.find('Clip/Source'))
     ss=source.find('SequenceSource/Sequence');ms=source.find('MediaSource/Media');media=self.ref(ms)
     start=int(it.findtext('TrackItem/Start'));end=int(it.findtext('TrackItem/End'));inp=int(c.findtext('Clip/InPoint','0'));op=int(c.findtext('Clip/OutPoint',str(inp+end-start)))
     items.append(dict(item_id=item.get('ObjectID'),clip_id=c.get('ObjectID'),subclip_id=s.get('ObjectID'),name=s.findtext('Name'),start=start,end=end,inp=inp,out=op,media=media.findtext('FilePath') if media is not None else None,nested_sequence=ss.get('ObjectURef') if ss is not None else None))
    yield dict(type=g.tag,index=int(tr.get('Index')),uid=track.get('ObjectUID'),muted=track.findtext('ClipTrack/Track/IsMuted'),items=sorted(items,key=lambda x:x['start']))
 def dump(self):return [dict(uid=s.get('ObjectUID'),name=s.findtext('Name'),tracks=list(self.tracks(s))) for s in self.root if s.tag=='Sequence']
if __name__=='__main__':
 p=Project(PROJECT);audit=p.dump();Path('base-audit.json').write_text(json.dumps(audit,indent=2))
 for s in audit:
  print(s['uid'],s['name'])
  for t in s['tracks']:print(t['type'],t['index'],len(t['items']),max([i['end']/T for i in t['items']] or [0]),t['items'][0] if t['items'] else '')
 d=base64.b64decode(p.root.find('.//TranscriptData').text)
 def fields(pos):
  v=pos-struct.unpack_from('<i',d,pos)[0]
  return {i:pos+o for i,o in enumerate(struct.unpack_from('<'+'H'*((struct.unpack_from('<H',d,v)[0]-4)//2),d,v+4)) if o}
 def target(p):return p+struct.unpack_from('<I',d,p)[0]
 def vector(p):
  p=target(p);return [target(p+4+i*4) for i in range(struct.unpack_from('<I',d,p)[0])]
 def string(p):
  p=target(p);n=struct.unpack_from('<I',d,p)[0];return d[p+4:p+4+n].decode()
 def tick(p):return struct.unpack_from('<q',d,p)[0]/T
 doc=fields(target(fields(struct.unpack_from('<I',d,0)[0])[0]));raw=[]
 for seg in vector(doc[0]):
  sf=fields(seg)
  for word in vector(sf[3]):
   wf=fields(word);start=tick(wf[0]);duration=tick(wf[1]);raw.append(dict(word=string(wf[2]),start=start,end=start+duration))
 Path('source-words.json').write_text(json.dumps(raw,indent=2))
 clips=next(t['items'] for t in audit[0]['tracks'] if t['type']=='AudioTrackGroup' and t['index']==0)
 words=[]
 for i,c in enumerate(clips):
  for w in raw:
   if c['inp']/T<=(w['start']+w['end'])/2<c['out']/T:
    words.append(dict(word=w['word'],start=max(w['start'],c['inp']/T)-c['inp']/T+c['start']/T,end=min(w['end'],c['out']/T)-c['inp']/T+c['start']/T,clip=i,source_start=w['start']))
 Path('sequence-words.json').write_text(json.dumps(words,indent=2))
 Path('sequence-transcript.txt').write_text('\n'.join(f"{i}: {w['start']:.3f} {w['word']}" for i,w in enumerate(words)),encoding='utf-8')
 print('source words',len(raw),'sequence words',len(words),'source end',raw[-1])


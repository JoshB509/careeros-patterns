import pathlib,json,numpy as np,hashlib
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
p=pathlib.Path(r'C:\Users\you\Documents\Codex\2026-11-10\exec-cut-analysis');x=np.load(p/'source_mono.npy');sr=48000;c=json.loads((p/'clips.json').read_text());n=len(x)//480;t=(np.arange(n)+.5)*.01;db=20*np.log10(np.maximum(np.sqrt(np.mean(x[:n*480].reshape(-1,480)**2,axis=1)),1e-10));rows=[]
for name,point,side,removed in [('head_trim',c[0]['inp'],'lead',c[0]['inp']),('tail_trim',c[-1]['out'],'tail',len(x)/sr-c[-1]['out'])]:
 row=dict(boundary=name,source_s=point,removed_s=removed)
 for th in [-60,-55,-50,-45,-40]:
  ii=np.where(((t>=point)&(t<point+2) if side=='lead' else (t>=point-2)&(t<point))&(db>=th))[0]
  row[f'{side}_ms_m{abs(th)}']=max(0,((t[ii[0]]-.005-point) if side=='lead' else (point-t[ii[-1]]-.005)))*1000 if len(ii) else None
 rows.append(row)
with PdfPages(p/'head_tail_waveforms.pdf') as pdf:
 for r in rows:
  z=r['source_s'];lo=z-1;hi=z+1;m=(t>=lo)&(t<hi);fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True);i0=int(lo*sr);i1=int(hi*sr);d=x[i0:i1];n=len(d)//48;d=d[:n*48].reshape(-1,48);tt=lo+(np.arange(n)+.5)*.001;axs[0].fill_between(tt,d.min(1),d.max(1),color='#39596c');axs[0].set_ylabel('Raw PCM amplitude');axs[1].plot(t[m],db[m]);axs[1].set(ylim=(-100,0),ylabel='10ms RMS dBFS',xlabel='Source mic seconds')
  for ax in axs:ax.axvline(z,color='#be3c2b');ax.axvspan(lo,z,color='#dc6a54',alpha=.15) if r['boundary']=='head_trim' else ax.axvspan(z,hi,color='#dc6a54',alpha=.15)
  fig.suptitle(f"{r['boundary']} at source {z:.6f}s; removes {r['removed_s']:.6f}s");fig.tight_layout();pdf.savefig(fig);fig.savefig(p/(r['boundary']+'.png'),dpi=120);plt.close(fig)
(p/'head_tail_trims.json').write_text(json.dumps(rows,indent=2))
m=json.loads((p/'measurements.json').read_text());check={f:hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()==h for f,h in m['sha256'].items()};(p/'originals_unchanged_check.json').write_text(json.dumps(check,indent=2));print(json.dumps(rows,indent=2));print('UNCHANGED',check)

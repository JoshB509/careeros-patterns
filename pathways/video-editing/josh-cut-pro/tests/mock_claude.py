"""Mock Claude API for testing the helper's plumbing (streams canned replies)."""
import json, re, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
LOG=open('mock_requests.log','a')
def svg(t): return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"><rect width="1920" height="1080" fill="#fff"/><rect x="180" y="300" width="900" height="140" rx="22" fill="#FDF1C7" stroke="#EED27A" stroke-width="3"/><text x="230" y="390" font-family="Arial" font-size="52" fill="#15171C">%s</text><rect x="1322" y="202" width="518" height="674" fill="#D6D2C9" stroke="#F5C21B" stroke-width="6"/><text x="1500" y="550" font-family="Arial" font-size="30" fill="#888">CAMERA</text></svg>'%t
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_POST(self):
        b=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        sysp=b['system'][0]['text']; user=b['messages'][0]['content']
        LOG.write(json.dumps(dict(model=b['model'],sys=sysp[:60],user_len=len(user),max=b['max_tokens']))+'\n'); LOG.flush()
        idx=[int(x) for x in re.findall(r'#(\d+) ',user)]
        if sysp.startswith('You edit talking-head'):
            rem=[]
            # mock: remove any immediate repeated word and the words of lines containing "<" sound marker start
            toks=re.findall(r'#(\d+) (\S+)',user)
            for (i,w),(j,w2) in zip(toks,toks[1:]):
                if re.sub(r'\W','',w.lower())==re.sub(r'\W','',w2.lower()) and re.sub(r'\W','',w): rem.append({"from":int(i),"to":int(i),"why":"repeat"})
            rem.append({"from":idx[40],"to":idx[52],"why":"abandoned take"})
            out=json.dumps({"remove":rem})
        elif 'revising ONE animation' in sysp:
            out=json.dumps({"number":2,"type":"full","name":"Redone idea","description":"A redone full screen idea.","presses":[{"word":idx[300],"quote":"x","shows":"card"}],"end_word":idx[310],"sketch_svg":svg('Redone')})
        elif sysp.startswith('You plan the animations'):
            a=[]
            allowed=re.search(r'Allowed "type" values: ([a-z, ]+)\.',sysp)
            allowed=[t.strip() for t in allowed.group(1).split(',')] if allowed else ['pip','full']
            for n,(s,e) in enumerate([(120,150),(300,330),(600,640)],1):
                toks=re.findall(r'#(\d+) (\S+)',user); ws=[w for i,w in toks]
                a.append({"number":n,"type":allowed[(n-1)%len(allowed)],"name":"Animation %d idea"%n,"description":"Cards build up for idea %d."%n,
                  "presses":[{"word":idx[s],"quote":' '.join(ws[s:s+3]),"shows":"first card"},{"word":idx[s+8],"quote":' '.join(ws[s+8:s+11]),"shows":"second card"}],
                  "end_word":idx[e],"sketch_svg":svg('Idea %d'%n)})
            out=json.dumps({"animations":a})
        else:
            m=re.search(r'"type": "([^"]+)"',user); pipm='picture' in (m.group(1) if m else '')
            n=len(re.findall(r'"press": \d+',user))
            rows=''.join('<div class="abs card %s" style="left:110px;top:%dpx;width:1000px" data-b="%d">Card for press %d</div>'%('strong' if k==1 else 'gold',300+170*(k-1),k,k) for k in range(1,n+1))
            out='<section class="scene %s"><div class="abs eyebrow" style="left:110px;top:230px" data-b="1">The idea</div>%s</section>'%('pip' if pipm else 'fs',rows)
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
        ev=lambda d: self.wfile.write(('event: x\ndata: %s\n\n'%json.dumps(d)).encode())
        ev({"type":"message_start","message":{"usage":{"input_tokens":len(user)//4,"cache_creation_input_tokens":len(sysp)//4,"cache_read_input_tokens":0,"output_tokens":1}}})
        for i in range(0,len(out),500): ev({"type":"content_block_delta","delta":{"type":"text_delta","text":out[i:i+500]}})
        ev({"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":len(out)//4}}); ev({"type":"message_stop"})
HTTPServer(('127.0.0.1',47999),H).serve_forever()

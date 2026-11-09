import re,zlib,sys,os,json,glob

def stream_of(body):
    if body is None: return b''
    m=re.search(rb'stream\r?\n(.*?)\s*endstream',body,re.S)
    if not m: return b''
    raw=m.group(1)
    if b'FlateDecode' in body[:m.start()]:
        try: return zlib.decompressobj().decompress(raw)
        except Exception: return b''
    return raw

def objs(d):
    out={}
    for m in re.finditer(rb'(?<![0-9])(\d+)\s+0\s+obj\b',d):
        num=int(m.group(1))
        end=d.find(b'endobj',m.end())
        out[num]=d[m.end():end if end>0 else len(d)]
    return out

def parse_cmap(txt):
    m={}
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange',txt,re.S):
        for mm in re.finditer(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<([0-9A-Fa-f]+)>|\[[^\]]*\])',blk):
            lo,hi=int(mm.group(1),16),int(mm.group(2),16)
            if mm.group(3).startswith(b'<'):
                base=int(mm.group(4),16)
                for i in range(lo,hi+1):
                    try: m[i]=chr(base+(i-lo))
                    except: pass
    out={}
    for f in files:
        ym=re.search(r'明细(\d{6})',f).group(1)
        r=parse(f); out[ym]=r
        print(ym, json.dumps(r,ensure_ascii=False))
    json.dump(out,open('.workbuddy/tmp/bills.json','w'),ensure_ascii=False,indent=1)

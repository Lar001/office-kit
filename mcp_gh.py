#!/usr/bin/env python3
"""直连 GitHub 官方 MCP 服务器（api.githubcopilot.com/mcp/），复用连接器令牌。
用法:
  python3 mcp_gh.py tools                    # 列工具
  python3 mcp_gh.py call <tool> '<json参数>' # 调用工具
"""
import json,os,sys,subprocess

URL="https://api.githubcopilot.com/mcp/"
TOK=open(os.path.expanduser("~/.workbuddy/.ghtoken")).read().strip()

class Session:
    def __init__(self):
        self.sid=None; self.n=0
        r=self._raw({"jsonrpc":"2.0","id":0,"method":"initialize","params":{
            "protocolVersion":"2025-03-26","capabilities":{},
            "clientInfo":{"name":"workbuddy","version":"1.0"}}})
        self._raw({"jsonrpc":"2.0","method":"notifications/initialized"})
    def _raw(self,body):
        cmd=["/usr/bin/curl","-sS","-m","120","-D","-","-X","POST",URL,
             "-H","Content-Type: application/json","-H","Accept: application/json, text/event-stream",
             "-H","Authorization: Bearer "+TOK,"-H","User-Agent: workbuddy-gh",
             "--data-binary",json.dumps(body)]
        if self.sid: cmd+=["-H","Mcp-Session-Id: "+self.sid]
        p=subprocess.run(cmd,capture_output=True)
        out=p.stdout.decode('utf-8','ignore')
        hdr,_,data=out.partition("\r\n\r\n")
        for line in hdr.split("\r\n"):
            if line.lower().startswith("mcp-session-id:"): self.sid=line.split(":",1)[1].strip()
        for line in data.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return {}
    def call(self,tool,args):
        self.n+=1
        return self._raw({"jsonrpc":"2.0","id":self.n,"method":"tools/call",
                          "params":{"name":tool,"arguments":args}})

def _text(r):
    c=r.get("result",{}).get("content",[])
    return "\n".join(x.get("text","") for x in c if x.get("type")=="text")

if __name__=="__main__":
    if len(sys.argv)<2: print(__doc__); sys.exit(1)
    s=Session()
    if sys.argv[1]=="tools":
        d=s._raw({"jsonrpc":"2.0","id":99,"method":"tools/list","params":{}})
        for t in d.get("result",{}).get("tools",[]):
            print(t["name"],"—",(t.get("description") or "")[:100])
    elif sys.argv[1]=="call":
        r=s.call(sys.argv[2],json.loads(sys.argv[3]) if len(sys.argv)>3 else {})
        if r.get("error"): print("ERROR",json.dumps(r["error"],ensure_ascii=False))
        else:
            print(_text(r)[:3000])
            if r.get("result",{}).get("isError"): print("[isError]")

#!/usr/bin/env python3
"""GitHub Gist 云备份（连接器令牌即可写，无需 PAT）。
用法:
  python3 gist.py push <gist_id> <文件...>     # 更新已有 gist（生成新版本）
  python3 gist.py new  <说明> <文件...>        # 新建秘密 gist
  python3 gist.py pull <gist_id> [输出目录]    # 拉回全部文件
  python3 gist.py ls <gist_id>                 # 看文件与版本数
  python3 gist.py list                         # 我的全部 gist
"""
import json,os,sys,subprocess
TOK=open(os.path.expanduser("~/.workbuddy/.ghtoken")).read().strip()
API="https://api.github.com/gists/"
def req(method,path,data=None):
    cmd=["/usr/bin/curl","-sS","-m","90","-X",method,API+path,
         "-H","Authorization: Bearer "+TOK,"-H","Accept: application/vnd.github+json"]
    if data is not None:
        cmd+=["-H","Content-Type: application/json","--data-binary",json.dumps(data,ensure_ascii=False)]
    p=subprocess.run(cmd,capture_output=True)
    return json.loads(p.stdout or b"{}")
if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else ""
    if c=="new":
        d=req("POST","",{"description":sys.argv[2],"public":False,
            "files":{os.path.basename(f):{"content":open(f,encoding='utf-8').read()} for f in sys.argv[3:]}})
        print(d.get("id"),d.get("html_url") or d.get("message"))
    elif c=="push":
        gid=sys.argv[2]
        d=req("PATCH",gid,{"files":{os.path.basename(f):{"content":open(f,encoding='utf-8').read()} for f in sys.argv[3:]}})
        print("版本",len(d.get("history",[])),"文件",len(d.get("files",{})),d.get("message",""))
    elif c=="pull":
        gid=sys.argv[2]; out=sys.argv[3] if len(sys.argv)>3 else "."
        d=req("GET",gid); os.makedirs(out,exist_ok=True)
        for name,info in d.get("files",{}).items():
            if "content" in info:
                open(os.path.join(out,name),"w",encoding='utf-8').write(info["content"])
                print("拉回",name,len(info["content"]),"字节")
    elif c=="ls":
        d=req("GET",sys.argv[2])
        print("说明:",d.get("description"))
        print("版本数:",len(d.get("history",[])))
        for n,i in d.get("files",{}).items(): print(" -",n,i.get("size"),"字节")
    elif c=="list":
        d=req("GET","?per_page=100")
        for g in d: print(g["id"],g.get("description","")[:60])
    else: print(__doc__)

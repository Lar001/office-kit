#!/usr/bin/env python3
"""私有档案仓库云备份（Lar001/workbuddy-archive，需带 repo 权限的 PAT）。
用法:
  python3 archive.py put 本地文件 [仓库内路径]   # 上传/更新（生成新提交）
  python3 archive.py ls [目录]                  # 列仓库内容
  python3 archive.py get 仓库路径 [本地另存名]   # 下载单个文件
"""
import base64,json,os,sys,subprocess
TOK=open(os.path.expanduser("~/.workbuddy/.ghtoken")).read().strip()
REPO="Lar001/workbuddy-archive"
def req(method,url,data=None):
    cmd=["/usr/bin/curl","-sS","-m","60","-X",method,url,
         "-H","Authorization: Bearer "+TOK,"-H","Accept: application/vnd.github+json"]
    tmp=None
    if data is not None:
        # 大文件不能走 argv（Errno 7: Argument list too long），落盘再 @file
        import tempfile
        fd,tmp=tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd,'wb') as f:
            f.write(json.dumps(data,ensure_ascii=False).encode('utf-8'))
        cmd+=["-H","Content-Type: application/json","--data-binary","@"+tmp]
    try:
        p=subprocess.run(cmd,capture_output=True)
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)
    return json.loads(p.stdout or b"{}")
if __name__=="__main__":
    c=sys.argv[1] if len(sys.argv)>1 else ""
    if c=="put":
        lf=sys.argv[2]; path=sys.argv[3] if len(sys.argv)>3 else os.path.basename(lf)
        payload={"message":"update "+path,"content":base64.b64encode(open(lf,'rb').read()).decode(),"branch":"main"}
        old=req("GET",f"https://api.github.com/repos/{REPO}/contents/{path}")
        if old.get("sha"): payload["sha"]=old["sha"]
        d=req("PUT",f"https://api.github.com/repos/{REPO}/contents/{path}",payload)
        print(path,"->","ok "+d["commit"]["sha"][:8] if d.get("commit") else d.get("message"))
    elif c=="ls":
        path=sys.argv[2] if len(sys.argv)>2 else ""
        d=req("GET",f"https://api.github.com/repos/{REPO}/contents/{path}")
        if isinstance(d,list):
            for x in d: print(x["type"],x["path"],x.get("size",""))
        else: print(d.get("message"))
    elif c=="get":
        path=sys.argv[2]; out=sys.argv[3] if len(sys.argv)>3 else os.path.basename(path)
        d=req("GET",f"https://api.github.com/repos/{REPO}/contents/{path}")
        if d.get("content"):
            open(out,'wb').write(base64.b64decode(d["content"]))
            print("拉回",out,len(d["content"]),"B(base64)")
        else: print(d.get("message"))
    else: print(__doc__)

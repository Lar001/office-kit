#!/usr/bin/env python3
"""GitHub 直连工具（走 REST API，无需安装 git）
用法:
  python3 gh.py token <PAT>            # 保存令牌到 ~/.workbuddy/.ghtoken
  python3 gh.py whoami
  python3 gh.py ls [user]              # 列仓库
  python3 gh.py repo owner/name        # 仓库概况
  python3 gh.py tree owner/name [ref]  # 列目录树
  python3 gh.py cat owner/name path [ref]   # 读文件
  python3 gh.py put owner/name path localfile -m "msg" [--branch br]
  python3 gh.py branch owner/name newbr [--from main]
  python3 gh.py pr owner/name head base --title T [--body B]
  python3 gh.py tarball owner/name [ref] [outdir]
  python3 gh.py search 关键词 [repos|code|issues] [页数]
"""
import json,os,sys,base64,subprocess,tarfile,io,urllib.parse

CURL=os.environ.get("CURL_BIN") or ("/usr/bin/curl" if os.path.exists("/usr/bin/curl") else "curl")
TOK=os.path.expanduser("~/.workbuddy/.ghtoken")
API="https://api.github.com"

def token():
    if os.path.exists(TOK):
        t=open(TOK).read().strip()
        if t: return t
    return os.environ.get("GITHUB_TOKEN","")

def _curl(method,url,data=None,hdr=None):
    cmd=[CURL,"-sS","-m","60","-X",method,url,
         "-H","Accept: application/vnd.github+json","-H","User-Agent: workbuddy-gh"]
    t=token()
    if t: cmd+=["-H","Authorization: Bearer "+t]
    for h in (hdr or []): cmd+=["-H",h]
    body=None
    if data is not None:
        body=json.dumps(data).encode()
        cmd+=["-H","Content-Type: application/json","--data-binary","@-"]
    p=subprocess.run(cmd,input=body,capture_output=True)
    return p.returncode,p.stdout.decode('utf-8','ignore'),p.stderr.decode('utf-8','ignore')

def req(method,path,data=None,raw=False):
    url=path if path.startswith("http") else API+path
    rc,out,err=_curl(method,url,data)
    if rc!=0: return 0,{"error":err.strip() or "curl failed"}
    try: d=json.loads(out or "{}")
    except Exception: d=out
    if isinstance(d,dict) and "message" in d and "documentation_url" in d:
        return 0,d
    return 200,d

def die(*a):
    print(*a); sys.exit(1)

def main():
    if len(sys.argv)<2: die(__doc__)
    c=sys.argv[1]; a=sys.argv[2:]
    if c=="token":
        open(TOK,'w').write(a[0].strip()); os.chmod(TOK,0o600)
        print("令牌已保存"); return
    if c=="whoami":
        s,d=req("GET","/user"); print(d if isinstance(d,str) else (d.get("login"),d.get("name"),d.get("public_repos")))
    elif c=="ls":
        s,d=req("GET",f"/users/{a[0]}/repos?per_page=100&sort=updated" if a else "/user/repos?per_page=100&sort=updated")
        if isinstance(d,str): die(s,d)
        for x in d: print(f"{x['full_name']:50} {x['default_branch']:8} {'private' if x['private'] else 'public':7} {x.get('description') or ''}")
    elif c=="repo":
        s,d=req("GET",f"/repos/{a[0]}"); print(json.dumps(d,ensure_ascii=False,indent=1) if not isinstance(d,str) else d)
    elif c=="tree":
        ref=a[1] if len(a)>1 else (req("GET",f"/repos/{a[0]}")[1].get("default_branch") or "main")
        s,d=req("GET",f"/repos/{a[0]}/git/trees/{ref}?recursive=1")
        if isinstance(d,str): die(s,d)
        for x in d.get("tree",[]): print(x["type"],x["path"])
    elif c=="cat":
        s,d=req("GET",f"/repos/{a[0]}/contents/{a[1]}"+(f"?ref={a[2]}" if len(a)>2 else ""))
        if isinstance(d,str): die(s,d)
        if isinstance(d,list):
            for x in d: print(x["type"],x["path"]); return
        print(base64.b64decode(d["content"]).decode("utf-8","ignore"))
    elif c=="put":
        p=a[0]; path=a[1]; lf=a[2]
        msg="update "+path; br=None
        if "-m" in a: msg=a[a.index("-m")+1]
        if "--branch" in a: br=a[a.index("--branch")+1]
        content=base64.b64encode(open(lf,'rb').read()).decode()
        payload={"message":msg,"content":content}
        if br: payload["branch"]=br
        s,d=req("GET",f"/repos/{p}/contents/{path}"+(f"?ref={br}" if br else ""))
        if isinstance(d,dict) and "sha" in d: payload["sha"]=d["sha"]
        s,d=req("PUT",f"/repos/{p}/contents/{path}",payload)
        print(s, d if isinstance(d,str) else d.get("commit",{}).get("sha"))
    elif c=="branch":
        p=a[0]; nb=a[1]
        src=a[a.index("--from")+1] if "--from" in a else (req("GET",f"/repos/{p}")[1].get("default_branch") or "main")
        s,d=req("GET",f"/repos/{p}/git/ref/heads/{src}")
        if isinstance(d,str): die(s,d)
        s,d=req("POST",f"/repos/{p}/git/refs",{"ref":f"refs/heads/{nb}","sha":d["object"]["sha"]})
        print(s, d if isinstance(d,str) else "created "+nb)
    elif c=="pr":
        p=a[0]; head=a[1]; base=a[2]
        title=a[a.index("--title")+1] if "--title" in a else "PR"
        body=a[a.index("--body")+1] if "--body" in a else ""
        s,d=req("POST",f"/repos/{p}/pulls",{"title":title,"head":head,"base":base,"body":body})
        print(s, d if isinstance(d,str) else d.get("html_url"))
    elif c=="search":
        kw=a[0]
        kind=a[1] if len(a)>1 else "repos"
        limit=int(a[2]) if len(a)>2 else 10
        path={"repos":f"/search/repositories?q={urllib.parse.quote(kw)}&per_page={limit}",
              "code":f"/search/code?q={urllib.parse.quote(kw)}&per_page={limit}",
              "issues":f"/search/issues?q={urllib.parse.quote(kw)}&per_page={limit}"}[kind]
        s_,d=req("GET",path)
        if isinstance(d,str): die(s_,d)
        if kind=="repos":
            print("命中",d.get("total_count"))
            for x in d.get("items",[]):
                print(f"{x['full_name']:48} ★{x['stargazers_count']:<6} {x.get('description') or ''}"[:150])
        else:
            print("命中",d.get("total_count"))
            for x in d.get("items",[]):
                print(x.get("html_url") or x.get("repository",{}).get("full_name"))
    elif c=="tarball":
        p=a[0]; ref=a[1] if len(a)>1 else None
        if not ref:
            ref=req("GET",f"/repos/{p}")[1].get("default_branch") or "main"
        out=a[2] if len(a)>2 else "."
        url=f"https://codeload.github.com/{p}/tar.gz/{ref}"
        os.makedirs(out,exist_ok=True)
        tmp=os.path.join(out,"_repo.tar.gz")
        q=subprocess.run([CURL,"-sSL","-m","300","-o",tmp,url,"-H","User-Agent: workbuddy-gh"],capture_output=True)
        if q.returncode!=0: die("download failed",q.stderr.decode())
        with tarfile.open(tmp) as tf: tf.extractall(out)
        os.remove(tmp)
        print("downloaded ->",out)
    else: die(__doc__)

main()

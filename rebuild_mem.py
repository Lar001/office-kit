import json, os, glob, datetime, re

ROOT = "/storage/Users/currentUser/Desktop/05_AI助手记忆/会话历史/projects"
OUT = "/storage/Users/currentUser/WorkBuddy/Claw/.workbuddy/rebuild"
os.makedirs(OUT, exist_ok=True)

def parts_text(o):
    c = o.get("content")
    if isinstance(c, str):
        return c
    out = []
    if isinstance(c, list):
        for p in c:
            if not isinstance(p, dict):
                continue
            t = p.get("type")
            if t in ("input_text", "text", "output_text"):
                out.append(p.get("text", "") or p.get("content", ""))
    return "\n".join(out)

def ts(o):
    t = o.get("timestamp")
    if isinstance(t, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(t / 1000)
        except Exception:
            return None
    return None

users, asst, summaries = [], [], []
files = sorted(glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True))
stat = []
for f in files:
    n_u = n_a = 0
    try:
        fh = open(f, encoding="utf-8", errors="replace")
    except Exception:
        continue
    sess = os.path.basename(os.path.dirname(f))
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") != "message":
            continue
        role = o.get("role")
        txt = parts_text(o).strip()
        if not txt:
            continue
        d = ts(o)
        stamp = d.strftime("%Y-%m-%d %H:%M") if d else "?"
        if role == "user":
            if "<task-notification>" in txt or "<tool" in txt[:200]:
                continue
            if "<cb_summary>" in txt or "Summary of the conversation so far" in txt[:200]:
                body = re.sub(r"<[^>]+>", "", txt)
                summaries.append((stamp, sess, body.strip()[:4000]))
                continue
            body = re.sub(r"<system-reminder[\s\S]*?</system-reminder>", "", txt)
            body = re.sub(r"<[^>]+>", "", body).strip()
            if not body:
                continue
            users.append((stamp, sess, body[:2000]))
            n_u += 1
        elif role == "assistant":
            asst.append((stamp, sess, txt[:600]))
            n_a += 1
    fh.close()
    stat.append((f, n_u, n_a))

users.sort()
asst.sort()
summaries.sort()

with open(os.path.join(OUT, "01_用户原话.md"), "w", encoding="utf-8") as w:
    w.write("# 用户原话（跨全部会话，共 %d 条）\n\n" % len(users))
    for stamp, sess, body in users:
        w.write("## %s  [%s]\n%s\n\n" % (stamp, sess, body))

with open(os.path.join(OUT, "02_历史压缩摘要.md"), "w", encoding="utf-8") as w:
    w.write("# 历史压缩摘要（cb_summary，共 %d 条，倒序）\n\n" % len(summaries))
    for stamp, sess, body in reversed(summaries):
        w.write("## %s  [%s]\n%s\n\n" % (stamp, sess, body))

with open(os.path.join(OUT, "03_助手回复摘要.md"), "w", encoding="utf-8") as w:
    w.write("# 助手回复（前 600 字，共 %d 条）\n\n" % len(asst))
    for stamp, sess, body in asst:
        w.write("## %s  [%s]\n%s\n\n" % (stamp, sess, body))

print("文件数:", len(files))
print("用户原话:", len(users), "| 压缩摘要:", len(summaries), "| 助手回复:", len(asst))
for f, a, b in stat:
    if a or b:
        print("  %-70s u=%d a=%d" % (f.split("projects/")[-1], a, b))

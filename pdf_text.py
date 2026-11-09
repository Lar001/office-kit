#!/usr/bin/env python3
# 用法: python3 extract_pdf_text.py <文件.pdf> [输出.txt]
# 适用于无 ToUnicode、CIDFontType2 + CIDToGIDMap/Identity 的 PDF（Word 打印生成常见）
# 原理: 提取内嵌 FontFile2 的 TrueType cmap -> GID 反查 Unicode -> 解码内容流 CID
import re, zlib, struct, sys

def get_stream(data, n):
    m = re.search((str(n) + r' 0 obj').encode(), data)
    if not m: return None
    s = data.find(b'stream', m.end()); s = data.find(b'\n', s) + 1
    e = data.find(b'endstream', s)
    raw = data[s:e].rstrip(b'\r\n')
    try: return zlib.decompress(raw)
    except Exception: return raw

def build_g2u(ttf):
    numTables = struct.unpack('>H', ttf[4:6])[0]
    cmap_off = None
    for i in range(numTables):
        tag, _, off, _ = struct.unpack('>4sIII', ttf[12+16*i:28+16*i])
        if tag == b'cmap': cmap_off = off
    if cmap_off is None: return {}
    n = struct.unpack('>H', ttf[cmap_off+2:cmap_off+4])[0]
    u2g = {}
    for j in range(n):
        pid, eid, so = struct.unpack('>HHI', ttf[cmap_off+4+8*j:cmap_off+4+8*j+8])
        a = cmap_off + so
        fmt = struct.unpack('>H', ttf[a:a+2])[0]
        if fmt == 4:
            segX2 = struct.unpack('>H', ttf[a+6:a+8])[0]; seg = segX2//2
            endo = struct.unpack('>%dH'%seg, ttf[a+14:a+14+segX2])
            starto = struct.unpack('>%dH'%seg, ttf[a+16+segX2:a+16+2*segX2])
            delta = struct.unpack('>%dh'%seg, ttf[a+16+2*segX2:a+16+3*segX2])
            rpos = a+16+3*segX2
            rangeo = struct.unpack('>%dH'%seg, ttf[rpos:rpos+segX2])
            for s2 in range(seg):
                for c in range(starto[s2], endo[s2]+1):
                    if rangeo[s2] == 0: g = (c+delta[s2])&0xFFFF
                    else:
                        go = rpos+2*s2+rangeo[s2]
                        gi = struct.unpack('>H', ttf[go+2*(c-starto[s2]):go+2*(c-starto[s2])+2])[0]
                        if gi == 0: continue
                        g = (gi+delta[s2])&0xFFFF
                    if g: u2g.setdefault(c, g)
    g2u = {}
    for u, g in sorted(u2g.items()): g2u.setdefault(g, chr(u))
    return g2u

def main(path, out=None):
    data = open(path, 'rb').read()
    objs = re.findall(rb'(\d+) 0 obj(.{0,800}?)(?:stream|endobj)', data, re.S)
    fontfiles, fontmap, pages = {}, {}, []
    for num, body in objs:
        b = body.decode('latin1')
        if '/FontFile2' in b:
            m = re.search(r'/FontFile2 (\d+) 0 R', b)
            ref = num if '/Length1' in b and '/FontFile2' not in b else m.group(1) if m else num
            fontfiles[num.decode()] = None
        if '/BaseFont /CIDFont' in b:
            m = re.search(r'/FontFile2 (\d+) 0 R', b)
            if m: fontfiles[m.group(1)] = num.decode()
    fonts = {}
    for ff, fname in fontfiles.items():
        if fname and fname.isdigit():
            ttf = get_stream(data, int(ff))
            if ttf and ttf[:4] in (b'\x00\x01\x00\x00', b'true', b'OTTO'):
                fonts[fname] = build_g2u(ttf)
    union = {}
    for g2u in fonts.values():
        for g, u in g2u.items(): union.setdefault(g, u)
    # 页对象: /Contents [ N 0 R ] 且 /MediaBox
    for num, body in objs:
        b = body.decode('latin1')
        if '/MediaBox' in b:
            cs = re.findall(r'/Contents \[ (\d+) 0 R \]', b)
            if not cs:
                m = re.search(r'/Contents (\d+) 0 R', b)
                cs = [m.group(1)] if m else []
            pages.append((int(num), [int(x) for x in cs]))
    pages.sort()
    # 字体资源映射 /F1 11 0 R -> BaseFont 对象号
    fref = {}
    for num, body in objs:
        b = body.decode('latin1')
        for m in re.finditer(r'/(F\d+) (\d+) 0 R', b):
            fref[m.group(1)] = m.group(2)
    full = ''
    for pn, contents in pages:
        full += '\n===== 第 %d 页 =====\n' % (len(full.count('页')+1) if False else pages.index((pn, contents))+1)
        for c in contents:
            content = get_stream(data, c)
            if not content: continue
            cur = None; out = []
            for t in re.finditer(rb'/(F\d+)\s+[\d.]+\s+Tf|<([0-9A-Fa-f]+)>', content):
                if t.group(1):
                    key = fref.get(t.group(1).decode(), t.group(1).decode())
                    cur = key if key in fonts else t.group(1).decode()
                else:
                    hexs = t.group(2).decode()
                    for j in range(0, len(hexs), 4):
                        gid = int(hexs[j:j+4], 16)
                        ch = fonts.get(cur, {}).get(gid) or union.get(gid)
                        out.append(ch if ch else (' ' if gid == 3 else ''))
            full += ''.join(out)
    if out_path := (out or path.rsplit('.', 1)[0] + '_提取文本.txt'):
        open(out_path, 'w').write(full)
        print('已保存:', out_path)
    print(full)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

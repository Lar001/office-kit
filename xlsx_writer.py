import zipfile,re

FONTS=[
 '<font><sz val="11"/><color rgb="FF222222"/><name val="宋体"/></font>',                       #0
 '<font><b/><sz val="16"/><color rgb="FF1F3864"/><name val="微软雅黑"/></font>',               #1
 '<font><sz val="9"/><color rgb="FF808080"/><name val="宋体"/></font>',                        #2
 '<font><b/><sz val="10.5"/><color rgb="FFFFFFFF"/><name val="宋体"/></font>',                 #3
 '<font><b/><sz val="11"/><color rgb="FF1F3864"/><name val="宋体"/></font>',                   #4
 '<font><sz val="10"/><color rgb="FF333333"/><name val="宋体"/></font>',                       #5
 '<font><b/><sz val="11"/><color rgb="FFC00000"/><name val="宋体"/></font>',                   #6
]
FILLS=[
 '<fill><patternFill patternType="none"/></fill>',
 '<fill><patternFill patternType="gray125"/></fill>',
 '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill>', #2 表头
 '<fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F1"/><bgColor indexed="64"/></patternFill></fill>', #3 合计
 '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>', #4 提示
]
BORDERS=['<border><left/><right/><top/><bottom/><diagonal/></border>',
 '<border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border>']

# cellXfs
XFS=[
 ('0','0','0',0),   #0 default
 ('1','0','0',0),   #1 title
 ('2','0','0',0),   #2 subtitle
 ('3','2','1',1),   #3 header
 ('0','0','1',2),   #4 text center border
 ('0','0','1',3),   #5 int
 ('0','0','1',4),   #6 dec2
 ('0','0','1',5),   #7 pct(0.00"%")
 ('4','3','1',2),   #8 total text
 ('4','3','1',3),   #9 total int
 ('4','3','1',4),   #10 total dec
 ('4','3','1',5),   #11 total pct
 ('5','4','1',6),   #12 note wrap
 ('5','0','0',6),   #13 note nowrap
 ('6','3','1',2),   #14 total red text
 ('0','0','1',7),   #15 money 2dec
 ('0','0','1',8),   #16 dec4
 ('5','0','0',0),   #17 note(左对齐/顶部/换行/无框)
]
NUMFMT='<numFmts count="4"><numFmt numFmtId="176" formatCode="#,##0"/><numFmt numFmtId="177" formatCode="#,##0.00"/><numFmt numFmtId="178" formatCode="0.00&quot;%&quot;"/><numFmt numFmtId="179" formatCode="0.0000"/></numFmts>'
NFID={'0':0,'1':0,'2':0,'3':176,'4':177,'5':178,'6':'@','7':177,'8':179}
def cellxfs():
    out=[]
    for f,fill,bord,nf in XFS:
        out.append(f'<xf numFmtId="{NFID.get(nf,0)}" fontId="{f}" fillId="{fill}" borderId="{bord}" xfId="0"'+(f' applyNumberFormat="1"' if NFID.get(nf,0) else '')+' applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="'+
                   ('left' if f in ('1','2','5','12','13','17') else 'center')+'" vertical="'+
                   ('top' if f in ('12','17') else 'center')+'" wrapText="'+(('1' if f in ('3','12','17') else '0'))+'"/></xf>')
    return out

STYLES='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+NUMFMT+\
 '<fonts count="%d">'%len(FONTS)+''.join(FONTS)+'</fonts><fills count="%d">'%len(FILLS)+''.join(FILLS)+'</fills><borders count="2">'+''.join(BORDERS)+'</borders>'+\
 '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'+\
 '<cellXfs count="%d">'%len(XFS)+''.join(cellxfs())+'</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'

def esc(s):
    return (s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))

def colname(n):
    s=''
    while n>0:
        n,r=divmod(n-1,26); s=chr(65+r)+s
    return s

def sheet_xml(rows, widths=None, merges=None, freeze=None):
    out=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if freeze:
        out.append(f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="{freeze}" topLeftCell="A{freeze+1}" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
    out.append('<sheetFormatPr defaultRowHeight="18"/>')
    if widths:
        out.append('<cols>'+''.join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i,w in enumerate(widths))+'</cols>')
    out.append('<sheetData>')
    for ri,row in enumerate(rows,1):
        cells=[]
        for ci,c in enumerate(row,1):
            if c is None: continue
            if isinstance(c,tuple):
                v,s=c
            else:
                v,s=c,4
            ref=f'{colname(ci)}{ri}'
            if v is None or v=='':
                cells.append(f'<c r="{ref}" s="{s}"/>'); continue
            if isinstance(v,str):
                cells.append(f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>')
            else:
                cells.append(f'<c r="{ref}" s="{s}"><v>{v}</v></c>')
        out.append(f'<row r="{ri}">'+''.join(cells)+'</row>')
    out.append('</sheetData>')
    if merges:
        out.append(f'<mergeCells count="{len(merges)}">'+''.join(f'<mergeCell ref="{m}"/>' for m in merges)+'</mergeCells>')
    out.append('</worksheet>')
    return ''.join(out)

def build(path, sheets):
    n=len(sheets)
    ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(n))+'<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'
    rels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{esc(s["name"])}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i,s in enumerate(sheets))+'</sheets></workbook>'
    wbr='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>' for i in range(n))+f'<Relationship Id="rId{n+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',ct)
        z.writestr('_rels/.rels',rels)
        z.writestr('xl/workbook.xml',wb)
        z.writestr('xl/_rels/workbook.xml.rels',wbr)
        z.writestr('xl/styles.xml',STYLES.replace('"0.00&quot;%"','"0.00\\"%\\""'))
        for i,s in enumerate(sheets):
            z.writestr(f'xl/worksheets/sheet{i+1}.xml',sheet_xml(s['rows'],s.get('widths'),s.get('merges'),s.get('freeze')))

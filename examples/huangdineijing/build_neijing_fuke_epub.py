#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素问 B 版复刻 EPUB 样书 v2（6 页：封面+叶1-5）——对齐紫微斗数全书 EPUB 定稿设计语言
（用户定稿要素：宣纸米白底、朱红标题体系、原叶托裱图 float 环绕限高、随文朱注、
 句读朱圈、凡例/版权说明入封面、colophon、窄屏堆叠）。
单一来源：fuke_text_map.json（由 build_neijing_fuke.py 导出，与 PDF 同源）。"""
import json, os, zipfile, html

ROOT = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(ROOT, 'fuke_text_map.json'), encoding='utf-8'))
CN = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
N_LEAF = 5
OUT = os.path.join(ROOT, '復刻-素問·上古天真論-樣版6頁.epub')

def esc(s): return html.escape(s, quote=False)

CSS = """/* 复刻对读重排版：相对单位，阅读器自适应（同紫微全书 EPUB 定稿体系） */
body{ font-family: serif; line-height: 1.95; margin: 0 6%; color: #2C2824; background: #FDFBF4; }
h1.doctitle{ text-align:center; letter-spacing:.35em; font-weight:600; margin:1.2em 0 .4em; font-size:1.7em; }
.subtitle{ text-align:center; color:#8A8069; letter-spacing:.28em; margin:0 0 1.6em; font-size:.95em; }
h2.sec{ font-size:1.25em; letter-spacing:.4em; color:#9E2F23; margin:2.2em 0 1em;
        border-bottom:1px solid #C9B98A; padding-bottom:.3em; font-weight:600; }
h3.leaf-h{ font-size:1.1em; letter-spacing:.3em; color:#9E2F23; margin:2.4em 0 1em;
        border-left:4px solid #9E2F23; padding-left:.6em; font-weight:600; }
h3.leaf-h small{ font-size:.72em; color:#8A8069; letter-spacing:.1em; margin-left:.6em; }
p{ text-align:justify; margin:.7em 0; text-indent:2em; }
p.noindent{ text-indent:0; }
.chapno{ color:#9E2F23; letter-spacing:.5em; font-size:.95em; margin:2em 0 .3em; text-indent:0; }
.gist{ font-size:.9em; color:#4E4738; background:#F6EFDD; border-left:3px solid #9E2F23;
       padding:.8em 1em; margin:1.2em 0; text-indent:0; }
.gist b{ color:#9E2F23; }
/* 左图右文对读区块：float 环绕（忌 flex——高于视口的 flex 块会被分页阅读器整块裁断）
   图限高 ≤20em 保证单页完整 */
.pair{ margin:1em 0 1.6em; }
.pair::after{ content:""; display:table; clear:both; }
.pair figure{ float:left; width:36%; max-width:10.5em; margin:0 1em .6em 0; text-align:center; }
.pair figure img{ max-width:100%; max-height:20em; width:auto; height:auto;
                  border:1px solid #C9B98A; padding:2%; background:#fff; }
.pair figcaption{ font-size:.72em; color:#8A8069; margin-top:.4em; text-align:center; text-indent:0; line-height:1.6; }
.pair figcaption b{ color:#2C2824; }
.pair .txt{ min-width:0; }
.lsrc{ display:block; color:#8A8069; }
@media (max-width: 30em){
  .pair figure{ float:none; display:block; max-width:12em; margin:0 auto 1em; }
}
/* 复刻录文：正文墨字、句读朱圈、随文朱注（元刻经注双行小字之重排对应） */
.fu{ font-size:1.08em; line-height:2.15; letter-spacing:.05em; text-indent:0; margin:.45em 0; }
.d{ color:#9E2F23; font-size:.7em; }                       /* 句读圈 */
.z{ color:#9E2F23; font-size:.78em; }                     /* 王冰注/新校正=朱字随文 */
.z.blk{ display:block; text-indent:0; margin:.5em 0; line-height:1.9; }
.pian{ font-size:1.35em; letter-spacing:.3em; color:#2C2824; font-weight:600; text-indent:0; margin:1em 0 .3em; }
.pian b{ color:#9E2F23; font-weight:600; }
.lit{ font-size:.85em; color:#9E2F23; letter-spacing:.35em; margin:1.4em 0 .3em; text-indent:0; font-weight:bold; }
.note{ font-size:.85em; color:#8A8069; text-indent:0; }
.fanli p{ font-size:.88em; color:#4E4738; text-indent:0; margin:.45em 0; }
.colophon{ margin-top:3em; padding-top:1.5em; border-top:1px solid #C9B98A; color:#8A8069;
           font-size:.85em; text-align:center; text-indent:0; }
figure.ctr{ text-align:center; margin-top:12%; }
figure.ctr img{ max-width:80%; max-height:26em; border:1px solid #C9B98A; padding:2%; background:#fff; }
figure.ctr figcaption{ font-size:.75em; color:#8A8069; margin-top:.4em; }
"""

def leaf_flow(leaf):
    """大字流：句读朱圈 + 锚位随文朱注"""
    notes = {p: v for p, v in leaf['notes']}
    marks = set(leaf.get('marks', []))
    out = []
    for i, ch in enumerate(leaf['text']):
        out.append(esc(ch))
        if i in marks:
            out.append('<span class="d">。</span>')
        for _kind, t in notes.get(i, []):
            out.append(f'<span class="z">〔{esc(t)}〕</span>')
    return ''.join(out)

def page(title, body_):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            'xml:lang="zh-Hant">\n<head><meta charset="utf-8"/><title>' + title + '</title>\n'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            f'<body>\n{body_}\n</body></html>')

def cover_xhtml():
    return page('封面', '''<figure class="ctr"><img src="img/cover.jpg" alt="卷端書影"/>
<figcaption>卷端書影（元至元五年胡氏古林書堂刻本）</figcaption></figure>
<p class="noindent" style="text-align:center;margin-top:1.2em"><span style="font-size:2.2em;letter-spacing:.4em;font-weight:600">黃帝內經素問</span></p>
<p class="subtitle">卷一 · 上古天真論篇第一 · 复刻對讀樣版（六頁）</p>
<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em">[唐] 王冰 注 · [宋] 林億 等 校正 · 元至元五年胡氏古林書堂刻本</p>
<h2 class="sec">凡例</h2>
<div class="fanli">
<p>一、本書為元刻本數字复刻之重排樣書：每葉左為原書葉書影、右為對應复刻錄文，一葉一葉一一對應。</p>
<p>二、錄文墨字；<span class="d">。</span>朱圈為句讀（據整理本自動對齊落圈，還原元刻圈點）。</p>
<p>三、<span class="z">〔朱字〕</span>為隨文注文：王冰注與新校正俱作朱色小字，緊接所注正文之後（對應元刻雙行小字）。</p>
<p>四、卷端葉另含篇題下注與序注，據元刻葉一目驗轉錄、四庫本互校。</p>
<p>五、葉圖來源：哈佛大學圖書館藏《新刊補注釋文黃帝內經素問》元至元五年胡氏古林書堂刻本（ZHSY000605）數字影像，全冊統一，各葉不再重注。</p>
<p>六、复刻 PDF（直排刻本風）與本 EPUB（重排對讀風）同出一源：同一錄文數據與逐葉列錨定表。</p>
</div>''')

def leaf_xhtml(k):
    leaf = M['leaves'][k - 1]
    cn = CN[k] if k < len(CN) else str(k)
    n0 = sum(len(M['leaves'][j]['text']) for j in range(k - 1)) + 1
    n1 = n0 + len(leaf['text']) - 1
    if k == 1:
        lead = M['lead']
        head = (f'<p class="pian"><b>○</b>{esc(lead["pian"])}</p>'
                f'<p class="z blk">{esc(lead["title_note"])}</p>'
                f'<p class="z blk">{esc(lead["pre_notes"])}</p>')
    else:
        head = ''
    cap = '原書葉　卷一　第' + cn + '葉'
    body = (f'<p class="chapno">卷一 · 上古天真論篇第一</p>'
            f'<h3 class="leaf-h">第{cn}葉<small>錄文第 {n0}–{n1} 字</small></h3>'
            '<div class="pair">'
            f'<figure><img src="img/leaf{k}.jpg" alt="{cap}"/>'
            f'<figcaption><b>{cap.split("　")[0]}</b>　卷一　第{cn}葉</figcaption></figure>'
            f'<div class="txt">{head}<p class="fu">{leaf_flow(leaf)}</p></div></div>')
    if k == N_LEAF:
        body += ('<p class="colophon">黃帝內經素問 · 上古天真論篇第一 · 复刻樣版（六頁）<br/>'
                 '底本：元至元五年胡氏古林書堂刻本 · 錄文與列錨同源 build_neijing_fuke.py</p>')
    return page(f'第{cn}葉', body)

NAV = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
       '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hant">\n'
       '<head><meta charset="utf-8"/><title>目錄</title></head><body>\n'
       '<nav epub:type="toc" id="toc"><h1>目錄</h1><ol>\n'
       '<li><a href="cover.xhtml">封面 · 凡例</a></li>\n'
       + ''.join(f'<li><a href="leaf{k}.xhtml">第{CN[k]}葉</a></li>\n' for k in range(1, N_LEAF + 1))
       + '</ol></nav>\n<nav epub:type="landmarks" hidden="hidden"><ol>\n'
         '<li><a epub:type="cover" href="cover.xhtml">封面</a></li>\n'
         '<li><a epub:type="bodymatter" href="leaf1.xhtml">正文</a></li>\n'
         '</ol></nav>\n</body></html>')

OPF = '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="zh-Hant">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="bid">neijing-fuke-sample-6p-v2</dc:identifier>
  <dc:title>黃帝內經素問 上古天真論篇第一（復刻對讀樣版·六頁）</dc:title>
  <dc:creator>[唐] 王冰 注</dc:creator>
  <dc:language>zh-Hant</dc:language>
  <meta property="dcterms:modified">2026-10-01T00:00:00Z</meta>
 </metadata>
 <manifest>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="css" href="style.css" media-type="text/css"/>
  <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
''' + ''.join(f'  <item id="l{k}" href="leaf{k}.xhtml" media-type="application/xhtml+xml"/>\n' for k in range(1, N_LEAF + 1)) + '''  <item id="icv" href="img/cover.jpg" media-type="image/jpeg"/>
''' + ''.join(f'  <item id="im{k}" href="img/leaf{k}.jpg" media-type="image/jpeg"/>\n' for k in range(1, N_LEAF + 1)) + ''' </manifest>
 <spine>
  <itemref idref="cover"/>
''' + ''.join(f'  <itemref idref="l{k}"/>\n' for k in range(1, N_LEAF + 1)) + ''' </spine>
</package>'''

CONTAINER = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

def main():
    z = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED)
    z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip')
    z.writestr('META-INF/container.xml', CONTAINER)
    z.writestr('OEBPS/content.opf', OPF)
    z.writestr('OEBPS/nav.xhtml', NAV)
    z.writestr('OEBPS/style.css', CSS)
    z.writestr('OEBPS/cover.xhtml', cover_xhtml())
    for k in range(1, N_LEAF + 1):
        z.writestr(f'OEBPS/leaf{k}.xhtml', leaf_xhtml(k))
    z.write(os.path.join(ROOT, 'assets', 'yuan_cover.jpg'), 'OEBPS/img/cover.jpg')
    for k in range(1, N_LEAF + 1):
        src = f'/tmp/yuan_h{k}.jpg'
        if not os.path.exists(src):
            raise SystemExit(f'缺原叶图 {src}（先跑 build_neijing_fuke.py）')
        z.write(src, f'OEBPS/img/leaf{k}.jpg')
    z.close()
    print(OUT, os.path.getsize(OUT) // 1024, 'KB')

if __name__ == '__main__':
    main()

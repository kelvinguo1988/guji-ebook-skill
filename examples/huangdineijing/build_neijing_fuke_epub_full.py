#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》B 版复刻·全书 EPUB（81 章流式对读本，紫微/第一章定稿设计语言）
单一来源：fuke_text_map_full.json（build_neijing_fuke_full.py 导出）。
全书无逐叶元刻锚定，故不嵌原叶书影（SKILL §0.5.17 无对应即关闭对照），仅卷端书影入封面。"""
import json, os, zipfile, html

ROOT = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(ROOT, 'fuke_text_map_full.json'), encoding='utf-8'))
from build_neijing_fuke_epub import CSS, page   # 同款设计语言（style.css 与页模板唯一来源）

OUT = os.path.join(ROOT, '復刻-素問全書.epub')
JUANS = ['卷之一', '卷之二', '卷之三', '卷之四', '卷之五', '卷之六',
         '卷之七', '卷之八', '卷之九', '卷之十', '卷之十一', '卷之十二']

def esc(s): return html.escape(s, quote=False)

def chapter_flow(c):
    notes = {p: v for p, v in c['notes']}
    marks = set(c['marks'])
    out = []
    for i, ch in enumerate(c['text']):
        out.append(esc(ch))
        if i in marks:
            out.append('<span class="d">。</span>')
        for _kind, t in notes.get(i, []):
            out.append(f'<span class="z">〔{esc(t)}〕</span>')
    return ''.join(out)

def chapter_xhtml(c):
    lead = (M['lead'] or {}) if c['num'] == 1 else None
    head = ''
    if c['num'] == 1 and lead:
        head = (f'<p class="z blk">{esc(lead["title_note"])}</p>'
                f'<p class="z blk">{esc(lead["pre_notes"])}</p>')
    elif c['title_note']:
        head = f'<p class="z blk">{esc(c["title_note"])}</p>'
    body = (f'<p class="chapno">{JUANS[c["juan"] - 1]}</p>'
            f'<h3 class="leaf-h"><b>○</b>{esc(c["title"])}'
            f'<small>錄文 {len(c["text"])} 字·注 {sum(len(t) for _, v in c["notes"] for _k, t in v)} 字</small></h3>'
            f'<div>{head}<p class="fu">{chapter_flow(c)}</p></div>')
    if c['num'] == 81:
        body += ('<p class="colophon">黃帝內經素問 · 全書八十一篇 · 复刻重排本<br/>'
                 '底本：元至元五年胡氏古林書堂刻本（哈佛大學圖書館藏 ZHSY000605）· '
                 '錄文與古注：四部叢刊系統錄文（王冰注·林億校正·孫兆改誤），與元刻葉面通校<br/>'
                 '句讀據殆知閣標點本自動對齊 · 版式與 PDF 同源 build_neijing_fuke_full.py</p>')
    return page(c['title'], body)

def cover_xhtml():
    return page('封面', '''<figure class="ctr"><img src="img/cover.jpg" alt="卷端書影"/>
<figcaption>卷端書影（元至元五年胡氏古林書堂刻本）</figcaption></figure>
<p class="noindent" style="text-align:center;margin-top:1.2em"><span style="font-size:2.2em;letter-spacing:.4em;font-weight:600">黃帝內經素問</span></p>
<p class="subtitle">全書八十一篇 · 唐啟玄子次注 · 复刻重排本</p>
<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em">[唐] 王冰 注 · [宋] 林億 等 校正 · [宋] 孫兆 改誤 · 元至元五年胡氏古林書堂刻本</p>
<h2 class="sec">凡例</h2>
<div class="fanli">
<p>一、本書為元刻本《新刊補注釋文黃帝內經素問》十二卷八十一篇之數字复刻重排本，與直排刻本風 PDF 同出一源（同一錄文、注、句讀數據）。</p>
<p>二、錄文墨字；<span class="d">。</span>朱圈為句讀，據標點整理本自動對齊落圈，還原元刻圈點之制。</p>
<p>三、<span class="z">〔朱字〕</span>為隨文注文：王冰注與新校正俱作朱色小字，緊接所注正文之後（對應元刻雙行小字之體）。</p>
<p>四、篇題標○，題下注次於題後；卷一端另存新校正序注，據元刻葉面目驗轉錄、集成本互校。</p>
<p>五、全書未逐葉錨定元刻葉界，故不附原葉書影（逐葉對讀樣版見第一章六頁樣書）；書影僅存卷端一幀。</p>
<p>六、異體字一仍錄文之舊（四部叢刊系），不強改古今字；缺文殘處不臆補。</p>
</div>''')

def nav_xhtml():
    lines = ['<li><a href="cover.xhtml">封面 · 凡例</a></li>']
    cur = None
    for c in M['chapters']:
        if c['juan'] != cur:
            if cur is not None:
                lines.append('</ol></li>')
            cur = c['juan']
            lines.append(f'<li><span>{JUANS[cur - 1]}</span><ol>')
        lines.append(f'<li><a href="ch{c["num"]}.xhtml">{esc(c["title"])}</a></li>')
    lines.append('</ol></li>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hant">\n'
            '<head><meta charset="utf-8"/><title>目錄</title></head><body>\n'
            '<nav epub:type="toc" id="toc"><h1>目錄</h1><ol>\n' + '\n'.join(lines) +
            '\n</ol></nav>\n<nav epub:type="landmarks" hidden="hidden"><ol>\n'
            '<li><a epub:type="cover" href="cover.xhtml">封面</a></li>\n'
            '<li><a epub:type="bodymatter" href="ch1.xhtml">正文</a></li>\n'
            '</ol></nav>\n</body></html>')

def opf():
    items = ''.join(f'  <item id="c{c["num"]}" href="ch{c["num"]}.xhtml" '
                    f'media-type="application/xhtml+xml"/>\n' for c in M['chapters'])
    spine = ''.join(f'  <itemref idref="c{c["num"]}"/>\n' for c in M['chapters'])
    return '''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="zh-Hant">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="bid">neijing-fuke-full-81</dc:identifier>
  <dc:title>黃帝內經素問 全書（復刻重排本）</dc:title>
  <dc:creator>[唐] 王冰 注</dc:creator>
  <dc:language>zh-Hant</dc:language>
  <meta property="dcterms:modified">2026-10-01T00:00:00Z</meta>
 </metadata>
 <manifest>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="css" href="style.css" media-type="text/css"/>
  <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
''' + items + '''  <item id="icv" href="img/cover.jpg" media-type="image/jpeg"/>
 </manifest>
 <spine>
  <itemref idref="cover"/>
''' + spine + ''' </spine>
</package>'''

CONTAINER = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

def main():
    z = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED)
    z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip')
    z.writestr('META-INF/container.xml', CONTAINER)
    z.writestr('OEBPS/content.opf', opf())
    z.writestr('OEBPS/nav.xhtml', nav_xhtml())
    z.writestr('OEBPS/style.css', CSS)
    z.writestr('OEBPS/cover.xhtml', cover_xhtml())
    for c in M['chapters']:
        z.writestr(f'OEBPS/ch{c["num"]}.xhtml', chapter_xhtml(c))
    z.write(os.path.join(ROOT, 'assets', 'yuan_cover.jpg'), 'OEBPS/img/cover.jpg')
    z.close()
    print(OUT, os.path.getsize(OUT) // 1024, 'KB, chapters:', len(M['chapters']))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""道德经 B 版复刻 EPUB（FXL pre-paginated，随 PDF 逐页同版式，右→左 rtl 书脊）
用法：python3 build_ddj_fuke_epub.py  →  復刻-道德經·一至四章.epub
页源：復刻-道德經·一至四章.pdf（build_ddj_fuke.py 产物），每页渲 1.6x PNG 整页嵌入。"""
import os, zipfile, html
import fitz

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, '復刻-道德經·一至四章.pdf')
OUT = os.path.join(ROOT, '復刻-道德經·一至四章.epub')
TITLE = '老子道德經注（古逸叢書景刊王弼注本）復刻樣式'
SUB = '復刻本樣式·一至四章·左原葉右復刻逐葉對讀'

TOC = ['卷首封面葉（遵義黎氏校刊牌記）', '卷端葉：老子道德經上篇　一章　晉王弼注',
       '第一章（續）故常無欲以觀其妙', '第二章　天下皆知美之為美', '第二章（續）',
       '第三章　不尚賢', '第三章（續）是以聖人之治', '第四章　道沖而用之', '第四章（續·注尾）']

doc = fitz.open(SRC)
os.makedirs(os.path.join(ROOT, 'epub_fuke'), exist_ok=True)
pages = []
for i, p in enumerate(doc):
    pm = p.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))   # 原生画布 2480×1860 已足
    name = f'p{i+1}.png'
    pages.append((name, pm.width, pm.height))
    pm.save(os.path.join(ROOT, 'epub_fuke', name))
doc.close()

CONTAINER = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

manifests, spine, xhtmls = [], [], []
for k, (name, w, h) in enumerate(pages):
    pid = name.split('.')[0]
    manifests.append(f'<item id="{pid}" href="{name}" media-type="image/png"/>')
    manifests.append(f'<item id="{pid}_x" href="{pid}.xhtml" media-type="application/xhtml+xml"/>')
    spine.append(f'<itemref idref="{pid}_x"/>')
    xhtmls.append((pid, f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{html.escape(TITLE)}</title>
<meta name="viewport" content="width={w}, height={h}"/>
<style>html,body{{margin:0;padding:0}}img{{width:{w}px;height:{h}px;display:block}}</style>
</head>
<body><img src="{name}" alt="{html.escape(TOC[k]) if k < len(TOC) else pid}"/></body></html>'''))

NAV = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目錄</title></head>
<body><nav epub:type="toc"><h1>{html.escape(TITLE)}</h1><ol>
{chr(10).join(f'<li><a href="p{j+1}.xhtml">{html.escape(t)}</a></li>' for j, t in enumerate(TOC))}
</ol></nav></body></html>'''

OPF = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid" xml:lang="zh-Hant">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:identifier id="bid">urn:uuid:ddj-fuke-2026-sample</dc:identifier>
  <dc:title>{html.escape(TITLE)}</dc:title>
  <dc:creator>魏 王弼 注</dc:creator>
  <dc:description>{html.escape(SUB)}</dc:description>
  <dc:language>zh-Hant</dc:language>
  <meta property="dcterms:modified">2026-10-03T00:00:00Z</meta>
  <meta name="cover" content="p1"/>
 </metadata>
 <manifest>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  {''.join(manifests)}
 </manifest>
 <spine page-progression-direction="rtl">{''.join(spine)}</spine>
</package>'''

os.makedirs(os.path.join(ROOT, 'epub_fuke'), exist_ok=True)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('mimetype', 'application/epub+zip', zipfile.ZIP_STORED)
    z.writestr('META-INF/container.xml', CONTAINER)
    z.writestr('OEBPS/content.opf', OPF)
    z.writestr('OEBPS/nav.xhtml', NAV)
    for name, _, _ in pages:
        z.write(os.path.join(ROOT, 'epub_fuke', name), f'OEBPS/{name}')
    for pid, x in xhtmls:
        z.writestr(f'OEBPS/{pid}.xhtml', x)
print(f'{OUT}: {len(pages)} 页 FXL（rtl）')

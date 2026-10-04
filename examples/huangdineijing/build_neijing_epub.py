#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》A 版重排 EPUB（reflowable）——单一来源 neijing_full.html 的流式 section。
每卷 vol-head + 逐篇 pian → xhtml；书影降采样嵌入；print 版 CSS 剥离 @page/固定尺寸后复用。
用法：python3 build_neijing_epub.py  →  黄帝内经素问-全书.epub"""
import re, os, html, zipfile, uuid, datetime
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
H = open(os.path.join(ROOT, 'neijing_full.html'), encoding='utf-8').read()
TITLE = '黃帝內經素問'

# ---- 切 section（全部为同级兄弟，无嵌套） ----
secs = []
for m in re.finditer(r'<section class="([a-z-]+)">(.*?)</section>', H, re.S):
    secs.append((m.group(1), m.group(2)))
kinds = [k for k, _ in secs]
assert kinds.count('pian') == 81, f'篇数异常: {kinds.count("pian")}'
print('sections:', len(secs), '| pian:', kinds.count('pian'), '| vol-head:', kinds.count('vol-head'))

def esc(s): return html.escape(s, quote=False)
def xml_repair(s):
    s = re.sub(r'<(img|br|hr)((?:[^>/]|/(?!>))*)>', r'<\1\2/>', s)
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', s)
    return s

def page_doc(title, body):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/><title>{esc(title)}</title>'
            f'<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>\n<body>\n'
            f'{xml_repair(body)}\n</body></html>')

# ---- CSS：取 print 版样式，剥 @page 与固定页尺寸，加 EPUB 覆盖 ----
m = re.search(r'<style>(.*?)</style>', H, re.S)
css = m.group(1)
css = re.sub(r'@page[^{]*\{[^}]*\}', '', css)
css += '''
/* ---- EPUB reflow 覆盖 ---- */
html,body{background:#FFF !important}
body{max-width:44em;margin:0 auto;padding:1.2em 1em;line-height:1.95}
.page{width:auto !important;min-height:auto !important;height:auto !important;padding:0 !important;margin:0 !important;border:none !important;break-after:auto !important}
section{break-after:auto}
img{max-width:100%;height:auto}
.vol-head,.pian-head{margin-top:2.2em}
'''

BUILD = os.path.join(ROOT, 'epub_nj')
for d in ['OEBPS/text', 'OEBPS/styles', 'OEBPS/images', 'META-INF']:
    os.makedirs(os.path.join(BUILD, d), exist_ok=True)
open(os.path.join(BUILD, 'mimetype'), 'w').write('application/epub+zip')
open(os.path.join(BUILD, 'META-INF/container.xml'), 'w', encoding='utf-8').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
open(os.path.join(BUILD, 'OEBPS/styles/epub.css'), 'w', encoding='utf-8').write(css)

# ---- 图片降采样嵌入 ----
imgs = sorted(set(re.findall(r'src="assets/([^"]+)"', H)))
img_files, img_items = [], []
for i, name in enumerate(imgs):
    src = os.path.join(ROOT, 'assets', name)
    if not os.path.exists(src):
        continue
    im = Image.open(src).convert('RGB')
    if im.width > 1000:
        im = im.resize((1000, int(im.height * 1000 / im.width)), Image.LANCZOS)
    jpg = name.rsplit('.', 1)[0] + '.jpg'
    im.save(os.path.join(BUILD, 'OEBPS/images', jpg), 'JPEG', quality=82)
    img_files.append(jpg)
    img_items.append(f'<item id="img{i}" href="images/{jpg}" media-type="image/jpeg"/>')
print('images:', img_files)

# ---- 分文件：前件 / 12 卷（卷隔页+各篇） / 跋 ----
files, nav = [], []   # (fname, title, doc)
def add(fn, t, body):
    files.append((fn, page_doc(t, body)))
    nav.append((t, fn))

CN = '〇一二三四五六七八九十'
def cnum(n):
    return CN[n] if n < 10 else ('十' + CN[n % 10] if n % 10 else '十') if n < 20 else CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')

pian_secs = [(k, b) for k, b in secs if k == 'pian']
front = {k: b for k, b in secs if k in ('cover-page', 'titlepage', 'fanli', 'bankan', 'shuying', 'toc-block', 'endpage', 'vol-head')}
vol_secs = [b for k, b in secs if k == 'vol-head']
toc_secs = [b for k, b in secs if k == 'toc-block']

add('cover.xhtml', '封面', f'<div class="cover-page">{front["cover-page"]}</div>')
add('titlepage.xhtml', '书名页', f'<div class="titlepage">{front["titlepage"]}</div>')
if 'fanli' in front:
    add('fanli.xhtml', '凡例', f'<h2 class="sec">凡例</h2><div class="fanli">{front["fanli"]}</div>')
if 'shuying' in front:
    body = f'<h2 class="sec">卷首书影</h2><div class="shuying">{front["shuying"]}</div>'
    body = body.replace('assets/', '../images/').replace('.png"', '.jpg"')
    add('shuying.xhtml', '卷首书影', body)
if toc_secs:
    add('mulu.xhtml', '总目', '<h2 class="sec">总目</h2>' + ''.join(f'<div class="toc-block">{t}</div>' for t in toc_secs))

# 卷隔页与卷区间（与 build_neijing_full.py 的 VOLS 同源解析）
VOLS = {}
mm = re.search(r'VOLS\s*=\s*\{(.*?)\}', open(os.path.join(ROOT, 'build_neijing_full.py'), encoding='utf-8').read(), re.S)
for k, va, vb in re.findall(r'(\d+)\s*:\s*\((\d+),\s*(\d+)\)', mm.group(1)):
    VOLS[int(k)] = (int(va), int(vb))
assert sum(b - a + 1 for a, b in VOLS.values()) == 81 and len(VOLS) == 12, VOLS
for v, vb in enumerate(vol_secs, 1):
    add(f'juan{v:02d}.xhtml', f'卷之{cnum(v)}',
        f'<div class="vol-head">{vb}</div>'.replace('assets/', '../images/').replace('.png"', '.jpg"'))

pi = 0
for v in range(1, 13):
    a, b = VOLS[v]
    for n in range(a, b + 1):
        _, body = pian_secs[pi]
        pi += 1
        t = esc(re.search(r'<div class="ti">([^<]+)</div>', body).group(1))
        add(f'pian{n:03d}.xhtml', f'{n:03d} {t}',
            f'<div class="pian">{body}</div>')
assert pi == 81

add('colophon.xhtml', '跋', f'<div class="endpage">{front["endpage"]}</div>')

# ---- 写文件 ----
for fn, doc in files:
    open(os.path.join(BUILD, 'OEBPS/text', fn), 'w', encoding='utf-8').write(doc)

nav_li = ''.join(f'<li><a href="text/{f}">{esc(t)}</a></li>' for t, f in nav)
NAV = (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
       f'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/>'
       f'<title>目录</title></head><body><nav epub:type="toc" id="toc"><h1>目錄</h1><ol>{nav_li}</ol></nav>'
       f'<nav epub:type="landmarks" hidden="hidden"><ol><li><a epub:type="bodymatter" href="text/pian001.xhtml">正文</a></li>'
       f'</ol></nav></body></html>')
open(os.path.join(BUILD, 'OEBPS/nav.xhtml'), 'w', encoding='utf-8').write(NAV)

uid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
file_items = '\n'.join(f'<item id="f{i}" href="text/{f}" media-type="application/xhtml+xml"/>'
                       for i, (f, _) in enumerate(files))
spine = ''.join(f'<itemref idref="f{i}"/>' for i in range(len(files)))
OPF = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
       f'unique-identifier="bid" xml:lang="zh-Hans"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
       f'<dc:identifier id="bid">urn:uuid:{uid}</dc:identifier><dc:title>{TITLE}</dc:title>'
       f'<dc:creator>唐 王冰 注 · 宋 林億等 校正</dc:creator><dc:language>zh-Hans</dc:language>'
       f'<meta property="dcterms:modified">{modified}</meta></metadata>'
       f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
       f'<item id="css" href="styles/epub.css" media-type="text/css"/>{"".join(img_items)}{file_items}</manifest>'
       f'<spine>{spine}</spine></package>')
open(os.path.join(BUILD, 'OEBPS/content.opf'), 'w', encoding='utf-8').write(OPF)

OUT = os.path.join(ROOT, '黄帝内经素问-全书.epub')
if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, 'w') as z:
    z.write(os.path.join(BUILD, 'mimetype'), 'mimetype', compress_type=zipfile.ZIP_STORED)
    for b, _, fs in os.walk(BUILD):
        for f in fs:
            full = os.path.join(b, f)
            rel = os.path.relpath(full, BUILD)
            if rel == 'mimetype':
                continue
            z.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)
print('EPUB written:', OUT, os.path.getsize(OUT) // 1024, 'KB,', len(files), 'files')

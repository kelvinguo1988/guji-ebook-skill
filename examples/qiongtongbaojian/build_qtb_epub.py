#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《窮通寶鑑箋注》全书 EPUB 打包：从 /tmp/qtb_sections.json 生成 113 节 EPUB 3"""
import re, os, json, datetime, uuid, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SECS = json.load(open('/tmp/qtb_sections.json', encoding='utf-8'))
BUILD = os.path.join(ROOT, 'epub_qtb')
OUT = os.path.join(ROOT, '穷通宝鉴笺注-全书.epub')

from opencc import OpenCC
cc = OpenCC('s2t')
ENT = {'&ldquo;': '「', '&rdquo;': '」', '&lsquo;': '『', '&rsquo;': '』',
       '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&ircquo;': '', '&nbsp;': ' '}

def clean_text(t):
    for k, v in ENT.items():
        t = t.replace(k, v)
    return re.sub(r'&[a-zA-Z#0-9]{1,8};', '', t)

def to_trad(t):
    return cc.convert(t)

def esc(t):
    return re.sub(r'\s+', ' ', clean_text(t)).strip()

def norm_quotes(s):
    out, open_q = [], True
    for c in s:
        if c == '"':
            out.append('「' if open_q else '」'); open_q = not open_q
        else:
            out.append(c)
    return ''.join(out)

GANS = ['甲木', '乙木', '丙火', '丁火', '戊土', '己土', '庚金', '辛金', '壬水', '癸水']
NUM_CN = '一二三四五六七八九十'

def vol_of(title):
    for i, g in enumerate(GANS):
        if g in title:
            return i
    return None


TERM = re.compile(r'[。？！」"]$')
def merge_softwrap(lines):
    paras, buf = [], ''
    for l in lines:
        l = re.sub(r'\s+', '', l)
        if not l: continue
        buf += l
        if TERM.search(buf):
            paras.append(buf); buf = ''
    if buf: paras.append(buf)
    return paras

def paras_of(t):
    return [re.sub(r'\s+', '', p) for p in t.split('\n') if re.sub(r'\s+', '', p)]

for d_ in ['OEBPS/text', 'OEBPS/styles', 'OEBPS/images', 'META-INF']:
    os.makedirs(os.path.join(BUILD, d_), exist_ok=True)
open(os.path.join(BUILD, 'mimetype'), 'w').write('application/epub+zip')
open(os.path.join(BUILD, 'META-INF/container.xml'), 'w').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')

CSS = '''body{ font-family: serif; line-height: 1.95; margin: 0 5%; color: #2C2824; background: #FDFBF4; }
h1.doctitle{ text-align:center; letter-spacing:.3em; font-weight:600; margin:1.8em 0 .6em; font-size:1.5em;}
.volnum{ text-align:center; color:#9E2F23; letter-spacing:.4em; margin:2.5em 0 0; font-size:.95em;}
h2.sec{ font-size:1.15em; letter-spacing:.35em; color:#9E2F23; margin:2em 0 1em;
        border-bottom:1px solid #C9B98A; padding-bottom:.3em; font-weight:600;}
p{ text-align:justify; margin:.7em 0; text-indent:2em;}
p.noindent{ text-indent:0; }
p.yw{ font-size:1.08em; line-height:2.15; letter-spacing:.05em;}
.xuzhu{ font-size:.85em; color:#4E4738; margin:.3em 0 1em 1.5em; padding-left:1em;
        border-left:2px solid #C9B98A; text-indent:0;}
.xuzhu .xtag{ color:#9E2F23; border:1px solid #9E2F23; border-radius:3px;
              padding:0 .3em; margin-right:.5em; font-size:.85em;}
.kwcard{ border:1px solid #C9B98A; background:#FBF7EC; padding:.8em 1em; margin:.8em 0; text-indent:0;}
.kwcard .kt{ font-weight:bold; background:#4E4738; color:#F6EFDD; padding:.05em .4em; margin-right:.5em;}
.kwcard p{ text-indent:0; margin:.3em 0;}
.qishi{ border:1px solid #C9B98A; background:#FBF7EC; padding:1em 1.2em; margin:1.2em 0; text-indent:0;}
.qishi .qt{ color:#9E2F23; letter-spacing:.35em; margin-bottom:.5em;}
.note{ font-size:.85em; color:#8A8069; text-indent:0;}
.colophon{ margin-top:3em; padding-top:1.5em; border-top:1px solid #C9B98A; color:#8A8069;
           font-size:.85em; text-align:center; text-indent:0;}
'''
open(os.path.join(BUILD, 'OEBPS/styles/epub.css'), 'w', encoding='utf-8').write(CSS)

from PIL import Image
for name, w in [("qtb_jiamu_leaf.png", 1100), ("qtb_jiamu_spread.png", 1400)]:
    im = Image.open(os.path.join(ROOT, 'assets', name)).convert('RGB')
    if im.width > w:
        im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    im.save(os.path.join(BUILD, 'OEBPS/images', name.replace('.png', '.jpg')), 'JPEG', quality=82)

def page_doc(title, body_html, fname):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/><title>{title}</title>'
            f'<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>\n<body>\n{body_html}\n</body></html>')

def xml_repair(s):
    s = re.sub(r'<(img|br|hr)((?:[^>/]|/(?!>))*)>', r'<\1\2/>', s)
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', s)
    return s

files, nav_items = [], []
files.append(('cover.xhtml', page_doc('封面',
    '<p class="noindent" style="text-align:center;margin-top:18%"><span style="font-size:2.6em;'
    'letter-spacing:.4em;font-weight:600">窮通寶鑑</span></p>'
    '<p class="noindent" style="text-align:center;letter-spacing:.4em;color:#8A8069">箋　注</p>'
    '<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em;margin-top:2em">'
    '十干月令調候祕本 · 欄江網 · 造化元鑰</p>', 'cover.xhtml')))
nav_items.append(('封面', 'cover.xhtml'))
files.append(('fanli.xhtml', page_doc('凡例',
    '<h1 class="doctitle">凡例</h1>'
    '<p class="noindent"><b>一、底本。</b>文字以排印整理本为底，参风陵文库藏清写刻本（书影随文）。</p>'
    '<p class="noindent"><b>二、体例。</b>每节先陈原文（繁体，附徐乐吾评注），继以白话通释、术语笺释与今人按语。</p>'
    '<p class="noindent"><b>三、用字。</b>原文、评注用繁体；白话、按语用简体。</p>'
    '<p class="noindent"><b>四、结构。</b>全书按十天干分十卷，卷内以十二月令立目，凡一百一十三节。</p>', 'fanli.xhtml')))
nav_items.append(('凡例', 'fanli.xhtml'))

last_vol = None
for n in range(1, 114):
    s = SECS[str(n)]
    vi = vol_of(s['title'])
    if vi is None:
        vi = last_vol
    if vi != last_vol:
        vn = f'chap{vi*100:03d}_vol.xhtml'
        body_v = (f'<p class="volnum">卷{NUM_CN[vi]} · 論{GANS[vi]}</p>'
                  f'<h1 class="doctitle">{GANS[vi]}</h1>'
                  f'<p class="noindent" style="text-align:center;color:#8A8069">凡{sum(1 for x in range(1,114) if vol_of(SECS[str(x)]["title"])==vi)}节</p>')
        files.append((vn, page_doc(f'卷{NUM_CN[vi]}', body_v, vn)))
        nav_items.append((f'卷{NUM_CN[vi]} · 論{GANS[vi]}', vn))
        last_vol = vi
    body_ep = [f'<h1 class="doctitle">第{n}节 · {esc(s["title"])}</h1>',
               '<h2 class="sec">原文</h2>']
    yparas = []
    for p in merge_softwrap(s['yuanwen'].split('\n')):
        p = norm_quotes(to_trad(p))
        if p.startswith('徐乐吾曰'):
            yparas.append(('xu', re.sub(r'^徐乐吾曰[:：]?', '', p)))
        else:
            yparas.append(('main', p))
    for kind, p in yparas:
        if kind == 'xu':
            body_ep.append(f'<div class="xuzhu"><span class="xtag">徐注</span>{esc(p)}</div>')
        else:
            body_ep.append(f'<p class="yw">{esc(p)}</p>')
    body_ep.append('<h2 class="sec">白话通释</h2>')
    for p in merge_softwrap(s['baihua'].split('\n')):
        body_ep.append(f'<p>{esc(norm_quotes(p))}</p>')
    kws = re.findall(r'([^\n：]{2,10})：([^\n]+)', s['kw'])
    if kws:
        body_ep.append('<h2 class="sec">术语笺释</h2>')
        for kt, kv in kws:
            body_ep.append(f'<div class="kwcard"><span class="kt">{esc(kt)}</span>'
                           f'<p>{esc(norm_quotes(kv))}</p></div>')
    qishi = merge_softwrap(s['qishi'].split('\n'))
    if qishi:
        body_ep.append('<div class="qishi"><div class="qt">今人按语</div>')
        for p in qishi:
            body_ep.append(f'<p>{esc(norm_quotes(p))}</p>')
        body_ep.append('</div>')
    fn = f'chap{n:03d}.xhtml'
    files.append((fn, page_doc(f'第{n}节 · {esc(s["title"])}', '\n'.join(body_ep), fn)))
    nav_items.append((f'第{n}节 · {esc(s["title"])}', fn))
files.append(('colophon.xhtml', page_doc('跋',
    '<div class="colophon">《窮通寶鑑》原名《欄江網》，一名《造化元鑰》。<br/>'
    '原文与徐乐吾评注以排印整理本为底、参风陵文库藏清写刻本对读。<br/>'
    '白话、术语笺释与今人按语从排印本辑录。全书一百一十三节。</div>', 'colophon.xhtml')))
nav_items.append(('跋', 'colophon.xhtml'))

for fname, doc in files:
    open(os.path.join(BUILD, 'OEBPS/text', fname), 'w', encoding='utf-8').write(xml_repair(doc))

nav_li = '\n'.join(f'<li><a href="text/{f}">{esc(t)}</a></li>' for t, f in nav_items)
NAV = (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
       f'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/>'
       f'<title>目录</title></head><body><nav epub:type="toc" id="toc"><h1>目錄</h1><ol>{nav_li}</ol></nav>'
       f'<nav epub:type="landmarks" hidden="hidden"><ol><li><a epub:type="bodymatter" href="text/cover.xhtml">正文</a></li>'
       f'</ol></nav></body></html>')
open(os.path.join(BUILD, 'OEBPS/nav.xhtml'), 'w', encoding='utf-8').write(NAV)
uid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
img_items = ('\n<item id="img1" href="images/qtb_jiamu_leaf.jpg" media-type="image/jpeg"/>'
             '\n<item id="img2" href="images/qtb_jiamu_spread.jpg" media-type="image/jpeg"/>')
file_items = '\n'.join(f'<item id="f{i}" href="text/{f}" media-type="application/xhtml+xml"/>'
                       for i, (f, _) in enumerate(files))
spine = '\n'.join(f'<itemref idref="f{i}"/>' for i in range(len(files)))
OPF = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
       f'unique-identifier="bid" xml:lang="zh-Hans"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
       f'<dc:identifier id="bid">urn:uuid:{uid}</dc:identifier><dc:title>窮通寶鑑箋注</dc:title>'
       f'<dc:creator>編纂</dc:creator><dc:language>zh-Hans</dc:language>'
       f'<meta property="dcterms:modified">{modified}</meta></metadata>'
       f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
       f'<item id="css" href="styles/epub.css" media-type="text/css"/>{img_items}{file_items}</manifest>'
       f'<spine>{spine}</spine></package>')
open(os.path.join(BUILD, 'OEBPS/content.opf'), 'w', encoding='utf-8').write(OPF)
NCX = (f'<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
       f'<head><meta name="dtb:uid" content="urn:uuid:{uid}"/></head>'
       f'<docTitle><text>窮通寶鑑箋注</text></docTitle><navMap>'
       + ''.join(f'<navPoint id="n{i}" playOrder="{i+1}"><navLabel><text>{esc(t)}</text></navLabel>'
                 f'<content src="text/{f}"/></navPoint>' for i, (t, f) in enumerate(nav_items))
       + '</navMap></ncx>')
open(os.path.join(BUILD, 'OEBPS/toc.ncx'), 'w', encoding='utf-8').write(NCX)

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
print('EPUB written:', OUT, os.path.getsize(OUT) // 1024, 'KB')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗数全书》全书 A 版整理 EPUB 3（南阳堂刊本对读）
结构：封面 · 编例 · 第一章太微赋（沿用定稿随文笺注版式）· 卷一~卷三（93 篇带标点录文，
按叶对齐插入原书叶图；无录文存世段以「原叶整版」块呈现并诚实标注）。
单一来源：录文 zw_full_data.json、叶对齐 /tmp/zwalign_out.json（与 B 版 PDF 同源）；
第一章页面与样式直接复用 build_zwds_epub.py 的产物（epub_build/）。
用法：先跑 build_zwds_epub.py，再跑本脚本；epubcheck 验证。"""
import os, re, json, html as htmllib, uuid, datetime, zipfile, shutil, sys
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '紫微斗数全书-整理本.epub')
BUILD = os.path.join(ROOT, 'epub_full_build')
CH1 = os.path.join(ROOT, 'epub_build')          # 第一章定稿产物
SECS = json.load(open(os.path.join(ROOT, 'zw_full_data.json'), encoding='utf-8'))
ALIGN = json.load(open('/tmp/zwalign_out.json', encoding='utf-8'))
STREAM, LEAVES = ALIGN['stream'], ALIGN['leaves']
CAP = 230

# ---------- 录文流 → 篇/段定位（与 align_zwds_full.py 同法重建） ----------
PUNCT = set('，。：；︰！？、（）《》「」『』〔〕…—～·；,.!?():\u3000 \n')
sec_ranges = []          # [(s0, s1)] 每篇的流区间
para_marks = []          # [[每段起始流idx + 末尾哨兵]]
p = 0
for sec in SECS:
    s0 = p
    marks = []
    for para in sec['paras']:
        marks.append(p)
        for ch in para:
            if ch not in PUNCT and '\u4e00' <= ch <= '\u9fff':
                p += 1
    marks.append(p)
    sec_ranges.append((s0, p))
    para_marks.append(marks)
assert p == len(STREAM), (p, len(STREAM))

def sec_of_pos(pos):
    for i, (a, b) in enumerate(sec_ranges):
        if a <= pos < b:
            return i
    return None

def para_of_pos(si, pos):
    ms = para_marks[si]
    for k in range(len(ms) - 1):
        if ms[k] <= pos < ms[k + 1]:
            return k
    return max(0, len(ms) - 2)

# ---------- 叶分类（与 build_zwds_fuke_full.py 同规则，保持两版一致） ----------
hits = [i for i, l in enumerate(LEAVES) if l['kind'] == 'text']
for j, i in enumerate(hits):
    l = LEAVES[i]
    if 'end' not in l:
        continue
    n = l['end'] - l['start']
    if n > CAP or (n < 40 and j < len(hits) - 1):
        l['kind'] = 'other'
        l['demoted'] = True
taiwei_i = next(i for i, s in enumerate(SECS) if s['title'] == '太微賦')
TW0, TW1 = sec_ranges[taiwei_i]

# ---------- 图像（740px embed → 560px q62，控制成品体积） ----------
shutil.rmtree(BUILD, ignore_errors=True)
IMG_DIR = os.path.join(BUILD, 'OEBPS', 'images')
os.makedirs(IMG_DIR, exist_ok=True)
def embed_half(name):
    for sub in ('full_embed', 'full'):
        src = os.path.join(ROOT, 'assets', sub, name + '.jpg')
        if os.path.exists(src):
            break
    else:
        return None
    dst = os.path.join(IMG_DIR, name + '.jpg')
    if not os.path.exists(dst):
        im = Image.open(src).convert('RGB')
        if im.width > 560:
            im = im.resize((560, int(im.height * 560 / im.width)), Image.LANCZOS)
        im.save(dst, 'JPEG', quality=62, optimize=True, progressive=True)
    return name + '.jpg'

# ---------- 单元序列：text 叶 → 图块；连续非 text → 整版仿页块 ----------
units = []               # {'kind':'leaf'/'fax', 'leaves':[...], 'anchor':流idx or ('after', gi)}
gi = 0                   # 前一 text 叶在 LEAVES 中的下标
run = []
def flush_run(prev_leaf_idx):
    global run
    if not run:
        return
    anchor = LEAVES[prev_leaf_idx]['end'] if prev_leaf_idx is not None else None
    units.append({'kind': 'fax', 'leaves': run, 'anchor': anchor})
    run = []
last_text = None
for i, l in enumerate(LEAVES):
    if l['kind'] == 'text':
        flush_run(last_text)
        units.append({'kind': 'leaf', 'leaves': [l], 'anchor': l['start']})
        last_text = i
    else:
        run.append(l)
flush_run(last_text)

# 单元 → (sec, para) 落点
def locate(anchor):
    if anchor is None:
        return (None, None)
    si = sec_of_pos(anchor)
    if si is None:
        for k, (a, b) in enumerate(sec_ranges):
            if anchor >= b:
                si = k
        if si is None:
            return (None, None)
        return (si, max(0, len(para_marks[si]) - 2))
    return (si, para_of_pos(si, anchor))

placements = {}          # sec -> [(para_idx, order, unit)]
tail_units = []
for u in units:
    si, pi = locate(u['anchor'])
    if si is None:
        # 卷首之前或全空：罗序兜底
        si, pi = 1, 0
    if TW0 <= (u['anchor'] or 0) < TW1:
        continue         # 第一章样章自有版式
    placements.setdefault(si, []).append((pi, len(placements.get(si, [])), u))

# ---------- XHTML 生成 ----------
CSS = open(os.path.join(CH1, 'OEBPS', 'styles', 'epub.css'), encoding='utf-8').read()
CSS += """
h2.sect{ font-size:1.2em; letter-spacing:.35em; color:#2C2824; margin:2.2em 0 .8em;
         border-bottom:2px solid #9E2F23; padding-bottom:.25em; font-weight:600; }
h3.subs{ font-size:1.02em; letter-spacing:.2em; color:#4E4738; margin:1.6em 0 .5em; font-weight:600; }
.juan-h{ text-align:center; letter-spacing:.5em; color:#9E2F23; font-size:1.5em; margin:1.6em 0 1.2em; }
.faxim{ margin:1.4em 0; clear:both; border-top:1px dashed #C9B98A; border-bottom:1px dashed #C9B98A;
        padding:.8em 0; }
.faxim p.lbl{ font-size:.82em; color:#9E2F23; letter-spacing:.2em; margin:0 0 .6em; text-indent:0; font-weight:bold; }
.faxim figure{ display:inline-block; width:9.6em; margin:0 .7em .7em 0; text-align:center; vertical-align:top; }
.faxim figure img{ max-width:100%; border:1px solid #C9B98A; background:#fff; }
.faxim figcaption{ font-size:.68em; color:#8A8069; margin-top:.3em; text-indent:0; line-height:1.5; }
.xref{ text-align:center; margin:1.4em 0; text-indent:0; }
.xref a{ color:#9E2F23; }
"""

def esc(s): return s

def page(title, body_, lang='zh-Hans'):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="{lang}" lang="{lang}">\n'
            '<head><meta charset="utf-8"/><title>' + title + '</title>\n'
            '<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>\n'
            f'<body>\n' + '\n'.join(body_) + '\n</body></html>')

def fig_block(l):
    name = embed_half(l['name'])
    if not name:
        return ''
    cap = l['name'].replace('_', ' ')
    pre = htmllib.escape((l.get('anchor') or '')[:12])
    return ('<div class="pair"><figure><img src="../images/' + name + '" alt="' + cap + '"/>'
            '<figcaption><b>原書葉　' + cap + '</b>　起首【' + pre + '…】</figcaption></figure><div class="txt"></div></div>')

def fax_block(ls):
    parts = ['<div class="faxim"><p class="lbl">原葉整版・無録文存世（圖表／命例／版題，原貌呈現）</p>']
    for l in ls:
        name = embed_half(l['name'])
        if not name:
            continue
        parts.append('<figure><img src="../images/' + name + '" alt="' + l['name'] + '"/>'
                     '<figcaption>' + l['name'].replace('_', ' ') + '</figcaption></figure>')
    parts.append('</div>')
    return ''.join(parts)

VOL_TITLES = {'紫微斗數全書卷一': '卷一', '紫微斗数全书卷二': '卷二', '紫微斗数全书卷三': '卷三'}
vol_secs = {}
for si, s in enumerate(SECS):
    vol_secs.setdefault(s['juan'], []).append(si)

vol_files = {}
for juan, idxs in vol_secs.items():
    vt = VOL_TITLES.get(juan, juan)
    body_ = [f'<p class="chapno">全書整理本</p>', f'<h1 class="juan-h">{juan.replace("紫微斗數全書", "").replace("紫微斗数全书", "").strip()}</h1>']
    for si in idxs:
        s = SECS[si]
        if not s['paras']:
            continue
        if s['title'] == '太微賦':
            body_.append('<h2 class="sect" id="s%d">太微賦（含例曰）</h2>' % si)
            body_.append('<p class="xref">本篇為全書首篇，已另行制作「原葉對読随文笺注」专章 → '
                         '<a href="chap01.xhtml">第一章 · 太微賦（原叶对读 · 白话 · 笺释）</a></p>')
            continue
        anchor_id = f'id="s{si}"'
        if s['level'] == 3:
            body_.append(f'<h2 class="sect" {anchor_id}>{htmllib.escape(s["title"])}</h2>')
        else:
            body_.append(f'<h3 class="subs" {anchor_id}>{htmllib.escape(s["title"])}</h3>')
        plist = s['paras']
        puts = sorted(placements.get(si, []), key=lambda x: (x[0], x[1]))
        pi_set = {k for k, _, _ in puts}
        cur = 0
        emitted = set()
        for k, para in enumerate(plist):
            for (pk, _, u) in puts:
                if pk == k and id(u) not in emitted:
                    body_.append(fig_block(u['leaves'][0]) if u['kind'] == 'leaf' else fax_block(u['leaves']))
                    emitted.add(id(u))
            body_.append('<p>' + htmllib.escape(para) + '</p>')
        for (pk, _, u) in puts:
            if id(u) not in emitted:
                body_.append(fig_block(u['leaves'][0]) if u['kind'] == 'leaf' else fax_block(u['leaves']))
    fname = {'卷一': 'vol1', '卷二': 'vol2', '卷三': 'vol3'}.get(vt, 'volx') + '.xhtml'
    vol_files[vt] = (fname, page(f'{juan}', body_))

# ---------- 封面 / 编例 ----------
os.makedirs(os.path.join(BUILD, 'OEBPS', 'text'), exist_ok=True)
os.makedirs(os.path.join(BUILD, 'OEBPS', 'styles'), exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

n_text = sum(1 for l in LEAVES if l['kind'] == 'text')
n_dem = sum(1 for l in LEAVES if l.get('demoted'))
n_other = sum(1 for l in LEAVES if l['kind'] in ('other', 'title'))
cover = page('封面',
    ['<figure style="margin-top:12%"><img src="../images/zw_cover_shiying.jpg" alt="卷端书影"/>'
     '<figcaption style="text-align:center">卷端書影（南陽堂刊本 · 日本公文書館藏）</figcaption></figure>',
     '<p class="noindent" style="text-align:center;margin-top:1.5em">'
     '<span style="font-size:2.4em;letter-spacing:.4em;font-weight:600">紫微斗數全書</span></p>',
     '<p class="noindent" style="text-align:center;letter-spacing:.4em;color:#8A8069">整理本 · 全書三卷</p>',
     '<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em;margin-top:1.5em">'
     '舊題陳摶撰 · 潘希尹補輯 · 明刊本系統</p>'])

bianli_items = [
    '本书为《新锓希夷陈先生紫微斗数全书》南阳堂刊本（日本国立公文书馆藏）之整理本。录文以维基文库通行本为底，'
    '全书三卷 93 篇、约 5.4 万字，与原刊 532 个半叶逐叶锚点对齐；正文用繁体，编例、说明用简体。',
    f'版式：各篇按录文顺序排读；<b>原书叶图</b>按其起始位置随文插入（朱框小图，题注标明叶号与起首数字），'
    '读至此可见该叶原貌。第一章《太微赋》另设专章，逐叶对读并附白话通释与术语笺释。',
    f'全书对齐情况：逐叶匹配成文 {n_text} 叶；另有 {n_dem} 叶因原书夹注混排、一图跨段等原因不做强行拆配。',
    '<b>无录文存世段（安星图、表格、批命活套、命例等约 200 半叶）以「原叶整版」块呈现</b>：虚线框内为原书叶'
    '影像并如实标注，不代拟文字——此为底本实存而传世录文阙如者，整理原则为宁缺毋伪。',
    '凡例、编例等现代说明文字为简体；经文、序跋、赋诀为繁体；同一句内不繁简并见。',
]
bianli = page('编例', ['<h1 class="doctitle">編例</h1>',
                       '<p class="subtitle">整理原则与阅读方法</p>']
              + ['<p class="noindent">' + it + '</p>' for it in bianli_items])

# ---------- 打包 ----------
os.makedirs(os.path.join(BUILD, 'META-INF'), exist_ok=True)
open(os.path.join(BUILD, 'mimetype'), 'w').write('application/epub+zip')
open(os.path.join(BUILD, 'META-INF', 'container.xml'), 'w').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles>\n</container>')
open(os.path.join(BUILD, 'OEBPS', 'styles', 'epub.css'), 'w').write(CSS)
open(os.path.join(BUILD, 'OEBPS', 'text', 'cover.xhtml'), 'w').write(cover)
open(os.path.join(BUILD, 'OEBPS', 'text', 'bianli.xhtml'), 'w').write(bianli)
for vt, (fname, content) in vol_files.items():
    open(os.path.join(BUILD, 'OEBPS', 'text', fname), 'w').write(content)
# 第一章定稿页 + 其图像
shutil.copy(os.path.join(CH1, 'OEBPS', 'text', 'chap01.xhtml'),
            os.path.join(BUILD, 'OEBPS', 'text', 'chap01.xhtml'))
for im in ('zw_cover_shiying.jpg', 'zw_leaf2.jpg', 'zw_leaf4.jpg', 'zw_leaf5.jpg',
           'zw_leaf6.jpg', 'zw_leaf7.jpg'):
    shutil.copy(os.path.join(CH1, 'OEBPS', 'images', im), os.path.join(IMG_DIR, im))

items = [('nav', 'nav.xhtml', 'application/xhtml+xml', 'nav'),
         ('ncx', 'toc.ncx', 'application/x-dtbncx+xml', None),
         ('css', 'styles/epub.css', 'text/css', None),
         ('c01', 'text/cover.xhtml', 'application/xhtml+xml', None),
         ('c02', 'text/bianli.xhtml', 'application/xhtml+xml', None),
         ('c03', 'text/chap01.xhtml', 'application/xhtml+xml', None)]
spine = ['c01', 'c02', 'c03']
n = 3
toc_lis = ['<li><a href="text/cover.xhtml">封面</a></li>',
           '<li><a href="text/bianli.xhtml">编例</a></li>',
           '<li><a href="text/chap01.xhtml">第一章 · 太微賦（原叶对读 · 随文笺注）</a></li>']
for key in ('卷一', '卷二', '卷三'):
    fname = vol_files[key][0]
    n += 1
    iid = f'c{n:02d}'
    items.append((iid, 'text/' + fname, 'application/xhtml+xml', None))
    spine.append(iid)
    subs = []
    for si in vol_secs[[k for k in vol_secs if VOL_TITLES.get(k) == key][0]]:
        s = SECS[si]
        if s['paras'] and s['level'] == 3:
            subs.append(f'<li><a href="text/{fname}#s{si}">{htmllib.escape(s["title"])}</a></li>')
        elif s['paras'] and s['level'] == 4 and key == '卷一' and '問' in s['title']:
            subs.append(f'<li><a href="text/{fname}#s{si}">{htmllib.escape(s["title"])}</a></li>')
    toc_lis.append(f'<li><a href="text/{fname}">{key}</a><ol>' + '\n'.join(subs) + '</ol></li>')

img_names = sorted(os.listdir(IMG_DIR))
img_items = '\n'.join(f'<item id="im{i}" href="images/{nm}" media-type="image/jpeg"/>'
                      for i, nm in enumerate(img_names))
items_xml = '\n'.join(
    f'<item id="{i}" href="{h}" media-type="{m}"' + (f' properties="{p}"/>' if p else '/>')
    for i, h, m, p in items)
book_uuid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
OPF = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-Hans">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>紫微斗數全書（整理本 · 南陽堂刊本對讀）</dc:title>
    <dc:creator>陳摶（舊題）· 潘希尹補輯 · 整理版</dc:creator>
    <dc:language>zh-Hans</dc:language>
    <dc:source>南陽堂刊本（明代 · 日本公文書館藏）· 維基文庫通行錄文</dc:source>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    {items_xml}
    {img_items}
  </manifest>
  <spine toc="ncx">
""" + '\n'.join(f'    <itemref idref="{s}"/>' for s in spine) + """
  </spine>
</package>"""

ncx_pts = []
for k, (iid, title) in enumerate([('c01', '封面'), ('c02', '编例'), ('c03', '第一章 · 太微賦')], 1):
    href = {'c01': 'cover', 'c02': 'bianli', 'c03': 'chap01'}[iid]
    ncx_pts.append(f'<navPoint id="n{k}" playOrder="{k}"><navLabel><text>{title}</text></navLabel>'
                   f'<content src="text/{href}.xhtml"/></navPoint>')
for vi, key in enumerate(('卷一', '卷二', '卷三'), 1):
    fname = vol_files[key][0]
    ncx_pts.append(f'<navPoint id="v{vi}" playOrder="{len(ncx_pts)+1}">'
                   f'<navLabel><text>{key}</text></navLabel><content src="text/{fname}"/></navPoint>')
NCX = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:{book_uuid}"/><meta name="dtb:depth" content="1"/></head>
  <docTitle><text>紫微斗數全書（整理本）</text></docTitle>
  <navMap>
""" + '\n'.join(ncx_pts) + """
  </navMap>
</ncx>"""

NAV = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
       '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans">\n'
       '<head><meta charset="utf-8"/><title>目录</title></head><body>\n'
       '<nav epub:type="toc" id="toc"><h1>目錄</h1><ol>\n'
       + '\n'.join(toc_lis) +
       '\n</ol></nav>\n'
       '<nav epub:type="landmarks" hidden="hidden"><ol>\n'
       '<li><a epub:type="cover" href="text/cover.xhtml">封面</a></li>\n'
       '<li><a epub:type="bodymatter" href="text/chap01.xhtml">正文</a></li>\n'
       '</ol></nav>\n</body></html>')

open(os.path.join(BUILD, 'OEBPS', 'content.opf'), 'w').write(OPF)
open(os.path.join(BUILD, 'OEBPS', 'nav.xhtml'), 'w').write(NAV)
open(os.path.join(BUILD, 'OEBPS', 'toc.ncx'), 'w').write(NCX)

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, 'w') as z:
    z.write(os.path.join(BUILD, 'mimetype'), 'mimetype', compress_type=zipfile.ZIP_STORED)
    for base, _, files in os.walk(BUILD):
        for f in files:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, BUILD)
            if rel == 'mimetype':
                continue
            z.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)

# ---------- 完整性核对：每篇带标点录文必须原文见于卷页 ----------
missing = []
for juan, (fname, content) in [(k, v) for k, v in vol_files.items()]:
    pass
vol_content = {vt: content for vt, (fname, content) in vol_files.items()}
for si, s in enumerate(SECS):
    if not s['paras'] or s['title'] == '太微賦':
        continue
    vt = VOL_TITLES[s['juan']]
    for para in s['paras']:
        if htmllib.escape(para) not in vol_content[vt]:
            missing.append((s['title'], para[:15]))
chap01 = open(os.path.join(BUILD, 'OEBPS', 'text', 'chap01.xhtml'), encoding='utf-8').read()
# 太微赋区以第一章定稿数据为准：正字归一（鬥→斗 佈→布 兇→凶 鉅→巨）后核对；
# 「例曰」二字在第一章独立为篇题标签，不计入 fu 录文
VARIANTS = str.maketrans('鬥佈兇鉅', '斗布凶巨')
tw_norm = ''.join(SECS[taiwei_i]['paras']).translate(VARIANTS)
n_secs_tw = sum(1 for c in tw_norm if c not in PUNCT and '\u4e00' <= c <= '\u9fff') - 2
fu_text = ''.join(re.findall(r'<p class="fu">(.*?)</p>', chap01))
fu_text = re.sub(r'<[^>]+>', '', fu_text)
n_ch1_tw = sum(1 for c in htmllib.unescape(fu_text) if '\u4e00' <= c <= '\u9fff')
print('EPUB:', OUT, os.path.getsize(OUT) // 1024, 'KB |', len(img_names) + 6, 'imgs')
print('missing paras:', len(missing), missing[:5])
print('太微赋区: 全書流(归一)', n_secs_tw, 'vs 第一章录文', n_ch1_tw)
assert n_secs_tw == n_ch1_tw, (n_secs_tw, n_ch1_tw)
assert not missing
print('units:', sum(len(v) for v in placements.values()),
      '| text叶:', n_text, '| demoted:', n_dem, '| other+title:', n_other)

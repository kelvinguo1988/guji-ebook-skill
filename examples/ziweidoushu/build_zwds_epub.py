#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗数全书》第一章（太微赋）EPUB 3 — 重排版 v2
设计（用户定稿）：每个复刻叶一个对读区块——左半=对应原书叶图，右半=该叶原文；
白话通释逐句、术语笺释逐卡按锚点融入所属叶区块的「随文笺注」，不再独立成节。
单一来源：录文取 zw_ch1_data.json（与 A/B 两版同源），辅以 zwds_sample.html 提取凡例/通释/笺释。
用法：先跑 build_zwds_sample.py 生成 HTML，再跑本脚本；epubcheck 验证。"""
import os, re, json, html as htmllib, uuid, datetime, zipfile
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '紫微斗数全书-第一章-太微赋.epub')
BUILD = os.path.join(ROOT, 'epub_build')

src_html = open(os.path.join(ROOT, 'zwds_sample.html'), encoding='utf-8').read()

def sec(cls):
    m = re.search(r'<section class="%s[^"]*">(.*?)</section>' % cls, src_html, re.S)
    return m.group(1) if m else ''

fanli_items = re.findall(r'<li>(.*?)</li>', sec('fanli'), re.S)
assert len(fanli_items) == 6, len(fanli_items)
gist = re.search(r'<div class="ch-gist">(.*?)</div>', src_html, re.S).group(1)
baihua = re.findall(r'<p>(.*?)</p>',
                    re.search(r'<div class="baihua">(.*?)</div>', src_html, re.S).group(1), re.S)
kwcards = re.findall(r'<div class="kwcard"><span class="kt">(.*?)</span><p>(.*?)</p></div>',
                     src_html, re.S)
assert len(baihua) == 2 and len(kwcards) == 6, (len(baihua), len(kwcards))

# ---------- 录文与叶切分（与 build_zwds_fuke.py 完全同源） ----------
DATA = json.load(open(os.path.join(ROOT, 'zw_ch1_data.json'), encoding='utf-8'))
taiwei_lines, li_lines = DATA['taiwei'], DATA['li']
fu_main_html = re.findall(r'<p class="fu">(.*?)</p>',
    src_html[src_html.index('太微赋</h2>'):src_html.index('例曰</h3>')], re.S)
fu_li_html = re.findall(r'<p class="fu">(.*?)</p>',
    src_html[src_html.index('例曰</h3>'):src_html.index('白话通释</h3>')], re.S)
assert [htmllib.unescape(x) for x in fu_main_html] == taiwei_lines
assert [htmllib.unescape(x) for x in fu_li_html] == li_lines

PUNCT = set('，。：；！？、「」『』（）〔〕')
body = ''.join(c for c in ''.join(taiwei_lines + li_lines) if c not in PUNCT)
STARTS = [0, 115, 345, 575, 805]          # 复刻引擎实测叶边界（卷端起 5 列×23 行 + 每叶 10 列）
assert len(body) == 835

def leaf_of_gi(gi):
    for i in range(4, -1, -1):
        if gi >= STARTS[i]:
            return i
    return 0

def leaf_of(anchor):
    pos = body.find(anchor)
    assert pos >= 0, '锚点未命中: ' + anchor
    return leaf_of_gi(pos)

# 逐行切块：punct 归属前字；跨界即 flush 并换叶
frags = [[] for _ in range(5)]            # [(text, is_li_start)]
gi = leaf = 0
cur, pend = '', ''
for li_idx, line in enumerate(taiwei_lines + li_lines):
    is_li_start = (li_idx == len(taiwei_lines))
    for c in line:
        if c in PUNCT:
            pend += c
            continue
        if leaf < 4 and gi >= STARTS[leaf + 1]:
            frags[leaf].append((cur + pend, is_li_start))
            cur, pend = '', ''
            leaf += 1
            is_li_start = False
        cur += c
        pend = ''
        gi += 1
    frags[leaf].append((cur + pend, is_li_start))
    cur, pend = '', ''
    is_li_start = False
assert gi == len(body)
assert sum(len(f) for f in frags) >= 5

# ---------- 注解融入：白话逐句锚点 + 术语逐卡锚点 ----------
def split_sents(p):
    p = re.sub(r'^【.*?】', '', p)
    parts = re.split(r'(?<=[。；])', p)
    return [x for x in parts if x.strip()]

bai1 = split_sents(htmllib.unescape(baihua[0]))
bai2_raw = htmllib.unescape(baihua[1]).replace('，以及太阳居午', '；又如太阳居午')
bai2 = split_sents(bai2_raw)
# 锚点 = 该句所释正文短语（繁体，用于在录文中定位所属叶）
ANCH_BAI = ['至玄至微', '分野', '十二垣', '以身命', '紫微', '帝星動',            # 太微赋正文通释 6 句
            '祿逢沖破', '星臨廟旺', '日月', '七殺破軍', '君臣慶會', '日麗中天']    # 例曰通释 6 句
assert len(bai1) + len(bai2) == len(ANCH_BAI), (len(bai1), len(bai2))
leaf_bai = [[] for _ in range(5)]
for s, a in zip(bai1 + bai2, ANCH_BAI):
    leaf_bai[leaf_of(a)].append(s.strip())

ANCH_KW = {'十二垣': '十二垣', '入庙 / 失度': '失度', '空亡': '空亡',
           '帝星': '帝星', '羊陀火铃': '羊鈴', '马头带剑': '馬頭帶劍'}
leaf_kw = [[] for _ in range(5)]
for kt, kv in kwcards:
    kt_u, kv_u = htmllib.unescape(kt), htmllib.unescape(kv)
    leaf_kw[leaf_of(ANCH_KW[kt_u])].append((kt_u, kv_u))

# ---------- 图片降采样 ----------
LEAF_IMG = [('zw_leaf2.jpg', '原書葉　卷端大題與太微賦起首'),
            ('zw_leaf5.jpg', '原書葉　太微賦續與例曰起首'),
            ('zw_leaf4.jpg', '原書葉　太微賦例曰諸格'),
            ('zw_leaf6.jpg', '原書葉　例曰諸格續　蟾宮折桂之條'),
            ('zw_leaf7.jpg', '原書葉　例曰篇末　次接形性賦')]
CN = ['一', '二', '三', '四', '五']
os.makedirs(os.path.join(BUILD, 'OEBPS', 'images'), exist_ok=True)
IMGS = ['zw_cover_shiying.jpg'] + [f for f, _ in LEAF_IMG]
for name in IMGS:
    im = Image.open(os.path.join(ROOT, 'assets', name)).convert('RGB')
    if im.width > 900:
        im = im.resize((900, int(im.height * 900 / im.width)), Image.LANCZOS)
    im.save(os.path.join(BUILD, 'OEBPS', 'images', name), 'JPEG', quality=82)

# ---------- XHTML ----------
CSS = """/* 重排版样式：相对单位，阅读器自适应；简繁分工见凡例 */
body{ font-family: serif; line-height: 1.95; margin: 0 6%; color: #2C2824; background: #FDFBF4; }
h1.doctitle{ text-align:center; letter-spacing:.35em; font-weight:600; margin:1.2em 0 .4em; font-size:1.7em; }
.subtitle{ text-align:center; color:#8A8069; letter-spacing:.28em; margin:0 0 2.4em; font-size:.95em; }
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
/* 左图右文对读区块：float 环绕（不用 flex——flex 区块高于视口时会被分页阅读器整块裁断）
   图限高 ≤20em，保证任何阅读器单页完整显示 */
.pair{ margin:1em 0 1.6em; }
.pair::after{ content:""; display:table; clear:both; }
.pair figure{ float:left; width:36%; max-width:10.5em; margin:0 1em .6em 0; text-align:center; }
.pair figure img{ max-width:100%; max-height:20em; width:auto; height:auto;
                  border:1px solid #C9B98A; padding:2%; background:#fff; }
.pair figcaption{ font-size:.72em; color:#8A8069; margin-top:.4em; text-align:center; text-indent:0; line-height:1.6; }
.pair figcaption b{ color:#2C2824; }
.pair .txt{ min-width:0; }
.ann{ background:#FBF6E8; border-top:1px solid #C9B98A; border-bottom:1px solid #C9B98A;
      padding:.7em 1em; margin:1.2em 0; clear:both; }
@media (max-width: 30em){
  .pair figure{ float:none; display:block; max-width:12em; margin:0 auto 1em; }
}
.fu{ font-size:1.08em; line-height:2.1; letter-spacing:.05em; text-indent:0; margin:.45em 0; }
.lit{ font-size:.85em; color:#9E2F23; letter-spacing:.35em; margin:1.4em 0 .3em; text-indent:0; font-weight:bold; }
.ann p.lbl{ font-size:.8em; color:#9E2F23; letter-spacing:.25em; margin:0 0 .3em; text-indent:0; font-weight:bold; }
.ann p{ font-size:.88em; color:#4E4738; text-indent:0; margin:.45em 0; }
.ann p.kw .kt{ font-weight:bold; color:#9E2F23; letter-spacing:.08em; }
.lsrc{ display:block; color:#8A8069; }
.note{ font-size:.85em; color:#8A8069; text-indent:0; }
.colophon{ margin-top:3em; padding-top:1.5em; border-top:1px solid #C9B98A; color:#8A8069;
           font-size:.85em; text-align:center; text-indent:0; }
"""

def page(title, body_):
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            'xml:lang="zh-Hans" lang="zh-Hans">\n'
            f'<head><meta charset="utf-8"/><title>{title}</title>\n'
            '<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>\n'
            f'<body>\n{body_}\n</body></html>')

cover = page('封面',
    '<figure style="margin-top:12%"><img src="../images/zw_cover_shiying.jpg" alt="卷端书影"/>'
    '<figcaption style="text-align:center">卷端書影（南陽堂刊本 · 日本公文書館藏）</figcaption></figure>'
    '<p class="noindent" style="text-align:center;margin-top:1.5em">'
    '<span style="font-size:2.4em;letter-spacing:.4em;font-weight:600">紫微斗數全書</span></p>'
    '<p class="noindent" style="text-align:center;letter-spacing:.4em;color:#8A8069">整理版 · 原書葉對照</p>'
    '<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em;margin-top:1.5em">'
    '舊題陳摶撰 · 潘希尹補輯 · 明刊本系統</p>')

fanli = page('凡例', '<h1 class="doctitle">凡例</h1>\n<p class="subtitle">如何使用这本电子书</p>\n'
             + '\n'.join('<p class="noindent">' + it.strip() + '</p>' for it in fanli_items))

chap = ['<p class="chapno">卷首 · 第一章</p>',
        '<h1 class="doctitle">太微賦</h1>',
        '<p class="subtitle">全书赋诀之祖 · 含「例曰」 · 原叶对读本</p>',
        f'<p class="gist">{gist.strip()}</p>',
        '<h2 class="sec" id="spair">原叶对读 · 随文笺注</h2>',
        '<p class="note">每区块左为南阳堂刊本原书叶、右为该叶对应录文；白话通释与术语笺释随叶融入，读一叶得一叶之解。</p>']
for i in range(5):
    img, cap = LEAF_IMG[i]
    tail = ('<span class="lsrc">叶图来源：南阳堂刊本（明代 · 日本公文书馆藏 · 书格数字化），'
            '全册统一，各叶不再重注。</span>') if i == 4 else ''
    chap.append(f'<h3 class="leaf-h" id="lf{i+1}">第{CN[i]}叶'
                f'<small>录文第 {STARTS[i]+1}–{(STARTS[i+1] if i<4 else len(body))} 字</small></h3>')
    chap.append('<div class="pair">')
    chap.append(f'<figure><img src="../images/{img}" alt="{cap}"/>'
                f'<figcaption><b>{cap.split("　")[0]}</b>　{cap.split("　",1)[1]}{tail}</figcaption></figure>')
    chap.append('<div class="txt">')
    # 同叶碎块并入连续段（跨叶断句处自然衔接），例曰起首单独标注
    pairs = [(x.strip(), f) for x, f in frags[i] if x.strip()]
    li_pos = next((j for j, (_, f) in enumerate(pairs) if f), None)
    merged = [x for x, _ in pairs]
    if li_pos is not None and li_pos > 0:
        head, li_body = ''.join(merged[:li_pos]), ''.join(merged[li_pos:])
        chap.append(f'<p class="fu">{head}</p><p class="lit">例曰</p>')
        merged = [li_body]
    elif li_pos == 0:
        chap.append('<p class="lit">例曰</p>')
        merged = [''.join(merged)]
    else:
        merged = [''.join(merged)]
    for text in merged:
        chap.append(f'<p class="fu">{text}</p>')
    if leaf_bai[i] or leaf_kw[i]:
        chap.append('<div class="ann">')
        if leaf_bai[i]:
            chap.append('<p class="lbl">白话通释</p>')
            chap += ['<p>' + s + '</p>' for s in leaf_bai[i]]
        if leaf_kw[i]:
            chap.append('<p class="lbl">术语笺释</p>')
            chap += [f'<p class="kw"><span class="kt">{k}</span>　{v}</p>' for k, v in leaf_kw[i]]
        chap.append('</div>')
    chap.append('</div></div>')
chap.append('<p class="colophon">紫微斗数全书 · 第一章样章（太微赋）· 原叶对读 v2<br/>'
            '编纂参考：南阳堂刊本（日本公文书馆藏）· 维基文库通行录文 · 识典古籍 SDZJ0170</p>')
chap01 = page('第一章 · 太微赋', '\n'.join(chap))

NAV = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
       '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans">\n'
       '<head><meta charset="utf-8"/><title>目录</title></head><body>\n'
       '<nav epub:type="toc" id="toc"><h1>目錄</h1><ol>\n'
       '<li><a href="text/cover.xhtml">封面</a></li>\n'
       '<li><a href="text/fanli.xhtml">凡例</a></li>\n'
       '<li><a href="text/chap01.xhtml">第一章 · 太微賦</a><ol>\n'
       + '\n'.join(f'<li><a href="text/chap01.xhtml#lf{i+1}">第{CN[i]}叶 · 原叶对读</a></li>' for i in range(5))
       + '\n</ol></li></ol></nav>\n'
       '<nav epub:type="landmarks" hidden="hidden"><ol>\n'
       '<li><a epub:type="cover" href="text/cover.xhtml">封面</a></li>\n'
       '<li><a epub:type="bodymatter" href="text/chap01.xhtml">正文</a></li>\n'
       '</ol></nav>\n</body></html>')

book_uuid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
img_items = '\n'.join(f'<item id="im{i}" href="images/{n}" media-type="image/jpeg"/>'
                      for i, n in enumerate(IMGS))
OPF = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-Hans">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>紫微斗數全書（第一章樣章 · 太微賦 · 原葉對讀本）</dc:title>
    <dc:creator>陳摶（舊題）· 潘希尹補輯 · 整理版</dc:creator>
    <dc:language>zh-Hans</dc:language>
    <dc:source>南陽堂刊本（明代 · 日本公文書館藏）· 維基文庫通行錄文</dc:source>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="styles/epub.css" media-type="text/css"/>
    <item id="c01" href="text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="c02" href="text/fanli.xhtml" media-type="application/xhtml+xml"/>
    <item id="c03" href="text/chap01.xhtml" media-type="application/xhtml+xml"/>
    {img_items}
  </manifest>
  <spine toc="ncx">
    <itemref idref="c01"/>
    <itemref idref="c02"/>
    <itemref idref="c03"/>
  </spine>
</package>"""

NCX = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:{book_uuid}"/><meta name="dtb:depth" content="1"/></head>
  <docTitle><text>紫微斗數全書（第一章樣章）</text></docTitle>
  <navMap>
    <navPoint id="n1" playOrder="1"><navLabel><text>封面</text></navLabel><content src="text/cover.xhtml"/></navPoint>
    <navPoint id="n2" playOrder="2"><navLabel><text>凡例</text></navLabel><content src="text/fanli.xhtml"/></navPoint>
    <navPoint id="n3" playOrder="3"><navLabel><text>第一章 · 太微賦</text></navLabel><content src="text/chap01.xhtml"/></navPoint>
  </navMap>
</ncx>"""

os.makedirs(os.path.join(BUILD, 'OEBPS', 'text'), exist_ok=True)
os.makedirs(os.path.join(BUILD, 'OEBPS', 'styles'), exist_ok=True)
os.makedirs(os.path.join(BUILD, 'META-INF'), exist_ok=True)
open(os.path.join(BUILD, 'mimetype'), 'w').write('application/epub+zip')
open(os.path.join(BUILD, 'META-INF', 'container.xml'), 'w').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
    '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles>\n</container>')
open(os.path.join(BUILD, 'OEBPS', 'content.opf'), 'w').write(OPF)
open(os.path.join(BUILD, 'OEBPS', 'nav.xhtml'), 'w').write(NAV)
open(os.path.join(BUILD, 'OEBPS', 'toc.ncx'), 'w').write(NCX)
open(os.path.join(BUILD, 'OEBPS', 'styles', 'epub.css'), 'w').write(CSS)
open(os.path.join(BUILD, 'OEBPS', 'text', 'cover.xhtml'), 'w').write(cover)
open(os.path.join(BUILD, 'OEBPS', 'text', 'fanli.xhtml'), 'w').write(fanli)
open(os.path.join(BUILD, 'OEBPS', 'text', 'chap01.xhtml'), 'w').write(chap01)

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

# 完整性核对：录文全数入卷（去标点汉字总数一致）
out_text = re.sub(r'<[^>]+>', '', chap01)
n_cjk_src = sum(1 for c in body if '\u4e00' <= c <= '\u9fff')
n_cjk_out = sum(1 for c in ''.join(t for t, _ in sum(frags, [])) if '\u4e00' <= c <= '\u9fff')
assert n_cjk_src == n_cjk_out, (n_cjk_src, n_cjk_out)
print('EPUB written:', OUT, os.path.getsize(OUT) // 1024, 'KB',
      '| 五叶区块字数:', [sum(len(t) for t, _ in f) for f in frags],
      '| 笺注分布 bai:', [len(x) for x in leaf_bai], 'kw:', [len(x) for x in leaf_kw])

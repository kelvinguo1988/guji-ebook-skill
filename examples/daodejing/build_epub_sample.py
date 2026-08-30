#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《道德經三版本對照箋注》第一章樣張 — EPUB 3 打包
单一来源：直接从 book.html 提取内容生成重排版 EPUB。
"""
import os, re, zipfile, uuid, datetime
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "道德经三版本对照笺注-第一章样张.epub")
IMG_SRC = os.path.join(ROOT, "assets")
BUILD = os.path.join(ROOT, "epub_build")

# ---------- 图片降采样 ----------
os.makedirs(os.path.join(BUILD, "OEBPS", "images"), exist_ok=True)
imgs = {}
for name, target_w in [("wb_guyi.png", 1200), ("hsg_leaf.png", 900),
                        ("st_ch1.png", 900), ("bo_jia.png", 900), ("bo_yi.png", 900)]:
    im = Image.open(os.path.join(IMG_SRC, name)).convert("RGB")
    w, h = im.size
    if w > target_w:
        im = im.resize((target_w, int(h * target_w / w)), Image.LANCZOS)
    out = os.path.join(BUILD, "OEBPS", "images", name.replace(".png", ".jpg"))
    im.save(out, "JPEG", quality=82)
    imgs[name] = os.path.basename(out)

# ---------- 从 book.html 提取内容 ----------
html = open(os.path.join(ROOT, "book.html"), encoding="utf-8").read()
sections = re.findall(r'<section class="page[^"]*">(.*?)</section>', html, re.S)
assert len(sections) == 12, f"expect 12 sections, got {len(sections)}"

def clean(s):
    s = re.sub(r'<div class="folio"[^>]*>.*?</div>', '', s, flags=re.S)
    s = re.sub(r'<div class="rh">.*?</div>', '', s, flags=re.S)
    s = re.sub(r'<div class="frame"></div>', '', s)
    return s.strip()

p3, p4, p5, p6, p7, p8, p9, p10, p11, p12 = [clean(x) for x in sections[2:12]]

# 凡例（简体；li 转为 p，重排版无需 ul 结构）
fanli_body = re.sub(r'^.*?<ul class="fali"[^>]*>', '', p3, flags=re.S).replace('</ul>', '')
fanli_body = re.sub(r'<span class="no">([一二三四五六])</span>', r'<b>\1、</b>', fanli_body)
fanli_body = re.sub(r'<li[^>]*>', '<p>', fanli_body).replace('</li>', '</p>')

# 第一章
chap = []
chap.append('<p class="chapno">第一章</p>')
chap.append('<h1 class="doctitle">道可道，非常道</h1>')
chap.append('<p class="subtitle">五千言之门径</p>')
chap.append('<figure><img src="../images/st_ch1.jpg" alt="石涛楷书道德经上篇首"/><figcaption><b>石濤楷書《道德經》冊 · 上篇首</b>（台北故宫博物院藏）</figcaption></figure>')
chap.append(re.search(r'<div class="ch-lead">(.*?)</div>\s*<div class="ch-gist">', p4, re.S).group(1))
chap.append('<p class="note">' + re.search(r'<div class="ch-gist">(.*?)</div>', p4, re.S).group(1) + '</p>')
chap.append('<h2 class="sec" id="sread">四版本对读</h2>')
vtxts = re.findall(r'<div class="vtxt[^"]*">(.*?)</div>', p5 + p6, re.S)
for n, txt in zip(["王弼本（底本）", "河上公本", "帛书甲本", "帛书乙本"], vtxts):
    chap.append(f'<p class="jing"><span class="vname">{n}</span>{txt.strip()}</p>')
chap.append('<p class="note">〔　〕残缺拟补；（　）通假今字；句读从《長沙馬王堆漢墓簡帛集成》释文。</p>')
chap.append('<h2 class="sec" id="sbook">书影</h2>')
for png, jpg, cap in [
    ("wb_guyi.png", "wb_guyi.jpg", "<b>图一</b>　王弼注《老子道德經》卷上首叶（《古逸叢書》据集唐字本景刊）"),
    ("hsg_leaf.png", "hsg_leaf.jpg", "<b>图二</b>　《音註河上公老子道德經》體道第一（南宋建阳刊本 · 台北故宫博物院藏）"),
    ("bo_jia.png", "bo_jia.jpg", "<b>图三</b>　马王堆帛书《老子》甲本书影（《長沙馬王堆漢墓簡帛集成》图版）"),
    ("bo_yi.png", "bo_yi.jpg", "<b>图四</b>　马王堆帛书《老子》乙本书影（同上）"),
]:
    chap.append(f'<figure><img src="../images/{jpg}" alt=""/><figcaption>{cap}</figcaption></figure>')
chap.append('<p class="note">帛书两本皆〈德〉篇在前、〈道〉篇在后，第一章居全卷之末。图三、图四为两本卷端书影，以见西汉写本形貌。</p>')
chap.append('<h2 class="sec" id="szhu">笺注</h2>')
for e in re.findall(r'<div class="entry">(.*?)</div>', p9, re.S):
    e = re.sub(r'(</span>)\s*<p>', r'\1', e.strip(), count=1)
    e = re.sub(r'</p>\s*$', '', e)
    chap.append('<p class="entry">' + e + '</p>')
chap.append('<h3>古注荐读</h3>')
for q in re.findall(r'<blockquote>(.*?)</blockquote>', p9, re.S):
    chap.append('<blockquote>' + q + '</blockquote>')
chap.append('<h2 class="sec" id="strans">今译</h2>')
chap.append('<p class="jing">' + re.search(r'<div class="body">(.*?)</div>', p10, re.S).group(1).strip() + '</p>')
dayi_p = re.search(r'<div class="dayi">.*?<p>(.*?)</p>', p10, re.S).group(1)
chap.append('<p class="note"><b>大意</b>　' + dayi_p + '</p>')
chap.append('<p class="note">' + re.search(r'<div class="duanju">(.*?)</div>', p10, re.S).group(1) + '</p>')
chap.append('<h2 class="sec" id="sjiao">校勘记</h2>')
chap.append('<table>' + re.search(r'<table class="jiaokan"[^>]*>(.*?)</table>', p11, re.S).group(1) + '</table>')
for item in re.findall(r'<div class="item">(.*?)</div>', p11, re.S):
    inner = re.sub(r'<span class="n">([一二三四])</span>\s*<p>', r'<b>校按\1</b>　', item.strip())
    inner = re.sub(r'</p>\s*$', '', inner)
    chap.append('<p class="xiaoan">' + inner + '</p>')
chap.append('<h2 class="sec">附记 · 版本源流</h2>')
for b, p_ in re.findall(r'<div class="ver-item">\s*<b>(.*?)</b>\s*<p>(.*?)</p>', p12, re.S):
    tag = re.search(r'<i>(.*?)</i>', b).group(1)
    name = re.sub(r'<i>.*?</i>', '', b).strip()
    chap.append(f'<p class="entry"><b>{name}</b>（{tag}）　{p_}</p>')
chap.append('<p class="colophon">道德经三版本对照笺注 · 第一章样张<br/>编纂参考：识典古籍 / 中华古籍智慧化服务平台 / 《長沙馬王堆漢墓簡帛集成》</p>')

chap_body = "\n".join(chap)

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

CSS = """/* 重排版电子书样式：相对单位，阅读系统自适应 */
body{ font-family: serif; line-height: 1.9; margin: 0 5%; color: #2C2824; background: #FDFBF4; }
.chapno{ color:#9E2F23; letter-spacing:.5em; font-size:.95em; margin:2em 0 .3em; }
h1.doctitle{ text-align:center; letter-spacing:.35em; font-weight:600; margin:2.2em 0 .4em; font-size:1.7em;}
.subtitle{ text-align:center; color:#8A8069; letter-spacing:.28em; margin:0 0 2.4em; font-size:.95em;}
h2.sec{ font-size:1.25em; letter-spacing:.4em; color:#9E2F23; margin:2.2em 0 1em;
        border-bottom:1px solid #C9B98A; padding-bottom:.3em; font-weight:600;}
h3{ margin:1.4em 0 .8em; }
p{ text-align:justify; margin:.7em 0; text-indent:2em;}
p.noindent, p.note, p.entry, p.xiaoan{ text-indent:0; }
.jing{ font-size:1.15em; line-height:2.1; letter-spacing:.06em; text-indent:0; margin:1em 0;}
.jing .vname{ display:block; font-size:.72em; color:#9E2F23; letter-spacing:.3em;
              margin:1.4em 0 .2em; border-left:3px solid #9E2F23; padding-left:.6em;}
.lac{ color:#9E2F23; } .loanglyph{ color:#8A8069; } em.fj{ font-style:normal; color:#9E2F23; font-size:.75em;}
.mark{ color:#9E2F23; }
figure{ margin:1.6em 0; text-align:center; page-break-inside:avoid; }
figure img{ max-width:100%; height:auto; border:1px solid #C9B98A; padding:2%; background:#fff;}
figcaption{ font-size:.8em; color:#8A8069; margin-top:.6em; text-align:center; text-indent:0;}
figcaption b{ color:#2C2824; }
table{ width:100%; border-collapse:collapse; font-size:.82em; margin:1.2em 0;}
th{ background:#4E4738; color:#F6EFDD; padding:.45em .3em; font-weight:normal; letter-spacing:.1em;}
td{ border-bottom:1px solid #DDD3B4; padding:.5em .3em; text-align:center; vertical-align:top;}
td.an{ text-align:left; }
.t{ color:#9E2F23; }
.entry{ margin:1em 0;}
.entry .zi{ font-weight:bold; background:#4E4738; color:#F6EFDD; padding:.05em .4em; margin-right:.5em;}
blockquote{ margin:1em 0 1em 1.5em; padding-left:1em; border-left:3px solid #C9B98A;
            color:#4E4738; font-size:.92em; text-indent:0;}
blockquote b{ color:#2C2824; }
.xiaoan b{ color:#2C2824; }
.note{ font-size:.85em; color:#8A8069;}
.colophon{ margin-top:3em; padding-top:1.5em; border-top:1px solid #C9B98A; color:#8A8069;
           font-size:.85em; text-align:center; text-indent:0;}
"""

def page(title, body, fname):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans" lang="zh-Hans">
<head><meta charset="utf-8"/><title>{title}</title>
<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>
<body>
{body}
</body></html>"""

cover_html = page("封面", """
<p class="noindent" style="text-align:center; margin-top:20%;">
   <span style="font-size:2.6em; letter-spacing:.4em; font-weight:600;">道德經</span></p>
<p class="noindent" style="text-align:center; letter-spacing:.4em; color:#8A8069;">三版本對照箋注</p>
<p class="noindent" style="text-align:center; color:#8A8069; font-size:.85em; margin-top:2em;">王弼本 · 河上公本 · 馬王堆帛書甲乙本</p>
<p class="noindent" style="text-align:center; margin-top:4em; color:#8A8069; font-size:.8em;">逐章對讀 · 書影互證 · 箋注今譯 · 校勘隨章</p>
""", "cover.xhtml")

fanli_html = page("凡例", '<h1 class="doctitle">凡例</h1>\n<p class="subtitle">如何使用这本书</p>\n' + fanli_body, "fanli.xhtml")
chap01_html = page("第一章 · 道可道，非常道", chap_body, "chap01.xhtml")

NAV = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans" lang="zh-Hans">
<head><meta charset="utf-8"/><title>目录</title></head>
<body>
<nav epub:type="toc" id="toc"><h1>目錄</h1>
  <ol>
    <li><a href="text/cover.xhtml">封面</a></li>
    <li><a href="text/fanli.xhtml">凡例</a></li>
    <li><a href="text/chap01.xhtml">第一章 · 道可道，非常道</a>
      <ol>
        <li><a href="text/chap01.xhtml#sread">四版本对读</a></li>
        <li><a href="text/chap01.xhtml#sbook">书影</a></li>
        <li><a href="text/chap01.xhtml#szhu">笺注</a></li>
        <li><a href="text/chap01.xhtml#strans">今译</a></li>
        <li><a href="text/chap01.xhtml#sjiao">校勘记</a></li>
      </ol>
    </li>
  </ol>
</nav>
<nav epub:type="landmarks" hidden="hidden"><ol>
  <li><a epub:type="toc" href="text/cover.xhtml">目录</a></li>
  <li><a epub:type="bodymatter" href="text/chap01.xhtml">正文</a></li>
</ol></nav>
</body></html>"""

book_uuid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

img_items = "\n".join(
    f'<item id="i{i}" href="images/{imgs[png]}" media-type="image/jpeg"/>'
    for i, png in enumerate(["wb_guyi.png", "hsg_leaf.png", "st_ch1.png", "bo_jia.png", "bo_yi.png"]))

OPF = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-Hans">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>道德經三版本對照箋注（第一章樣張）</dc:title>
    <dc:creator>編纂樣張</dc:creator>
    <dc:language>zh-Hans</dc:language>
    <dc:source>王弼本《古逸叢書》景刊 / 南宋建陽刊河上公本 / 馬王堆帛書甲乙本</dc:source>
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
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_uuid}"/>
    <meta name="dtb:depth" content="1"/>
  </head>
  <docTitle><text>道德經三版本對照箋注（第一章樣張）</text></docTitle>
  <navMap>
    <navPoint id="n1" playOrder="1"><navLabel><text>封面</text></navLabel><content src="text/cover.xhtml"/></navPoint>
    <navPoint id="n2" playOrder="2"><navLabel><text>凡例</text></navLabel><content src="text/fanli.xhtml"/></navPoint>
    <navPoint id="n3" playOrder="3"><navLabel><text>第一章 · 道可道，非常道</text></navLabel><content src="text/chap01.xhtml"/></navPoint>
  </navMap>
</ncx>"""

os.makedirs(os.path.join(BUILD, "OEBPS", "text"), exist_ok=True)
os.makedirs(os.path.join(BUILD, "OEBPS", "styles"), exist_ok=True)
os.makedirs(os.path.join(BUILD, "META-INF"), exist_ok=True)
open(os.path.join(BUILD, "mimetype"), "w").write("application/epub+zip")
open(os.path.join(BUILD, "META-INF/container.xml"), "w").write(CONTAINER)
open(os.path.join(BUILD, "OEBPS/content.opf"), "w").write(OPF)
open(os.path.join(BUILD, "OEBPS/nav.xhtml"), "w").write(NAV)
open(os.path.join(BUILD, "OEBPS/toc.ncx"), "w").write(NCX)
open(os.path.join(BUILD, "OEBPS/styles/epub.css"), "w").write(CSS)
open(os.path.join(BUILD, "OEBPS/text/cover.xhtml"), "w").write(cover_html)
open(os.path.join(BUILD, "OEBPS/text/fanli.xhtml"), "w").write(fanli_html)
open(os.path.join(BUILD, "OEBPS/text/chap01.xhtml"), "w").write(chap01_html)

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w") as z:
    z.write(os.path.join(BUILD, "mimetype"), "mimetype", compress_type=zipfile.ZIP_STORED)
    for base, _, files in os.walk(BUILD):
        for f in files:
            full = os.path.join(base, f)
            rel = os.path.relpath(full, BUILD)
            if rel == "mimetype":
                continue
            z.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)
print("EPUB written:", OUT, os.path.getsize(OUT) // 1024, "KB")

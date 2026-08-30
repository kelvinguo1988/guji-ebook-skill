#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《道德經三版本對照箋注》全书生成器 v2
单一来源：book.html（设计系统+第一章样章） + work/book_data.json + content_81.py
产出：book_full.html（Edge 渲染 PDF，字体审计见 build_pdf.sh）+ 道德经三版本对照笺注-全书.epub
"""
import re, os, json, difflib, html as H, datetime, uuid, zipfile, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from content_81 import CONTENT

DATA = json.load(open('/Users/sec-t/Downloads/道德经/work/book_data.json', encoding='utf8'))
WB, HSG, JIA, YI = DATA['wangbi'], DATA['hsg'], DATA['jia'], DATA['yi']

from opencc import OpenCC
_cc = OpenCC('s2t')
ENT = {'&ldquo;': '「', '&rdquo;': '」', '&lsquo;': '『', '&rsquo;': '』',
       '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&ircquo;': '', '&nbsp;': ' '}

def clean_text(t):
    for k, v in ENT.items():
        t = t.replace(k, v)
    return re.sub(r'&[a-zA-Z#0-9]{1,8};', '', t)

def to_trad(t):
    return _cc.convert(clean_text(t))

def hanzi(s):
    return ''.join(c for c in s if '\u4e00' <= c <= '\u9fff')

def norm_boshi(t):
    t = re.sub(r'（[^）]*）', '', t)
    return hanzi(t.replace('〔', '').replace('〕', ''))

def esc(t):
    return H.escape(clean_text(t), quote=False)

def clean_pairs(pairs):
    """剔除混入勘误条目/编号/超长碎片的句对，剥离注文脚注号，返回繁体洁净句对。"""
    out = []
    for p in pairs:
        j, z = clean_text(p[0]), clean_text(p[1])
        jh = hanzi(j)
        if not jh or len(jh) > 30:
            continue
        if any(c.isdigit() for c in j):
            continue
        if '影宋' in j or '勘誤' in j or ('卷之' in j and '竟' in j):
            continue
        z = re.sub(r'\d{1,3}(?=[，。；：、])', '', z)
        if any(c.isdigit() for c in z):
            continue
        out.append((to_trad(j), to_trad(z)))
    return out

def hsg_jing_safe(n):
    """河上公本经文：数据被卷尾题记/勘误污染的章（16/37/59/81 等）从洁净章句对重建，并转繁体。"""
    h = HSG[str(n)]
    pairs = clean_pairs(h.get("pairs", []))
    j = clean_text(h.get('jing', ''))
    pair_jing = hanzi(''.join(p[0] for p in pairs))
    jh = hanzi(j)
    contaminated = (any(c.isdigit() for c in j)
                    or ('卷之' in j and '竟' in j) or '勘誤' in j or '影宋' in j
                    or (pair_jing and (len(jh) < len(pair_jing) * 0.5 or len(jh) > len(pair_jing) * 1.4)))
    if contaminated and pairs:
        j = ''.join(p[0] for p in pairs)
    return to_trad(j)

def zhuti(n):
    return CONTENT[n]['zz'] if n in CONTENT else CONTENT[1]['zz']

def jinyi(n):
    return CONTENT[n]['jy'] if n in CONTENT else ''

def juan(n):
    return '卷一 · 道經' if n <= 37 else '卷二 · 德經'

def timu(n, k=12):
    j = WB[str(n)]['jing']
    seg = re.split(r'[。，；、：]', j)[0]
    return seg[:k]

SRC = {'base': '《古逸叢書》景刊王弼注本 · 底本',
       'hss': '南宋建陽刊本 · 臺北故宮博物院藏',
       'jia': '西汉初年写本 · 《集成》释文',
       'yi': '西汉初年写本 · 《集成》释文'}

def vpanel(tagcls, taglabel, small, text, srcclass):
    text = esc(text)
    extra = ' sm' if len(hanzi(text)) > 115 else ''
    cls = 'base' if srcclass == 'base' else 'other'
    small_html = f'<small>{small}</small>' if small else ''
    return (f'<div class="rcell"><span class="tag {tagcls}">{taglabel}{small_html}</span>'
            f'<div class="reader"><div class="vtxt {cls}{extra}">{text}</div>'
            f'<div class="src">{SRC[srcclass]}</div></div></div>')

def diff_table(n):
    wb = hanzi(WB[str(n)]['jing'])
    jia = norm_boshi(JIA[str(n)]['text'])
    yi = norm_boshi(YI[str(n)]['text'])
    hsg = hanzi(HSG[str(n)]['jing'])
    sm = difflib.SequenceMatcher(None, wb, jia, autojunk=False)
    rows = []

    def stance(seg_w, seg_j):
        if seg_w and seg_w in hsg:
            return '同王弼'
        if seg_j and seg_j in hsg:
            return '同甲本'
        return '异'

    def stance_yi(seg_w, seg_j):
        if seg_j and seg_j in yi:
            return '同甲'
        if seg_w and seg_w in yi:
            return '同王弼'
        return '异'

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        seg_w, seg_j = wb[i1:i2], jia[j1:j2]
        if not seg_w and not seg_j:
            continue
        note = '用字异'
        if '恆' in seg_j and '常' in (seg_w + wb):
            note = '帛书作「恆」，今本避讳作「常」'
        elif '也' in seg_j:
            note = '帛书句尾语气词「也」'
        elif not seg_w:
            note = '帛书衍文'
        elif not seg_j:
            note = '王弼本增字'
        rows.append([esc(seg_w) or '—', stance(seg_w, seg_j),
                     f'<span class="t">{esc(seg_j)}</span>' or '—', stance_yi(seg_w, seg_j), note])
        if len(rows) >= 6:
            break
    if not rows:
        rows = [['（字符级比对无差异）', '—', '—', '—', '本章四本经文用字相合']]

    notes = []
    if n <= 37:
        notes.append('篇属。帛书两本皆〈德〉篇在前、〈道〉篇在后，本章居帛书卷末段；册本次序从王弼本。')
    else:
        bn = JIA[str(n)].get('boshu_no', '')
        notes.append(f'篇属。帛书两本皆〈德〉篇在前、〈道〉篇在后，本章属〈德〉篇（帛本次序第{bn if bn else "??"}章），居卷首段。')
    jia_raw, yi_raw = JIA[str(n)]['text'], YI[str(n)]['text']
    nloang = len(re.findall(r'（[^）]*）', jia_raw)) + len(re.findall(r'（[^）]*）', yi_raw))
    nlac = len(re.findall(r'〔[^〕]*〕', jia_raw)) + len(re.findall(r'〔[^〕]*〕', yi_raw))
    if nloang or nlac:
        notes.append(f'用字与残泐。两帛书释文共见通假今字 {nloang} 处、残缺拟补 {nlac} 处；借字如「胃（謂）」「噭（徼）」之属，皆依《長沙馬王堆漢墓簡帛集成》迻录。')
    yj = [t.count('也') for t in (norm_boshi(jia_raw), norm_boshi(yi_raw), wb)]
    if yj[0] or yj[1]:
        notes.append(f'语气词。帛书甲本「也」字 {yj[0]} 见、乙本 {yj[1]} 见，王弼本 {yj[2]} 见；今本删「也」，句读随之而变。')
    if '恆' in jia or '恆' in yi:
        notes.append('避讳。帛书作「恆」，今本作「常」，盖汉人避文帝刘恒讳改；恒、义本相通，改字而义存。')
    notes.append('今译从王弼本句读；异文红线标出，供覆按。')
    return rows, notes[:4]

def chapter_html(n):
    wb, hsg = WB[str(n)], HSG[str(n)]
    jia, yi = JIA[str(n)], YI[str(n)]
    hjing = hsg_jing_safe(n)
    t = timu(n)
    out = []
    # 章首（固定页）
    out.append(f'<section class="page">'
               f'<div class="ch-flow-head">'
               f'<div class="ch-flow-num">第 {n} 章 · {juan(n)}</div>'
               f'<h2 class="ch-flow-title">{esc(t)}</h2>'
               f'<div class="ch-flow-rule"><i></i><b></b><i></i></div>'
               f'<div class="ch-gist"><b>章旨</b>{esc(zhuti(n))}</div>'
               f'</div></section>')
    # 对读·上（固定页）
    out.append('<section class="page"><div class="readers" style="margin-top:2mm">'
               + vpanel('base', '王弼本', '底本', wb['jing'], 'base')
               + vpanel('hss', '河上公本', '', hjing, 'hss')
               + '</div></section>')
    # 对读·下 + 图例（固定页）
    out.append('<section class="page"><div class="readers" style="margin-top:2mm">'
               + vpanel('jia', '帛书甲本', '', jia['text'], 'jia')
               + vpanel('yi', '帛书乙本', '', yi['text'], 'yi')
               + '</div>'
               + '<div class="legend"><span><i>〔　〕</i>残缺拟补</span><span><i>（　）</i>通假今字</span>'
                 '<span>句读从《集成》释文</span></div></section>')
    # 古注（流式，另起新页）
    out.append('<div class="flow-sec">'
               '<div class="kicker">古注</div><h3 class="sec">王弼注 · 河上公章句</h3>')
    zhu = wb.get('zhu')
    if zhu:
        out.append('<h4 class="gsec">王弼注</h4>')
        for j, z in zhu:
            out.append(f'<p class="gupair"><b>{esc(to_trad(j))}</b>　{esc(to_trad(z))}</p>')
    else:
        out.append('<p class="note">王弼注此章阙，今以河上公章句足之。</p>')
    out.append('<h4 class="gsec">河上公章句</h4>')
    pairs = clean_pairs(hsg.get('pairs', []))
    for j, z in pairs[:9]:
        out.append(f'<p class="gupair"><b>{esc(j)}</b>　{esc(z)}</p>')
    if len(pairs) > 9:
        out.append(f'<p class="note">其余 {len(pairs) - 9} 则从略，全注见河上公本卷内。</p>')
    out.append('</div>')
    # 今译 + 校勘（流式续排）
    out.append('<div class="flow-sec">'
               '<div class="kicker">今译</div><h3 class="sec">白话通释</h3>')
    out.append(f'<p class="jy">{esc(jinyi(n))}</p>')
    rows, notes = diff_table(n)
    out.append('<div class="kicker" style="margin-top:8mm">校勘记</div><h3 class="sec">版本比对</h3>')
    out.append('<p class="note">异文由四本字符级比对程序生成（句读与括注从略），佐以规则校按。</p>')
    out.append('<table class="jiaokan"><tr><th style="width:20%">王弼本</th><th style="width:16%">河上公本</th>'
               '<th style="width:24%">帛书甲本</th><th style="width:20%">帛书乙本</th><th>备考</th></tr>')
    for r in rows:
        out.append('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>')
    out.append('</table>')
    for i, note in enumerate(notes, 1):
        out.append(f'<p class="xiaoan"><b>校按{"一二三四五六"[i - 1]}</b>　{note}</p>')
    out.append('</div>')
    out.append('</section>')
    return '\n'.join(out)

# ---------------- 组装全书 ----------------
base = open(os.path.join(ROOT, 'book.html'), encoding='utf-8').read()
style = re.search(r'<style>(.*?)</style>', base, re.S).group(1)
sections = re.findall(r'<section class="page[^"]*">(.*?)</section>', base, re.S)
assert len(sections) == 12, f'book.html sections={len(sections)}'
cover, titlepage, fanli = sections[0], sections[1], sections[2]
ch1_pages = '\n'.join(f'<section class="page">{s}</section>' for s in sections[3:12])

FLOW_CSS = '''
  /* ===== 全书流式版式 ===== */
  @page{ size:185mm 260mm; margin:20mm 20mm 16mm; }
  body{ background:var(--paper); }
  .page{ page-break-after:always; }
  .ch-flow-head{ padding-top:8mm; }
  .ch-flow-num{ font-family:var(--song); font-size:10pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:4mm; }
  .ch-flow-title{ font-family:var(--song); font-weight:900; font-size:23pt; letter-spacing:.2em; color:var(--ink); margin-bottom:4mm; }
  .ch-flow-rule{ display:flex; align-items:center; gap:3mm; margin-bottom:6mm; }
  .ch-flow-rule i{ width:30mm; height:.5pt; background:var(--rule); }
  .ch-flow-rule b{ width:2.2mm; height:2.2mm; background:var(--cinnabar); transform:rotate(45deg); }
  .readers{ margin-top:2mm; }
  .vtxt.sm.base{ font-size:12.8pt; } .vtxt.sm.other{ font-size:10.8pt; }
  .flow-sec{ break-before:page; }
  /* 流式内容之后的固定页分区必须强制换页，否则章首会与上一章拼接/跨页截断 */
  body > .flow-sec ~ .page{ break-before:page; }
  .chapter{ break-before:page; }
  .gupair{ font-size:9.8pt; line-height:1.92; text-align:justify; margin-bottom:2.6mm; color:var(--ink2); }
  .gupair b{ font-family:var(--song); color:var(--ink); }
  .gsec{ font-family:var(--song); font-size:9.5pt; letter-spacing:.4em; color:#775A28; margin:5mm 0 2.6mm; break-after:avoid; }
  .jy{ font-size:12pt; line-height:2.3; text-align:justify; color:var(--ink); }
  .toc-page{ page-break-after:always; }
  .toc-cols{ column-count:2; column-gap:9mm; }
  .toc-item{ font-size:9.5pt; line-height:2.0; color:var(--ink2); break-inside:avoid; }
  .toc-item b{ font-family:var(--song); color:var(--cinnabar); margin-right:2mm; }
  .vol-head{ page-break-before:always; text-align:center; padding-top:60mm; }
  .vol-head .vt{ font-family:var(--song); font-weight:900; font-size:30pt; letter-spacing:.6em; color:var(--ink); }
  .vol-head .vs{ margin-top:6mm; font-size:10pt; letter-spacing:.3em; color:var(--note); }
  h3.sec{ break-after:avoid; }
'''

def toc_pages():
    items = [f'<p class="toc-item"><b>{n:02d}</b>{esc(timu(n, 14))}</p>' for n in range(1, 82)]
    pages = []
    for i in range(0, 81, 30):
        chunk = ''.join(items[i:i + 30])
        pages.append(f'<section class="page toc-page">'
                     f'<div class="rh"><span>道德經三版本對照箋注</span><span>卷目</span></div>'
                     f'<div style="margin-top:9mm"><div class="kicker hollow">卷目</div><h3 class="sec">章次</h3>'
                     f'<div class="sec-sub">册本次序从王弼本；帛书两本次序相反，说详各章校按。</div></div>'
                     f'<div class="toc-cols">{chunk}</div></section>')
    return pages

def vol_head(n):
    return (f'<section class="vol-head"><div class="vt">{"道 經" if n == 1 else "德 經"}</div>'
            f'<div class="vs">{"第一章至第三十七章" if n == 1 else "第三十八章至第八十一章"}</div></section>')

fanli2 = fanli.replace('每章先陈<b>四版本对读</b>，继以<b>书影</b>互证，次为<b>笺注</b>（汇古注而系今释）、<b>今译</b>，末附<b>校勘记</b>。',
                       '每章先陈<b>四版本对读</b>，次为<b>古注</b>（王弼注与河上公章句并陈）、<b>今译</b>，末附<b>校勘记</b>（异文表由四本字符级比对生成，佐以规则校按）。')
fanli2 = fanli2.replace('书影采自台北故宫博物院、哈佛大学图书馆等处藏本；经文、古注均与藏本叶面逐一比对',
                        '书影采自台北故宫博物院、哈佛大学图书馆等处藏本，集中于卷首及第一章（图版以可核实为度）；经文、古注均与藏本叶面逐一比对')

body = []
body.append(f'<section class="page cover">{cover}</section>')
body.append(f'<section class="page titlepage">{titlepage}</section>')
body.append(f'<section class="page">{fanli2}</section>')
body.append('''<section class="page">
  <div class="rh"><span>道德經三版本對照箋注</span><span>卷首</span></div>
  <div style="margin-top:7mm"><div class="kicker hollow">书影</div><h3 class="sec">卷首书影</h3>
  <div class="sec-sub">底本与对读本的版刻原貌；第一章全具书影详见样章。</div></div>
  <div class="plates two">
    <figure class="plate"><div class="ph"><img src="assets/wb_guyi.png"/></div>
      <figcaption><span class="ft"><i>图一</i>王弼注《老子道德經》卷上首叶</span>
      <span class="fs">《古逸叢書》据集唐字本景刊 · 经文大字，注双行小字</span></figcaption></figure>
    <figure class="plate"><div class="ph"><img src="assets/hsg_leaf.png"/></div>
      <figcaption><span class="ft"><i>图二</i>《音註河上公老子道德經》體道第一</span>
      <span class="fs">南宋建陽麻沙刘通判宅仰高堂刊本 · 台北故宫博物院藏</span></figcaption></figure>
  </div></section>''')
body += toc_pages()
body.append(vol_head(1))
body.append(ch1_pages)
for n in range(2, 38):
    body.append(chapter_html(n))
body.append(vol_head(38))
for n in range(38, 82):
    body.append(chapter_html(n))
body.append('''<section class="chapter">
  <div style="text-align:center; padding-top:40mm;">
    <div class="kicker" style="justify-content:center">跋</div>
    <p style="font-size:10.5pt; line-height:2.2; color:var(--ink2); text-align:justify; margin:8mm 4mm 0;">本书以《古逸叢書》景刊王弼本为底，河上公本、马王堆帛书甲乙本对读，古注今译随章系之；异文表由四本字符级比对程序生成，校按规则化缀辑，图版以可核实为度。释文从《長沙馬王堆漢墓簡帛集成》，释义纂辑并参考识典古籍、国家图书馆中华古籍智慧化服务平台等数字古籍库。</p>
    <div style="margin-top:14mm; font-size:10pt; letter-spacing:.7em; color:var(--cinnabar);">全 書 終</div>
    <div style="margin-top:10mm; font-size:7.5pt; letter-spacing:.3em; color:var(--note); line-height:2;">道德经三版本对照笺注 · 全书八十一章<br/>十六开本（185×260mm）· 编纂参考：识典古籍 / 中华古籍智慧化服务平台 / 《長沙馬王堆漢墓簡帛集成》</div>
  </div></section>''')

html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>道德經三版本對照箋注</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{style}{FLOW_CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, 'book_full.html'), 'w', encoding='utf-8').write(html)
print('book_full.html:', round(os.path.getsize(os.path.join(ROOT, 'book_full.html')) / 1024 / 1024, 1), 'MB')

# ---------------- EPUB ----------------
def xml_repair(s):
    s = re.sub(r'<(img|br|hr)((?:[^>/]|/(?!>))*)>', r'<\1\2/>', s)
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', s)
    return s

def page_doc(title, body_html, fname):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/><title>{title}</title>'
            f'<link rel="stylesheet" type="text/css" href="../styles/epub.css"/></head>\n<body>\n'
            f'{xml_repair(body_html)}\n</body></html>')

EP_CSS_PATH = os.path.join(ROOT, 'epub_build', 'OEBPS', 'styles', 'epub.css')
EP_CSS = open(EP_CSS_PATH, encoding='utf-8').read() if os.path.exists(EP_CSS_PATH) else \
    'body{font-family:serif;line-height:1.9;}'

BUILD = os.path.join(ROOT, 'epub_full')
for d_ in ['OEBPS/text', 'OEBPS/styles', 'OEBPS/images', 'META-INF']:
    os.makedirs(os.path.join(BUILD, d_), exist_ok=True)
open(os.path.join(BUILD, 'mimetype'), 'w').write('application/epub+zip')
open(os.path.join(BUILD, 'META-INF/container.xml'), 'w').write(
    '<?xml version="1.0" encoding="UTF-8"?>\n<container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
open(os.path.join(BUILD, 'OEBPS/styles/epub.css'), 'w', encoding='utf-8').write(EP_CSS)

from PIL import Image
for name, w in [("wb_guyi.png", 1200), ("hsg_leaf.png", 900), ("st_ch1.png", 900),
                ("bo_jia.png", 900), ("bo_yi.png", 900)]:
    im = Image.open(os.path.join(ROOT, 'assets', name)).convert('RGB')
    if im.width > w:
        im = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    im.save(os.path.join(BUILD, 'OEBPS/images', name.replace('.png', '.jpg')), 'JPEG', quality=82)

files, nav_items = [], []
files.append(('cover.xhtml', 0, page_doc('封面',
    '<p class="noindent" style="text-align:center;margin-top:18%"><span style="font-size:2.6em;'
    'letter-spacing:.4em;font-weight:600">道德經</span></p>'
    '<p class="noindent" style="text-align:center;letter-spacing:.4em;color:#8A8069">三版本對照箋注</p>'
    '<p class="noindent" style="text-align:center;color:#8A8069;font-size:.85em;margin-top:2em">王弼本 · 河上公本 · 馬王堆帛書甲乙本</p>',
    'cover.xhtml')))
nav_items.append(('封面', 'cover.xhtml'))
files.append(('fanli.xhtml', 0, page_doc('凡例', '<h1 class="doctitle">凡例</h1>\n' + fanli2, 'fanli.xhtml')))
nav_items.append(('凡例', 'fanli.xhtml'))

ch1 = '\n'.join(sections[3:12])
ch1 = re.sub(r'<div class="folio"[^>]*>.*?</div>', '', ch1, flags=re.S)
ch1 = re.sub(r'<div class="rh">.*?</div>', '', ch1, flags=re.S)
ch1 = ch1.replace('assets/', '../images/').replace('.png"', '.jpg"')
files.append(('chap001.xhtml', 0, page_doc('第一章 · 道可道，非常道',
    '<h1 class="doctitle">第一章 · 道可道，非常道</h1>\n' + ch1, 'chap001.xhtml')))
nav_items.append(('第一章 · 道可道，非常道', 'chap001.xhtml'))

for n in range(2, 82):
    chap = chapter_html(n)
    vtxts = re.findall(r'<div class="vtxt[^"]*">(.*?)</div>', chap, re.S)
    jy = esc(jinyi(n))
    rows, notes = diff_table(n)
    table = ['<table><tr><th>王弼本</th><th>河上公本</th><th>帛书甲本</th><th>帛书乙本</th><th>备考</th></tr>']
    for r in rows:
        table.append('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>')
    table.append('</table>')
    guzhu = []
    zhu = WB[str(n)].get('zhu')
    if zhu:
        for j, z in zhu[:3]:
            guzhu.append(f'<blockquote><b>王弼曰</b>　{esc(to_trad(j))}{esc(to_trad(z))}</blockquote>')
    body_ep = [f'<h1 class="doctitle">第{n}章 · {esc(timu(n))}</h1>',
               f'<p class="note">章旨　{esc(zhuti(n))}</p>',
               '<h2 class="sec">四版本对读</h2>']
    for nm, tx in zip(['王弼本（底本）', '河上公本', '帛书甲本', '帛书乙本'], vtxts):
        body_ep.append(f'<p class="jing"><span class="vname">{nm}</span>{tx.strip()}</p>')
    body_ep.append('<h2 class="sec">古注选读</h2>')
    body_ep += (guzhu if guzhu else ['<blockquote>王弼注此章阙。</blockquote>'])
    body_ep.append('<h2 class="sec">今译</h2>')
    body_ep.append(f'<p>{jy}</p>')
    body_ep.append('<h2 class="sec">校勘记</h2>')
    body_ep += table
    for i, note in enumerate(notes, 1):
        body_ep.append(f'<p class="xiaoan"><b>校按{"一二三四五六"[i-1]}</b>　{note}</p>')
    fn = f'chap{n:03d}.xhtml'
    files.append((fn, 0, page_doc(f'第{n}章', '\n'.join(body_ep), fn)))
    nav_items.append((f'第{n}章 · {timu(n, 8)}', fn))

for fname, _, doc in files:
    open(os.path.join(BUILD, 'OEBPS/text', fname), 'w', encoding='utf-8').write(xml_repair(doc))

nav_li = '\n'.join(f'<li><a href="text/{f}">{esc(t)}</a></li>' for t, f in nav_items)
NAV = (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
       f'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans" lang="zh-Hans"><head><meta charset="utf-8"/>'
       f'<title>目录</title></head><body><nav epub:type="toc" id="toc"><h1>目錄</h1><ol>{nav_li}</ol></nav>'
       f'<nav epub:type="landmarks" hidden="hidden"><ol><li><a epub:type="bodymatter" href="text/chap001.xhtml">正文</a></li>'
       f'</ol></nav></body></html>')
open(os.path.join(BUILD, 'OEBPS/nav.xhtml'), 'w', encoding='utf-8').write(NAV)
uid = str(uuid.uuid4())
modified = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
img_items = '\n'.join(f'<item id="img{i}" href="images/{n.replace(".png", ".jpg")}" media-type="image/jpeg"/>'
                      for i, n in enumerate(["wb_guyi.png", "hsg_leaf.png", "st_ch1.png", "bo_jia.png", "bo_yi.png"]))
file_items = '\n'.join(f'<item id="f{i}" href="text/{f}" media-type="application/xhtml+xml"/>'
                       for i, (f, _, _) in enumerate(files))
spine = '\n'.join(f'<itemref idref="f{i}"/>' for i in range(len(files)))
OPF = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
       f'unique-identifier="bid" xml:lang="zh-Hans"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
       f'<dc:identifier id="bid">urn:uuid:{uid}</dc:identifier><dc:title>道德經三版本對照箋注</dc:title>'
       f'<dc:creator>編纂</dc:creator><dc:language>zh-Hans</dc:language>'
       f'<meta property="dcterms:modified">{modified}</meta></metadata>'
       f'<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
       f'<item id="css" href="styles/epub.css" media-type="text/css"/>{img_items}{file_items}</manifest>'
       f'<spine>{spine}</spine></package>')
open(os.path.join(BUILD, 'OEBPS/content.opf'), 'w', encoding='utf-8').write(OPF)
NCX = (f'<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
       f'<head><meta name="dtb:uid" content="urn:uuid:{uid}"/></head>'
       f'<docTitle><text>道德經三版本對照箋注</text></docTitle><navMap>'
       + ''.join(f'<navPoint id="n{i}" playOrder="{i+1}"><navLabel><text>{esc(t)}</text></navLabel>'
                 f'<content src="text/{f}"/></navPoint>' for i, (t, f) in enumerate(nav_items))
       + '</navMap></ncx>')
open(os.path.join(BUILD, 'OEBPS/toc.ncx'), 'w', encoding='utf-8').write(NCX)

OUT = os.path.join(ROOT, '道德经三版本对照笺注-全书.epub')
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
print('CHAPTERS DONE')

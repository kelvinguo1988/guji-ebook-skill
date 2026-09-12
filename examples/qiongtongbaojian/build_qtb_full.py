#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《窮通寶鑑箋注》全书生成器 v3 —— 标准流式分页版
数据：/tmp/qtb_sections.json（113 节，源自排印整理本）
产出：qtb_full.html（Edge 渲染 PDF，字体审计见 render_audit.sh）+ 穷通宝鉴笺注-全书.epub
体例：原文/徐乐吾评注 = 繁体；提要/白话/术语/今人按语 = 简体。
"""
import re, os, json, datetime, uuid, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SECS = json.load(open('/tmp/qtb_sections.json', encoding='utf-8'))

from opencc import OpenCC
cc = OpenCC('s2t')
ENT = {'&ldquo;': '「', '&rdquo;': '」', '&lsquo;': '『', '&rsquo;': '』',
       '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&ircquo;': '', '&nbsp;': ' '}

def clean_text(t):
    for k, v in ENT.items():
        t = t.replace(k, v)
    t = re.sub(r'(?m)^-{3,}$', '', t)          # markdown 分隔线
    t = re.sub(r'-{3,}', '——', t)               # 行内长破折线
    return re.sub(r'&[a-zA-Z#0-9]{1,8};', '', t)

def to_trad(t):
    s = cc.convert(clean_text(t))
    s = re.sub(r',', '，', s)
    s = re.sub(r';', '；', s)
    s = re.sub(r'\?', '？', s)
    s = re.sub(r'!', '！', s)
    s = re.sub(r':', '：', s)
    return s

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

def merge_softwrap(lines):
    paras, buf = [], ''
    for l in lines:
        l = re.sub(r'\s+', '', l)
        if not l:
            continue
        buf += l
        if re.search(r'[。？！」"]$', buf):
            paras.append(buf); buf = ''
    if buf:
        paras.append(buf)
    return paras

def split_xu(paras):
    out = []
    for p in paras:
        if p.startswith('徐乐吾曰'):
            out.append(('xu', re.sub(r'^徐乐吾曰[\s:：∶]*', '', p)))
        elif '徐乐吾曰' in p:
            pre, post = p.split('徐乐吾曰', 1)
            if pre:
                out.append(('main', pre))
            out.append(('xu', re.sub(r'^[\s:：∶]*', '', post)))
        else:
            out.append(('main', p))
    return out

def first_sent(t, cap=110):
    s = re.split(r'[。；]', re.sub(r'\s+', '', t))[0]
    return s[:cap]

def chapter_html(n):
    s = SECS[str(n)]
    vi = sec_vol[n]
    has_own = vol_of(s['title']) is not None
    vol_label = f' · 卷{NUM_CN[vi]} · 論{GANS[vi][:1]}' if has_own else ''
    title = to_trad(s['title'])
    ylines = s['yuanwen'].split('\n')
    if ylines and re.sub(r'\s+', '', to_trad(ylines[0])) == re.sub(r'\s+', '', to_trad(s['title'])):
        ylines = ylines[1:]   # 剥掉原文节内重复的节题行
    yparas = split_xu(merge_softwrap(ylines))
    out = ['<section class="chapter">',
           '<div class="ch-open">',
           '<div class="ch-head">',
           f'<div class="ch-num">第 {n} 节{vol_label}</div>',
           f'<h2 class="ch-title">{esc(title)}</h2>',
           '<div class="ch-rule"><i></i><b></b><i></i></div>',
           f'<div class="ch-gist"><b>提要</b>{esc(first_sent(s["baihua"], 110))}。</div>',
           '</div>',
           '<h3 class="sec">原文</h3>',
           '<p class="sec-note">繁体移录；「徐注」为徐乐吾评注，随文附见。</p>']
    for kind, p in yparas:
        p = to_trad(p)
        if kind == 'xu':
            out.append(f'<div class="xuzhu"><span class="xtag">徐注</span>{esc(p)}</div>')
        else:
            out.append(f'<p class="yw">{esc(norm_quotes(p))}</p>')
    out.append('<h3 class="sec">白话通释</h3>')
    for p in merge_softwrap(s['baihua'].split('\n')):
        out.append(f'<p>{esc(norm_quotes(p))}</p>')
    kws = re.findall(r'([^\n：]{2,10})：([^\n]+)', s['kw'])
    qishi = merge_softwrap(s['qishi'].split('\n'))
    if kws:
        out.append('<h3 class="sec">术语笺释</h3><div class="kwcards">')
        for kt, kv in kws:
            out.append(f'<div class="kwcard"><span class="kt">{esc(kt)}</span>'
                       f'<p>{esc(norm_quotes(kv))}</p></div>')
        out.append('</div>')
    if qishi:
        out.append('<h3 class="sec">今人按语</h3><div class="qishi">')
        for j, p in enumerate(qishi):
            cls = ' class="ask"' if ('？' in p and j == len(qishi) - 1) else ''
            out.append(f'<p{cls}>{esc(norm_quotes(p))}</p>')
        out.append('</div>')
    out.append('</section>')
    return '\n'.join(out)

# ---------------- 组装 ----------------
SAMPLE = os.environ.get('QTB_SAMPLE')  # 非空 → 只出第一章样章（第1~3节）
body = []
# 封面（@page:first 满版）
body.append('''<section class="cover-page">
  <div class="frame"></div>
  <div class="main-title">窮通寶鑑</div>
  <div class="sub-title">十干月令調候祕本</div>
  <div class="editions">原文 · 徐樂吾評注 · 白話通釋 · 清寫刻本書影對讀</div>
  <div class="quote">得氣之寒　遇暖而發</div>
  <div class="seal">調候為急</div>
  <div class="foot">欄江網 · 造化元鑰 · 子部術數類</div>
</section>''')
# 扉页
body.append('''<section class="titlepage">
  <div class="big">窮通寶鑑箋注</div>
  <div class="verline">卷一 · 論甲木 至 卷十 · 論癸水</div>
  <div class="rule-orn"><i></i><b></b><i></i></div>
  <div class="note-block">
    原文以排印整理本為底，參風陵文庫藏清寫刻本<br>
    徐樂吾評注隨文繫之　白話今譯附焉<br>
    術語箋釋　今人按語別為一格
  </div>
  <div class="sample-tag">{}</div>
</section>'''.format('第一章样章 · 甲木總論 正月甲木 二月甲木' if SAMPLE else '全書一百一十三節'))
# 凡例
body.append('''<section class="fanli">
  <h2 class="sec">凡例</h2>
  <ul class="fali">
    <li><b>一、底本与对读。</b>文字以排印整理本为底，参<b>風陵文庫藏清寫刻本</b>（书影随文）；原书题《欄江網》，一名《造化元鑰》，余春台编次，徐乐吾评注。</li>
    <li><b>二、编排次第。</b>每节先陈<b>原文</b>（繁体大字，徐乐吾评注以「徐注」随文缩排），继以<b>白话通释</b>、<b>术语笺释</b>与<b>今人按语</b>。</li>
    <li><b>三、用字体例。</b>原文、评注用繁体字；提要、白话、按语用简体字。命理专名（如「沖」「剋」）保留原字形。</li>
    <li><b>四、术语笺释。</b>调候、活木死木、斫轮格等专门术语，随节立卡释义；跨节互见者注「详见某节」。</li>
    <li><b>五、今人按语。</b>排印本所附现代解读别为一格辑录，仅供启发，不代表原书义理。</li>
  </ul>
</section>''')
# 卷首书影
body.append('''<section class="shuying">
  <h2 class="sec">卷首书影</h2>
  <p class="sec-note">风陵文库藏清写刻本 · 甲木总论起首叶（论甲木 · 木性腾上而无所止）。</p>
  <figure class="plate"><img src="assets/qtb_jiamu_leaf.png" alt="穷通宝鉴清写刻本甲木总论起首叶"/>
  <figcaption><span class="ft"><i>图一</i>《窮通寶鑑》甲木总论起首叶</span>
  —— 清写刻本 · 风陵文库藏 · 版心题「窮通寶鑑 甲」</figcaption></figure>
</section>''')
# 总目（40 节一页）
items = ''.join(f'<p class="toc-item"><b>{n:03d}</b>{esc(SECS[str(n)]["title"])}</p>' for n in range(1, 114))
item_list = re.findall(r'<p class="toc-item">.*?</p>', items, re.S)
for i in range(0, 113, 40):
    chunk = ''.join(item_list[i:i+40])
    body.append(f'<section class="toc-block"><h2 class="sec">总目（{i+1}–{min(i+40, 113)}）</h2>'
                f'<div class="toc-cols">{chunk}</div></section>')
base = open(os.path.join(ROOT, 'qtb_ch1.html'), encoding='utf-8').read()
secs_html = re.findall(r'<section class="page[^"]*">(.*?)</section>', base, re.S)
assert len(secs_html) == 12, f"qtb_ch1.html sections={len(secs_html)}"
cover, fanye, fali, shuying = secs_html[0], secs_html[1], secs_html[2], secs_html[3]
# 卷归属（无干名的总论节顺延前节）
sec_vol = {}
last_vi = None
for n in range(1, 114):
    vi = vol_of(SECS[str(n)]['title'])
    if vi is None:
        vi = last_vi
    sec_vol[n] = vi
    last_vi = vi
vol_counts = {}
for n in range(2, 114):
    vi = sec_vol[n]
    if vi is not None:
        vol_counts[vi] = vol_counts.get(vi, 0) + 1
# 卷隔页 + 各节
ch1_pages = '\n'.join(f'<section class="page">{s}</section>' for s in secs_html[4:11])
body.append(ch1_pages)
if SAMPLE:
    for n in (2, 3):
        body.append(chapter_html(n))
else:
    last_vi = None
    for n in range(2, 114):
        vi = sec_vol[n]
        if vi != last_vi:
            body.append(f'<section class="vol-head"><div class="vt">卷{NUM_CN[vi]} · 論{GANS[vi]}</div>'
                        f'<div class="vs">{GANS[vi]} · 凡{vol_counts.get(vi, 0)}节</div></section>')
            last_vi = vi
        body.append(chapter_html(n))
# 跋
body.append('''<section class="colophon">
  <div class="kicker" style="justify-content:center">跋</div>
  <p>《窮通寶鑑》原名《欄江網》，一名《造化元鑰》，余春台编次，徐乐吾评注；以十天干配十二月令，专论调候。本书原文与评注以排印整理本为底、参风陵文库藏清写刻本对读；白话、术语笺释与今人按语从排印本辑录，体例详见凡例。</p>
  <div class="end">全 書 終</div>
  <div class="meta">{}</div>
</section>'''.format(
    '穷通宝鉴笺注 · 第一章样章（甲木总论 · 正月甲木 · 二月甲木）<br/>十六开本（185×260mm）<br/>编纂参考：识典古籍 · 中华古籍智慧化服务平台 · 风陵文库藏清写刻本'
    if SAMPLE else
    '穷通宝鉴笺注 · 全书一百一十三节<br/>十六开本（185×260mm）<br/>编纂参考：识典古籍 · 中华古籍智慧化服务平台 · 风陵文库藏清写刻本'))

CSS = '''
:root{
  --paper:#F8F4E9; --ink:#2C2824; --ink2:#4E4738; --note:#8A8069;
  --cinnabar:#9E2F23; --dark:#232D3F; --dark2:#141D2B;
  --rule:#C9B98A; --rule-soft:#DDD3B4; --gold:#B79B5E;
  --song:"Noto Serif TC","Songti SC",serif;
  --kai:"LXGW WenKai","Noto Serif TC",serif;
}
*{ margin:0; padding:0; box-sizing:border-box; }
/* 纸面用纯白：若整页铺奶油底色，白色页边距会被读成窗口背景，正文视觉上「贴边」 */
html,body{ background:#FFFFFF; }
body{ font-family:var(--song); color:var(--ink); font-kerning:normal; }

@page{ size:185mm 260mm; margin:20mm 20mm 18mm; }
@page :first{ margin:0; }

/* 封面（唯一满版页） */
.cover-page{ width:185mm; height:260mm; position:relative; overflow:hidden;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%);
  color:#EDE3C8; page-break-after:always; }
.cover-page .frame{ position:absolute; inset:7mm; border:.6pt solid rgba(183,155,94,.55);
  outline:1.4pt double rgba(183,155,94,.28); outline-offset:1.8mm; }
.cover-page .main-title{ position:absolute; top:20mm; right:24mm; writing-mode:vertical-rl;
  font-family:var(--kai); font-weight:700; font-size:55pt; letter-spacing:.26em; line-height:1.12; }
.cover-page .sub-title{ position:absolute; top:28mm; right:86mm; writing-mode:vertical-rl;
  font-size:14pt; letter-spacing:.55em; color:#C8B98D; }
.cover-page .editions{ position:absolute; top:24mm; left:26mm; writing-mode:vertical-rl;
  font-size:9.5pt; letter-spacing:.4em; color:rgba(200,185,141,.85); height:120mm; }
.cover-page .quote{ position:absolute; bottom:38mm; left:26mm; writing-mode:vertical-rl;
  font-size:9pt; letter-spacing:.32em; color:rgba(200,185,141,.6); height:72mm; }
.cover-page .seal{ position:absolute; bottom:24mm; right:24mm; width:16mm; height:16mm;
  background:var(--cinnabar); color:#F6EBD9; display:flex; align-items:center; justify-content:center;
  writing-mode:vertical-rl; text-orientation:upright; font-size:8.4pt; letter-spacing:.16em;
  line-height:1.25; border-radius:1mm; }
.cover-page .foot{ position:absolute; bottom:11mm; left:0; right:0; text-align:center;
  font-size:7.5pt; letter-spacing:.5em; color:rgba(200,185,141,.55); }

/* 扉页 */
.titlepage{ page-break-after:always; text-align:center; padding-top:32mm; }
.titlepage .big{ writing-mode:vertical-rl; font-family:var(--song); font-weight:900;
  font-size:38pt; letter-spacing:.32em; height:112mm; display:inline-block; }
.titlepage .verline{ margin-top:11mm; font-size:12pt; letter-spacing:.42em; color:var(--ink2); }
.titlepage .rule-orn{ margin:10mm auto 8mm; display:flex; align-items:center; justify-content:center; gap:3mm; }
.titlepage .rule-orn i{ width:26mm; height:.5pt; background:var(--rule); }
.titlepage .rule-orn b{ width:2.6mm; height:2.6mm; background:var(--cinnabar); transform:rotate(45deg); }
.titlepage .note-block{ text-align:center; font-size:9.5pt; line-height:2.15; color:var(--ink2); letter-spacing:.1em; }
.titlepage .sample-tag{ margin-top:12mm; font-size:8.5pt; letter-spacing:.4em; color:var(--note); }

/* 通用 */
h2.sec{ font-family:var(--song); font-weight:700; font-size:13.5pt; letter-spacing:.35em;
  color:var(--ink); margin:9mm 0 3.5mm; break-after:avoid; }
h3.sec{ font-family:var(--song); font-weight:700; font-size:11.5pt; letter-spacing:.35em;
  color:var(--ink); margin:8mm 0 3mm; break-after:avoid; }
p.sec-note{ font-size:8.6pt; color:var(--note); letter-spacing:.1em; margin:0 0 4mm; break-after:avoid; }
.kicker{ font-family:var(--song); font-size:8pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:3mm; }

/* 第一章（甲木总论）碎片段：旧样章遗留结构——每片独立起页、书眉与小节头接管 */
.page{ break-before:page; }
.rh{ display:flex; justify-content:space-between; font-size:8pt; letter-spacing:.28em;
  color:var(--note); margin-bottom:7mm; }
.sec-sub{ font-size:10.5pt; line-height:1.9; color:var(--ink2); margin:-.5mm 0 4mm; }
.para{ break-inside:avoid; }
.para .seal-tag{ display:block; font-family:var(--song); font-size:10.5pt; letter-spacing:.4em;
  color:var(--ink); margin:2mm 0 1.6mm; }
.para p.text{ font-size:12pt; line-height:2.25; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:4mm; }
.fali li{ list-style:none; position:relative; padding-left:11mm; margin-bottom:5.4mm;
  font-size:10pt; line-height:1.95; text-align:justify; }
.fali li .no{ position:absolute; left:0; top:.4mm; width:6.4mm; height:6.4mm;
  border:.6pt solid var(--cinnabar); color:var(--cinnabar); border-radius:50%;
  font-family:var(--song); font-size:8pt; display:flex; align-items:center; justify-content:center; }
.fali b{ font-family:var(--song); color:var(--ink); }

/* 章首块（随原文同页起，不再独占页） */
.chapter{ break-before:page; }
.ch-head{ margin-bottom:7mm; }
.ch-num{ font-family:var(--song); font-size:9.5pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:4mm; }
.ch-title{ font-family:var(--song); font-weight:900; font-size:22pt; letter-spacing:.2em;
  color:var(--ink); margin-bottom:4mm; line-height:1.4; }
.ch-rule{ display:flex; align-items:center; gap:3mm; margin-bottom:5mm; }
.ch-rule i{ width:36mm; height:.5pt; background:var(--rule); }
.ch-rule b{ width:2.4mm; height:2.4mm; background:var(--cinnabar); transform:rotate(45deg); }
.ch-gist{ padding:3.6mm 4.6mm; background:rgba(158,47,35,.055); border-left:1pt solid var(--cinnabar);
  font-size:9.8pt; line-height:1.95; color:var(--ink); text-align:justify; margin-bottom:2mm; }
.ch-gist b{ font-family:var(--song); font-size:8.5pt; letter-spacing:.35em; color:var(--cinnabar); margin-right:2.4mm; }

/* 原文 */
p.yw{ font-size:12.5pt; line-height:2.3; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:4.5mm; }
.xuzhu{ font-size:9.8pt; line-height:1.95; color:var(--ink2); text-align:justify;
  margin:-1mm 0 4.5mm; break-inside:avoid; }
.xuzhu .xtag{ display:inline-block; font-family:var(--song); font-size:9.2pt; font-weight:700; color:var(--cinnabar);
  border:.6pt solid var(--cinnabar); border-radius:.8mm; padding:0 1.8mm; margin-right:2.2mm; }

/* 白话 */
.baihua p{ font-size:10.5pt; line-height:2.1; text-align:justify; color:var(--ink2); margin-bottom:4mm; }

/* 术语卡 */
.kwcards{ display:grid; grid-template-columns:1fr 1fr; gap:4.6mm; margin-bottom:2mm; }
.kwcard{ border:.6pt solid var(--rule); background:#FBF7EC; padding:4.2mm 4.6mm; break-inside:avoid; }
.kwcard .kt{ display:inline-block; font-family:var(--song); font-weight:700; font-size:9.5pt;
  color:#F6EFDD; background:var(--ink2); padding:.4mm 2.6mm; margin-bottom:2mm; letter-spacing:.15em; }
.kwcard p{ font-size:8.8pt; line-height:1.9; color:var(--ink2); text-align:justify; }

/* 今人按语 */
.qishi{ border:.7pt solid var(--rule); padding:4.6mm 5.4mm; background:#FBF7EC;
  break-inside:avoid; margin-bottom:2mm; }
.qishi .qt{ font-family:var(--song); font-size:9pt; letter-spacing:.42em; color:var(--cinnabar); margin-bottom:2.6mm; }
.qishi p{ font-size:9.8pt; line-height:2.0; text-align:justify; color:var(--ink2); }
.qishi .ask{ font-family:var(--kai); font-size:10.5pt; color:var(--cinnabar); }

/* 卷隔页 */
.vol-head{ break-before:page; text-align:center; padding-top:70mm; }
.vol-head .vt{ font-family:var(--song); font-weight:900; font-size:30pt; letter-spacing:.55em; color:var(--ink); }
.vol-head .vs{ margin-top:6mm; font-size:10pt; letter-spacing:.3em; color:var(--note); }

/* 书影 */
.plate{ text-align:center; break-inside:avoid; margin:6mm 0; }
.plate img{ max-width:100%; max-height:168mm; width:auto; border:.7pt solid var(--rule); padding:2.4mm; background:#FDFBF4; }
figcaption{ font-size:8pt; color:var(--note); margin-top:2.2mm; text-align:center; }
figcaption .ft{ font-family:var(--song); font-weight:700; font-size:9pt; letter-spacing:.18em; color:var(--ink); }
figcaption .ft i{ font-style:normal; color:var(--cinnabar); margin-right:2mm; }

/* 总目 */
.toc-block{ break-before:page; }
.toc-cols{ column-count:2; column-gap:9mm; }
.toc-item{ font-size:9pt; line-height:1.95; color:var(--ink2); break-inside:avoid; }
.toc-item b{ font-family:var(--song); color:var(--cinnabar); margin-right:2mm; }

/* 跋 */
.colophon{ break-before:page; text-align:center; padding-top:40mm; }
.colophon p{ text-align:justify; font-size:10pt; line-height:2.2; color:var(--ink2);
  margin:6mm 6mm 0; text-indent:0; }
.colophon .end{ margin-top:14mm; font-size:10pt; letter-spacing:.7em; color:var(--cinnabar); }
.colophon .meta{ margin-top:10mm; font-size:7.5pt; letter-spacing:.3em; color:var(--note); line-height:2; }
'''

out_name = 'qtb_sample.html' if SAMPLE else 'qtb_full.html'
html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>窮通寶鑑箋注</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, out_name), 'w', encoding='utf-8').write(html)
print(out_name, round(os.path.getsize(os.path.join(ROOT, out_name)) / 1024 / 1024, 1), 'MB')
print('BOOK DONE' if not SAMPLE else 'SAMPLE DONE')

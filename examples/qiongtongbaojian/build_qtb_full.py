#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《窮通寶鑑箋注》全书生成器
数据：/tmp/qtb_sections.json（113 节，源自排印整理本）
产出：qtb_full.html（渲染 PDF）+ 窮通寶鑑箋注-全书.epub
体例：原文/徐乐吾评注 = 繁体；白话/术语/今人按语 = 简体。
"""
import re, os, json, datetime, uuid, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SECS = json.load(open('/tmp/qtb_sections.json', encoding='utf-8'))

from opencc import OpenCC
cc = OpenCC('s2t')
ENT = {'&ldquo;': '「', '&rdquo;': '」', '&lsquo;': '『', '&rsquo;': '』',
       '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&nbsp;': ' ',
       '&ircquo;': '', '&mdash;': '——'}

def clean_text(t):
    for k, v in ENT.items():
        t = t.replace(k, v)
    return re.sub(r'&[a-zA-Z#0-9]{1,8};', '', t)

def to_trad(t):
    return cc.convert(clean_text(t))

def hanzi(s):
    return ''.join(c for c in s if '\u4e00' <= c <= '\u9fff')

def esc(t):
    return re.sub(r'\s+', ' ', clean_text(t)).strip()

def norm_quotes(s):
    """成对直角引号化：'X' → 「X」"""
    out, open_q = [], True
    for c in s:
        if c == '"':
            out.append('「' if open_q else '」'); open_q = not open_q
        else:
            out.append(c)
    return ''.join(out)

def split_quotes(t):
    return norm_quotes(t)

GANS = ['甲木', '乙木', '丙火', '丁火', '戊土', '己土', '庚金', '辛金', '壬水', '癸水']

NUM_CN = '一二三四五六七八九十'
VOL_DESC = ['甲木总论及正月至十二月甲木', '正月至十二月乙木', '正月至十二月丙火', '正月至十二月丁火', '正月至十二月戊土', '正月至十二月己土', '正月至十二月庚金', '正月至十二月辛金', '正月至十二月壬水', '正月至十二月癸水']
def vol_of(title):
    for i, g in enumerate(GANS):
        if g in title:
            return i, f'卷{NUM_CN[i]} · 論{g}'
    return None, None

def paras_of(t):
    return [re.sub(r'\s+', '', p) for p in t.split('\n') if re.sub(r'\s+', '', p)]

def first_sent(t, cap=90):
    s = re.split(r'[。；]', re.sub(r'\s+', '', t))[0]
    return s[:cap]

# ---------------- 章节生成 ----------------


TERM = re.compile(r'[。？！」"]$')

def merge_softwrap(lines):
    """无句末标点的行视为软换行，并入前段；返回段落列表。"""
    paras, buf = [], ''
    for l in lines:
        l = re.sub(r'\s+', '', l)
        if not l:
            continue
        buf += l
        if TERM.search(buf):
            paras.append(buf); buf = ''
    if buf:
        paras.append(buf)
    return paras

def split_xu(paras):
    """按「徐乐吾曰」切分经文段与徐注段。"""
    out = []
    for p in paras:
        if p.startswith('徐乐吾曰'):
            out.append(('xu', re.sub(r'^徐乐吾曰[:：]?', '', p)))
        elif '徐乐吾曰' in p:
            pre, post = p.split('徐乐吾曰', 1)
            if pre:
                out.append(('main', pre))
            out.append(('xu', post))
        else:
            out.append(('main', p))
    return out

def xu_para(p):
    """徐乐吾曰 评注块"""
    body = re.sub(r'^徐乐吾曰[:：]?', '', p).strip()
    return f'<div class="xuzhu"><span class="xtag">徐注</span>{esc(body)}</div>'

def chapter_html(n):
    s = SECS[str(n)]
    vi, vol = vol_of(s['title'])
    vol_label = f' · {vol}' if vol else ''
    t = to_trad(s['title'])
    yparas = split_xu(merge_softwrap(s['yuanwen'].split('\n')))
    out = []
    # 章首（固定页）
    out.append(f'<section class="page ch-head">'
               f'<div class="ch-num">第 {n} 节{vol_label}</div>'
               f'<h2 class="ch-title">{esc(to_trad(s["title"]))}</h2>'
               f'<div class="ch-rule"><i></i><b></b><i></i></div>'
               f'<div class="ch-gist"><b>提要</b>{esc(first_sent(s["baihua"], 110))}。</div>'
               f'</section>')
    # 原文（流式，另起新页；徐注随文缩排）
    out.append('<div class="flow-sec">'
               '<div class="kicker">原文</div><h3 class="sec">窮通寶鑑原文</h3>'
               '<div class="sec-sub">繁体迻录；「徐注」为徐乐吾评注，随文附见。</div>'
               '<div class="yw">')
    for kind, p in yparas:
        if kind == 'xu':
            out.append(xu_para(to_trad(p)))
        else:
            out.append(f'<p class="yw-main">{esc(split_quotes(to_trad(p)))}</p>')
    out.append('</div></div>')
    # 白话（流式续排）
    out.append('<div class="flow-sec">'
               '<div class="kicker">今译</div><h3 class="sec">白话通释</h3>'
               '<div class="baihua">')
    for p in merge_softwrap(s['baihua'].split('\n')):
        out.append(f'<p>{esc(split_quotes(p))}</p>')
    out.append('</div></div>')
    # 术语卡 + 今人按语（流式续排）
    kws = re.findall(r'([^\n：]{2,10})：([^\n]+)', s['kw'])
    qishi = merge_softwrap(s['qishi'].split('\n'))
    if kws or qishi:
        out.append('<div class="flow-sec">'
                   '<div class="kicker">笺释</div><h3 class="sec">术语与按语</h3>')
        if kws:
            out.append('<div class="kwcards">')
            for kt, kv in kws:
                out.append(f'<div class="kwcard"><span class="kt">{esc(kt)}</span>'
                           f'<p>{esc(split_quotes(kv))}</p></div>')
            out.append('</div>')
        if qishi:
            out.append('<div class="qishi"><div class="qt">今人按语</div>')
            for j, p in enumerate(qishi):
                cls = ' class="ask"' if ('？' in p and j == len(qishi) - 1) else ''
                out.append(f'<p{cls}>{esc(split_quotes(p))}</p>')
            out.append('</div>')
        out.append('</div>')
    out.append('</section>')
    return '\n'.join(out)

# ---------------- 组装 ----------------
base = open(os.path.join(ROOT, 'qtb_ch1.html'), encoding='utf-8').read()
style = re.search(r'<style>(.*?)</style>', base, re.S).group(1)

FLOW_CSS = '''
  @page{ size:185mm 260mm; margin:20mm 20mm 16mm; }
  body{ background:var(--paper); }
  .page{ page-break-after:always; }
  .ch-head{ padding-top:44mm; }
  .ch-num{ font-family:var(--song); font-size:10pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:6mm; }
  .ch-title{ font-family:var(--song); font-weight:900; font-size:25pt; letter-spacing:.22em; color:var(--ink); margin-bottom:7mm; }
  .ch-rule{ display:flex; align-items:center; gap:3mm; margin-bottom:9mm; }
  .ch-rule i{ width:40mm; height:.5pt; background:var(--rule); }
  .ch-rule b{ width:2.4mm; height:2.4mm; background:var(--cinnabar); transform:rotate(45deg); }
  .flow-sec{ break-before:page; }
  body > .vol-head ~ .page{ break-before:page; }
  .yw-main{ font-size:13pt; line-height:2.35; letter-spacing:.06em; text-align:justify; color:var(--ink); margin-bottom:5mm; }
  .xuzhu{ font-size:9.8pt; line-height:1.95; color:var(--ink2); text-align:justify;
          margin:-2mm 0 5mm 8mm; padding-left:4mm; border-left:1pt solid var(--rule); }
  .xuzhu .xtag{ display:inline-block; font-family:var(--song); font-size:7.5pt; color:var(--cinnabar);
                border:.5pt solid var(--cinnabar); border-radius:.8mm; padding:0 1.6mm; margin-right:2mm; }
  .baihua p{ font-size:10.5pt; line-height:2.1; text-align:justify; color:var(--ink2); margin-bottom:4mm; }
  .kwcards{ display:grid; grid-template-columns:1fr 1fr; gap:4.6mm; }
  .kwcard{ border:.6pt solid var(--rule); background:#FBF7EC; padding:4.4mm 4.8mm; }
  .kwcard .kt{ display:inline-block; font-family:var(--song); font-weight:700; font-size:10pt;
      color:#F6EFDD; background:var(--ink2); padding:.4mm 2.6mm; margin-bottom:2.2mm; letter-spacing:.15em; }
  .kwcard p{ font-size:8.8pt; line-height:1.9; color:var(--ink2); text-align:justify; }
  .qishi{ border:.7pt solid var(--rule); padding:5mm 6mm; background:#FBF7EC; margin-top:4mm; }
  .qishi .qt{ font-family:var(--song); font-size:9pt; letter-spacing:.42em; color:var(--cinnabar); margin-bottom:3mm; }
  .qishi p{ font-size:9.8pt; line-height:2.0; text-align:justify; color:var(--ink2); }
  .qishi .ask{ font-family:var(--kai); font-size:10.5pt; color:var(--cinnabar); }
  h3.sec{ break-after:avoid; }
  .toc-page{ page-break-after:always; }
  .toc-cols{ column-count:2; column-gap:9mm; }
  .toc-item{ font-size:9pt; line-height:1.95; color:var(--ink2); break-inside:avoid; }
  .toc-item b{ font-family:var(--song); color:var(--cinnabar); margin-right:2mm; }
  .vol-head{ page-break-before:always; page-break-after:always; text-align:center; padding-top:60mm; }
  .vol-head .vt{ font-family:var(--song); font-weight:900; font-size:30pt; letter-spacing:.6em; color:var(--ink); }
  .vol-head .vs{ margin-top:6mm; font-size:10pt; letter-spacing:.3em; color:var(--note); }
'''

body = []
# 封面/扉页/凡例：取自样章（封面原样，扉页与凡例改全书口径）
secs_html = re.findall(r'<section class="page[^"]*">(.*?)</section>', base, re.S)
cover, fanye, fali, shuying = secs_html[0], secs_html[1], secs_html[2], secs_html[3]
fali = fali.replace('全书按十天干分卷、以十二月令立目；本册为第一章样章。',
                    '全书按十天干分卷（卷一論甲木至卷十論癸水），以十二月令立目，凡一百一十三节。')
body.append(f'<section class="page cover">{cover}</section>')
body.append(f'<section class="page titlepage">{fanye}</section>')
body.append(f'<section class="page">{fali}</section>')
# 卷首书影（第一章样章内的书影页原样复用）
body.append(f'<section class="page">{shuying}</section>')
# 总目
toc_items = ''.join(f'<p class="toc-item"><b>{n:03d}</b>{esc(SECS[str(n)]["title"])}</p>'
                    for n in range(1, 114))
for i in range(0, 113, 40):
    chunk = ''.join(list(re.findall(r'<p class="toc-item">.*?</p>', toc_items, re.S))[i:i+40])
    body.append(f'<section class="page toc-page">'
                f'<div class="rh"><span>窮通寶鑑箋注</span><span>总目</span></div>'
                f'<div style="margin-top:9mm"><div class="kicker hollow">总目</div><h3 class="sec">一百一十三节</h3>'
                f'<div class="sec-sub">按十天干分卷，卷内以月令立目。</div></div>'
                f'<div class="toc-cols">{chunk}</div></section>')
# 卷隔页 + 各节
vol_counts = {}
last_vi = None
for n in range(1, 114):
    vi_, _ = vol_of(SECS[str(n)]['title'])
    if vi_ is None:
        vi_ = last_vi
    if vi_ is not None:
        vol_counts[vi_] = vol_counts.get(vi_, 0) + 1
    last_vi = vi_
last_vol = None
ch1_pages = '\n'.join(f'<section class="page">{s}</section>' for s in secs_html[4:11])
body.append(ch1_pages)
for n in range(2, 114):
    s = SECS[str(n)]
    vi, vol = vol_of(s['title'])
    if vi is None:
        vi, vol = last_vol, None
    if vi != last_vol:
        num_cn = '一二三四五六七八九十'[vi]
        body.append(f'<section class="vol-head"><div class="vt">卷{num_cn} · 論{GANS[vi]}</div>'
                    f'<div class="vs">凡{vol_counts[vi]}节</div></section>')
        last_vol = vi
    body.append(chapter_html(n))
# 跋
body.append('''<section class="chapter">
  <div style="text-align:center; padding-top:40mm;">
    <div class="kicker" style="justify-content:center">跋</div>
    <p style="font-size:10.5pt; line-height:2.2; color:var(--ink2); text-align:justify; margin:8mm 4mm 0;">《窮通寶鑑》原名《欄江網》，一名《造化元鑰》，余春台编次，徐乐吾评注；以十天干配十二月令，专论调候。本书原文与评注以排印整理本为底、参风陵文库藏清写刻本对读；白话、术语笺释与今人按语从排印本辑录，体例详见凡例。</p>
    <div style="margin-top:14mm; font-size:10pt; letter-spacing:.7em; color:var(--cinnabar);">全 書 終</div>
    <div style="margin-top:10mm; font-size:7.5pt; letter-spacing:.3em; color:var(--note); line-height:2;">穷通宝鉴笺注 · 全书一百一十三节<br/>十六开本（185×260mm）· 编纂参考：识典古籍 / 中华古籍智慧化服务平台 / 风陵文库藏清写刻本</div>
  </div></section>''')

html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>窮通寶鑑箋注</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{style}{FLOW_CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, 'qtb_full.html'), 'w', encoding='utf-8').write(html)
print('qtb_full.html:', round(os.path.getsize(os.path.join(ROOT, 'qtb_full.html')) / 1024 / 1024, 1), 'MB')
print('BOOK DONE')

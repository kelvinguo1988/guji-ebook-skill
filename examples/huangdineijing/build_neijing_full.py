#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》全书生成器 —— 81 篇 / 元刻十二卷格局 / 新系列版式
数据：parse_suwen.py → book_data.json（四部叢刊本经注 + 殆知阁段落锚）
内容：content_nj.py（章旨/白话/术语） + 卷首书影 assets/
产出：neijing_full.html（Edge 渲染 PDF）"""
import re, os, json, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from content_nj import NJ, TITLES

BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))
CN_NUM = '一二三四五六七八九十'

VOLS = {1: (1, 7), 2: (8, 16), 3: (17, 20), 4: (21, 30), 5: (31, 38), 6: (39, 45),
        7: (46, 55), 8: (56, 61), 9: (62, 67), 10: (68, 70), 11: (71, 74), 12: (75, 81)}
VOL_FIRST = {1: '上古天真論', 2: '靈蘭祕典論', 3: '脈要精微論', 4: '經脈別論', 5: '熱論',
             6: '舉痛論', 7: '病能論', 8: '皮部論', 9: '調經論', 10: '六微旨大論',
             11: '六元正紀大論', 12: '著至教論'}
def cnum(n):
    d = CN_NUM[:9]
    if n <= 9: return d[n-1]
    if n == 10: return '十'
    if n < 20: return '十' + d[n-11]
    t = {20:'二十',30:'三十',40:'四十',50:'五十',60:'六十',70:'七十',80:'八十'}[n//10*10]
    ones = n % 10
    return t + (d[ones-1] if ones else '')

def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

def merge_kinds(paras):
    """合并相邻同类 segment；经文 run 并为整段文本"""
    out = []
    for pp in paras:
        merged = []
        for k, t in pp:
            t = t.strip()
            if not t: continue
            if merged and merged[-1][0] == k and k in ('p', 'zhu'):
                merged[-1] = (k, merged[-1][1] + t)
            else:
                merged.append((k, t))
        out.append(merged)
    return out

CSS = '''
:root{
  --paper:#F8F4E9; --ink:#2C2824; --ink2:#4E4738; --note:#8A8069;
  --cinnabar:#9E2F23; --dark:#1F2B38; --dark2:#16202B;
  --rule:#C9B98A; --rule-soft:#DDD3B4; --gold:#B79B5E;
  --song:"Noto Serif TC","Songti SC",serif;
  --kai:"LXGW WenKai","Noto Serif TC",serif;
}
*{ margin:0; padding:0; box-sizing:border-box; }
html,body{ background:#FFFFFF; }
body{ font-family:var(--song); color:var(--ink); font-kerning:normal; }

@page{ size:185mm 260mm; margin:20mm 20mm 17mm; }
@page :first{ margin:0; }
@page full{ size:185mm 260mm; margin:0; }

/* 封面 */
.cover-page{ width:185mm; height:260mm; position:relative; overflow:hidden;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%);
  color:#EDE3C8; page-break-after:always; }
.cover-page .frame{ position:absolute; inset:7mm; border:.6pt solid rgba(183,155,94,.55);
  outline:1.4pt double rgba(183,155,94,.28); outline-offset:1.8mm; }
.cover-page .main-title{ position:absolute; top:19mm; right:23mm; writing-mode:vertical-rl;
  font-family:var(--kai); font-weight:700; font-size:50pt; letter-spacing:.22em; line-height:1.15; }
.cover-page .sub-title{ position:absolute; top:27mm; right:80mm; writing-mode:vertical-rl;
  font-size:13.5pt; letter-spacing:.5em; color:#C8B98D; }
.cover-page .editions{ position:absolute; top:24mm; left:26mm; writing-mode:vertical-rl;
  font-size:9.5pt; letter-spacing:.34em; color:rgba(200,185,141,.85); height:120mm; }
.cover-page .quote{ position:absolute; bottom:36mm; left:26mm; writing-mode:vertical-rl;
  font-size:9pt; letter-spacing:.3em; color:rgba(200,185,141,.6); height:70mm; }
.cover-page .seal{ position:absolute; bottom:23mm; right:23mm; width:16mm; height:16mm;
  background:var(--cinnabar); color:#F6EBD9; display:flex; align-items:center; justify-content:center;
  writing-mode:vertical-rl; text-orientation:upright; font-size:8.2pt; letter-spacing:.14em;
  line-height:1.25; border-radius:1mm; }
.cover-page .foot{ position:absolute; bottom:11mm; left:0; right:0; text-align:center;
  font-size:7.5pt; letter-spacing:.5em; color:rgba(200,185,141,.55); }

.titlepage{ page-break-after:always; text-align:center; padding-top:32mm; }
.titlepage .big{ writing-mode:vertical-rl; font-family:var(--song); font-weight:900;
  font-size:36pt; letter-spacing:.3em; height:108mm; display:inline-block; }
.titlepage .verline{ margin-top:11mm; font-size:11.5pt; letter-spacing:.4em; color:var(--ink2); }
.titlepage .rule-orn{ margin:10mm auto 8mm; display:flex; align-items:center; justify-content:center; gap:3mm; }
.titlepage .rule-orn i{ width:26mm; height:.5pt; background:var(--rule); }
.titlepage .rule-orn b{ width:2.6mm; height:2.6mm; background:var(--cinnabar); transform:rotate(45deg); }
.titlepage .note-block{ text-align:center; font-size:9.5pt; line-height:2.15; color:var(--ink2); letter-spacing:.1em; }

h2.sec{ font-family:var(--song); font-weight:700; font-size:13.5pt; letter-spacing:.35em;
  color:var(--ink); margin:9mm 0 3.5mm; break-after:avoid; }
h3.sec{ font-family:var(--song); font-weight:700; font-size:11.5pt; letter-spacing:.35em;
  color:var(--ink); margin:8mm 0 3mm; break-after:avoid; }
p.sec-note{ font-size:8.6pt; color:var(--note); letter-spacing:.1em; margin:0 0 4mm; break-after:avoid; }
.kicker{ font-family:var(--song); font-size:8pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:3mm; }
.fali li{ list-style:none; position:relative; padding-left:11mm; margin-bottom:5.2mm;
  font-size:10pt; line-height:1.95; text-align:justify; }
.fali li .no{ position:absolute; left:0; top:.4mm; width:6.4mm; height:6.4mm;
  border:.6pt solid var(--cinnabar); color:var(--cinnabar); border-radius:50%;
  font-family:var(--song); font-size:8pt; display:flex; align-items:center; justify-content:center; }
.fali b{ font-family:var(--song); color:var(--ink); }

.plates{ display:grid; grid-template-columns:1fr 1fr; gap:5mm; }
.plate{ text-align:center; break-inside:avoid; margin:0 0 2mm; }
.plate img{ max-width:100%; max-height:96mm; width:auto; border:.7pt solid var(--rule); padding:2mm; background:#FDFBF4; }
figcaption{ font-size:7.8pt; color:var(--note); margin-top:1.8mm; text-align:center; }
figcaption .ft{ font-family:var(--song); font-weight:700; font-size:8.6pt; letter-spacing:.14em; color:var(--ink); }
figcaption .ft i{ font-style:normal; color:var(--cinnabar); margin-right:1.6mm; }
figcaption .fs{ display:block; margin-top:1mm; font-size:7.4pt; color:var(--note); letter-spacing:.04em; }

/* 卷隔页 */
.vol-head{ page:full; break-before:page; text-align:center; padding-top:66mm; width:185mm; height:260mm; }
.vol-head .vt{ font-family:var(--song); font-weight:900; font-size:28pt; letter-spacing:.5em; color:var(--ink); }
.vol-head .vs{ margin-top:6mm; font-size:9.5pt; letter-spacing:.28em; color:var(--note); }
.vol-head .rule{ display:flex; align-items:center; justify-content:center; gap:3mm; margin:7mm 0; }
.vol-head .rule i{ width:34mm; height:.5pt; background:var(--rule); }
.vol-head .rule b{ width:2.4mm; height:2.4mm; background:var(--cinnabar); transform:rotate(45deg); }
.vol-head .pianlist{ display:inline-block; text-align:left; margin-top:2mm;
  font-size:9pt; line-height:2.0; letter-spacing:.12em; color:var(--ink2); }
.vol-head .pianlist b{ font-family:var(--song); color:var(--cinnabar); margin-right:2mm; }

/* 篇 */
.pian{ break-before:page; }
.pian-head{ margin-bottom:6mm; }
.pian .kicker{ margin-bottom:3.5mm; }
.pian .ti{ font-family:var(--song); font-weight:900; font-size:19pt; letter-spacing:.18em;
  color:var(--ink); margin-bottom:4mm; }
.pian .rule{ display:flex; align-items:center; gap:3mm; margin-bottom:5mm; }
.pian .rule i{ width:30mm; height:.5pt; background:var(--rule); }
.pian .rule b{ width:2.2mm; height:2.2mm; background:var(--cinnabar); transform:rotate(45deg); }
.ch-gist{ padding:3.6mm 4.6mm; background:rgba(158,47,35,.055); border-left:1pt solid var(--cinnabar);
  font-size:9.8pt; line-height:1.95; color:var(--ink); text-align:justify; }
.ch-gist b{ font-family:var(--song); font-size:8.5pt; letter-spacing:.35em; color:var(--cinnabar); margin-right:2.4mm; }

p.yw{ font-size:12pt; line-height:2.25; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:4.2mm; }
.xuzhu{ font-size:9.6pt; line-height:1.92; color:var(--ink2); text-align:justify;
  margin:-1mm 0 4.2mm; break-inside:avoid; }
.xuzhu .xtag{ display:inline-block; font-family:var(--song); font-size:9.2pt; font-weight:700; color:var(--cinnabar);
  border:.6pt solid var(--cinnabar); border-radius:.8mm; padding:0 1.8mm; margin-right:2.2mm; }
.xuzhu.jiao .xtag{ color:#775A28; border-color:#775A28; }

.baihua p{ font-size:10.2pt; line-height:2.05; text-align:justify; color:var(--ink2); margin-bottom:3.8mm; }
.kwcards{ display:grid; grid-template-columns:1fr 1fr; gap:4.4mm; margin-bottom:2mm; }
.kwcard{ border:.6pt solid var(--rule); background:#FBF7EC; padding:4mm 4.4mm; break-inside:avoid; }
.kwcard .kt{ display:inline-block; font-family:var(--song); font-weight:700; font-size:9.3pt;
  color:#F6EFDD; background:var(--ink2); padding:.4mm 2.6mm; margin-bottom:1.8mm; letter-spacing:.14em; }
.kwcard p{ font-size:8.7pt; line-height:1.88; color:var(--ink2); text-align:justify; }

.toc-block{ break-before:page; }
.toc-cols{ column-count:2; column-gap:9mm; }
.toc-item{ font-size:9pt; line-height:1.95; color:var(--ink2); break-inside:avoid; }
.toc-item b{ font-family:var(--song); color:var(--cinnabar); margin-right:2mm; }

.endpage{ page:full; break-before:page; text-align:center; padding-top:74mm;
  width:185mm; height:260mm;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%); }
.endpage .kicker{ color:#C8B98D; }
.endpage p{ text-align:justify; font-size:10pt; line-height:2.2; color:#CFC5AC; margin:6mm 32mm 0; }
.endpage .end{ margin-top:13mm; font-size:10pt; letter-spacing:.7em; color:#C8B98D; }
.endpage .meta{ margin-top:9mm; font-size:7.5pt; letter-spacing:.3em; color:rgba(200,185,141,.62); line-height:2; }
'''

def pian_html(n, vol):
    e = BOOK[str(n)]
    c = NJ.get(n, {})
    title = e['title']
    zz = c.get('zz', '')
    out = [f'<section class="pian">',
           f'<div class="pian-head">',
           f'<div class="kicker">素問 · 卷之{cnum(vol)} · 篇 第 {cnum(n)}</div>',
           f'<div class="ti">{esc(title)}</div>',
           f'<div class="rule"><i></i><b></b><i></i></div>']
    if zz:
        out.append(f'<div class="ch-gist"><b>章旨</b>{esc(zz)}</div>')
    out.append('</div>')
    out.append('<h3 class="sec">原文</h3>')
    out.append('<p class="sec-note">繁体大字；「注」为王冰注，「校正」为新校正语，随文附见。</p>')
    for pp in merge_kinds(e['paras']):
        for k, t in pp:
            t = esc(t)
            if k == 'p':
                out.append(f'<p class="yw">{t}</p>')
            elif k == 'zhu':
                out.append(f'<div class="xuzhu"><span class="xtag">注</span>{t}</div>')
            else:
                x = t
                if x.startswith('新校正云'):
                    x = x[len('新校正云'):].lstrip('　 ')
                out.append(f'<div class="xuzhu jiao"><span class="xtag">校正</span>{x}</div>')
    out.append('<h3 class="sec">白话通释</h3><div class="baihua">')
    for p in c.get('by', []):
        out.append(f'<p>{esc(p)}</p>')
    out.append('</div>')
    kws = c.get('kw', [])
    if kws:
        out.append('<h3 class="sec">术语笺释</h3><div class="kwcards">')
        for kt, kv in kws:
            out.append(f'<div class="kwcard"><span class="kt">{esc(kt)}</span><p>{esc(kv)}</p></div>')
        out.append('</div>')
    out.append('</section>')
    return '\n'.join(out)

def vol_head(vol):
    a, b = VOLS[vol]
    items = ''.join(f'<div><b>{n:02d}</b>{esc(BOOK[str(n)]["title"])}</div>'
                    for n in range(a, b+1))
    return (f'<section class="vol-head"><div class="vt">卷之{cnum(vol)}</div>'
            f'<div class="rule"><i></i><b></b><i></i></div>'
            f'<div class="vs">起{esc(VOL_FIRST[vol])} · 凡{b-a+1}篇</div>'
            f'<div class="pianlist">{items}</div></section>')

body = []
body.append('''<section class="cover-page">
  <div class="frame"></div>
  <div class="main-title">黃帝內經素問</div>
  <div class="sub-title">王冰注 · 新校正 · 白話通釋</div>
  <div class="editions">元至元古林書堂刻本葉面對讀 · 金刻本參校 · 全八十一篇</div>
  <div class="quote">法於陰陽　和於術數</div>
  <div class="seal">上古天真</div>
  <div class="foot">素問 · 子部醫家類</div>
</section>''')
body.append('''<section class="titlepage">
  <div class="big">黃帝內經素問</div>
  <div class="verline">全八十一篇 · 元刻十二卷格局</div>
  <div class="rule-orn"><i></i><b></b><i></i></div>
  <div class="note-block">
    唐 王冰 注　宋 林億等校正<br>
    經注錄文從《重廣補注黃帝內經素問》通行本系統<br>
    卷次從元至元古林書堂刻本總目　葉面對讀隨卷
  </div>
</section>''')
body.append('''<section class="fanli">
  <h2 class="sec">凡例</h2>
  <ul class="fali">
    <li><b>一、底本与录文。</b>经注录文以<b>《重廣補注黃帝內經素問》通行本系统</b>（王冰注、新校正语俱全）为底；卷次、分卷与<b>元至元五年胡氏古林書堂刻本《新刊補註釋文黃帝內經素問》</b>总目相从（元本併王冰二十四卷为十二卷），篇目次第以元刻总目叶为据。</li>
    <li><b>二、叶面对读。</b>元刻卷之一、三、五、十诸卷端叶书影列于卷首；首叶卷端题署、篇题圈号、起首经文、王冰注引《史记》诸条已与叶面逐字核验，朱圈句读、「成而登天」下墨钉等版刻特征记入版刻对读。</li>
    <li><b>三、参校本。</b>金刻本《黃帝內經素問》（國家圖書館藏，存卷三至五、十一至十八、二十凡十三卷）为参校；其卷一已佚，卷一诸篇无金刻可对，卷三以下同览两刻可互勘。</li>
    <li><b>四、用字体例。</b>经文、王冰注、新校正语用繁体；凡例、章旨、白话通释、术语笺释用简体。叶面异体字（如「眞」「寳」「隂」）录文一律改从通行正字。</li>
    <li><b>五、白话通释为全篇今译节要。</b>长篇如运气七篇者撮其大要；术语笺释随篇立卡，取一篇之要目。</li>
    <li><b>六、亡篇。</b>刺法論、本病論兩篇宋臣已言亡，今本所传为后人补托，仍依元刻总目附卷之十一，篇名下注明。</li>
  </ul>
</section>''')
body.append('''<section class="shuying">
  <h2 class="sec">卷首书影</h2>
  <p class="sec-note">底本与参校本的版刻原貌：元刻四帧卷端叶、金刻一帧端叶。</p>
  <div class="plates">
    <figure class="plate"><img src="assets/yuan_juan1.png" alt=""/>
      <figcaption><span class="ft"><i>图一</i>元刻《素問》卷之一首叶</span>
      <span class="fs">上古天真論篇第一 · 朱圈句读 · 「成而登天」下墨钉</span></figcaption></figure>
    <figure class="plate"><img src="assets/jin_juan3.png" alt=""/>
      <figcaption><span class="ft"><i>图二</i>金刻本《素問》卷第三端叶</span>
      <span class="fs">國家圖書館藏 · 存十三卷（卷三起）</span></figcaption></figure>
    <figure class="plate"><img src="assets/yuan_juan3.png" alt=""/>
      <figcaption><span class="ft"><i>图三</i>元刻《素問》卷之三端叶</span>
      <span class="fs">脈要精微論起 · 胡氏古林書堂刻本</span></figcaption></figure>
    <figure class="plate"><img src="assets/yuan_juan5.png" alt=""/>
      <figcaption><span class="ft"><i>图四</i>元刻《素問》卷之五端叶</span>
      <span class="fs">熱論起</span></figcaption></figure>
    <figure class="plate"><img src="assets/yuan_juan10.png" alt=""/>
      <figcaption><span class="ft"><i>图五</i>元刻《素問》卷之十端叶</span>
      <span class="fs">六微旨大論篇第六十八起 · 運氣諸大論</span></figcaption></figure>
  </div>
</section>''')
body.append('''<section class="bankan" style="border:.7pt solid var(--rule); background:#FBF7EC; padding:5mm 5.6mm; margin:6mm 0;">
  <h3 class="sec" style="margin-top:0">版刻对读</h3>
  <p class="sec-note" style="margin-bottom:2mm">元刻与金刻两刻实察记录，凡未经叶面核实者不出校。</p>
  <p style="font-size:9.6pt; line-height:2.0; text-align:justify; color:var(--ink2)">元刻卷之一首叶卷端题「新刊補註釋文黃帝內經素問卷之一」，次行题「啓玄子次註　林億孫奇高保衡等奉勅校正　孫兆重改誤」；篇题冠以圈号，经文加朱圈句读。「成而登天」句下接「天師曰」处有墨钉一方，通行本此处为「迺問於」三字连读，所代何字待考。「昔在黃帝」句下王冰注引《史記》黄帝事迹，与通行本注文相合，可证元刻注即王冰注旧文。金刻本每半叶十三行、行二十二字、注小字三十字、白口四周双边，存卷三至五、十一至十八、二十；其卷一已佚，故卷一诸篇以元刻为唯一叶面依据，卷三以下两刻并观可互勘异文。</p>
</section>''')
# 总目
toc_items = []
for vol in range(1, 13):
    a, b = VOLS[vol]
    toc_items.append(f'<p class="toc-item"><b>卷之{cnum(vol)}</b>（{a:02d}–{b:02d}）起{esc(VOL_FIRST[vol])}</p>')
    for n in range(a, b+1):
        toc_items.append(f'<p class="toc-item"><b>{n:03d}</b>{esc(BOOK[str(n)]["title"])}</p>')
toc_all = ''.join(toc_items)
chunks = re.findall(r'<p class="toc-item">.*?</p>', toc_all, re.S)
for i in range(0, len(chunks), 44):
    body.append(f'<section class="toc-block"><h2 class="sec">总目（{i+1}–{min(i+44, len(chunks))}）</h2>'
                f'<div class="toc-cols">{"".join(chunks[i:i+44])}</div></section>')
# 各卷
for vol in range(1, 13):
    body.append(vol_head(vol))
    a, b = VOLS[vol]
    for n in range(a, b+1):
        body.append(pian_html(n, vol))
# 跋
body.append('''<section class="endpage">
  <div class="kicker" style="justify-content:center">跋</div>
  <p>《黃帝內經素問》八十一篇至此終。經注錄文從通行王冰注本系統，卷次從元至元古林書堂刻本總目；元刻卷端書影隨卷首，版刻對讀記實察所得。白話通釋撮全篇大要，術語箋釋隨篇立卡，皆以便讀者循文會意，非敢代原書之教。</p>
  <div class="end">全 書 終</div>
  <div class="meta">黃帝內經素問 · 全書八十一篇<br/>十六开本（185×260mm）<br/>编纂参考：国家图书馆藏元至元胡氏古林書堂刻本 · 金刻本 · 《重廣補注黃帝內經素問》通行本系统</div>
</section>''')

html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>黃帝內經素問</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, 'neijing_full.html'), 'w', encoding='utf-8').write(html)
print('neijing_full.html', round(os.path.getsize(os.path.join(ROOT, 'neijing_full.html'))/1024/1024, 2), 'MB')

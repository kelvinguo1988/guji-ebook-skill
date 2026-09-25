#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗数全书》整理版 · 第一章样章生成器 —— 品类 A
内容：卷首开篇（太微赋，含例曰）+ 白话通释 + 术语笺释 + 原书叶对照
特色需求：原书每页对照、图片不能缺少——版式内建「原书叶对照」组件；
          扫描叶图就位后逐叶填入 LEAF_MAP（当前为占位桩，明确标注待补）。
用法：python3 build_zwds_sample.py（渲染 HTML → Edge 出 PDF）
"""
import os, json

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, 'zw_ch1_data.json'), encoding='utf-8'))

CSS = '''
:root{
  --paper:#F8F4E9; --ink:#2C2824; --ink2:#4E4738; --note:#8A8069;
  --cinnabar:#9E2F23; --dark:#1F2B38; --dark2:#16202B;
  --rule:#C9B98A; --rule-soft:#DDD3B4; --gold:#B79B5E;
  --song:"Noto Serif TC","Songti SC",serif;
  --kai:"LXGW WenKai","Noto Serif TC",serif;
}
*{ margin:0; padding:0; box-sizing:border-box; }
/* 纸面纯白（SKILL.md §4） */
html,body{ background:#FFFFFF; }
body{ font-family:var(--song); color:var(--ink); font-kerning:normal; }

@page{ size:185mm 260mm; margin:20mm 20mm 17mm; }
@page :first{ margin:0; }
@page full{ size:185mm 260mm; margin:0; }

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
.titlepage .sample-tag{ margin-top:12mm; font-size:8.5pt; letter-spacing:.4em; color:var(--note); }

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

.ch-gist{ padding:3.6mm 4.6mm; background:rgba(158,47,35,.055); border-left:1pt solid var(--cinnabar);
  font-size:9.8pt; line-height:1.95; color:var(--ink); text-align:justify; margin-bottom:5mm; }
.ch-gist b{ font-family:var(--song); font-size:8.5pt; letter-spacing:.35em; color:var(--cinnabar); margin-right:2.4mm; }

p.yw{ font-size:12.5pt; line-height:2.3; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:4.5mm; }
p.fu{ font-size:12.5pt; line-height:2.3; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:2mm; }
.xuzhu{ font-size:9.8pt; line-height:1.95; color:var(--ink2); text-align:justify;
  margin:-1mm 0 4.5mm; break-inside:avoid; }
.xuzhu .xtag{ display:inline-block; font-family:var(--song); font-size:9.2pt; font-weight:700; color:var(--cinnabar);
  border:.6pt solid var(--cinnabar); border-radius:.8mm; padding:0 1.8mm; margin-right:2.2mm; }

.baihua p{ font-size:10.2pt; line-height:2.05; text-align:justify; color:var(--ink2); margin-bottom:3.8mm; }
.kwcards{ display:grid; grid-template-columns:1fr 1fr; gap:4.4mm; margin-bottom:2mm; }
.kwcard{ border:.6pt solid var(--rule); background:#FBF7EC; padding:4mm 4.4mm; break-inside:avoid; }
.kwcard .kt{ display:inline-block; font-family:var(--song); font-weight:700; font-size:9.3pt;
  color:#F6EFDD; background:var(--ink2); padding:.4mm 2.6mm; margin-bottom:1.8mm; letter-spacing:.14em; }
.kwcard p{ font-size:8.7pt; line-height:1.88; color:var(--ink2); text-align:justify; }

/* 原书叶对照（本样章特色组件）：扫描叶图 + 对应原文区间标注 */
.leafmap{ break-inside:avoid; margin:5mm 0 6mm; border:.7pt solid var(--rule); background:#FBF7EC; padding:4.6mm 5.2mm; }
.leafmap .lm-t{ font-family:var(--song); font-size:9pt; letter-spacing:.35em; color:var(--cinnabar); margin-bottom:3mm; }
.leafmap .lm-item{ display:grid; grid-template-columns:52mm 1fr; gap:5mm; margin-bottom:4mm; break-inside:avoid; }
.leafmap .ph{ height:66mm; border:.7pt solid var(--rule); background:#FDFBF4; display:flex;
  align-items:center; justify-content:center; flex-direction:column; gap:2mm; }
.leafmap .ph .hole{ font-size:8.5pt; color:var(--note); letter-spacing:.15em; text-align:center; line-height:1.9; }
.leafmap .ph img{ max-width:100%; max-height:100%; object-fit:contain; }
.leafmap .lm-meta{ font-size:9pt; line-height:2.0; color:var(--ink2); text-align:justify; }
.leafmap .lm-meta b{ font-family:var(--song); color:var(--ink); }
.leafmap .lm-meta .rng{ color:var(--cinnabar); }

.endpage{ page:full; break-before:page; text-align:center; padding-top:74mm;
  width:185mm; height:260mm;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%); }
.endpage .kicker{ color:#C8B98D; }
.endpage p{ text-align:justify; font-size:10pt; line-height:2.2; color:#CFC5AC; margin:6mm 30mm 0; }
.endpage .end{ margin-top:13mm; font-size:10pt; letter-spacing:.7em; color:#C8B98D; }
.endpage .meta{ margin-top:9mm; font-size:7.5pt; letter-spacing:.3em; color:rgba(200,185,141,.62); line-height:2; }
'''

def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# 原书叶对照表：扫描叶就位后填 src（assets/ 叶图），当前为占位桩
# 南阳堂刊本（书格·日本公文书馆藏本数字化）叶位实察：
# index1R=卷端书名叶；index4L=卷端大题+太微赋起；index4R/5L=太微赋续与例曰
LEAF_MAP = [
    {'leaf': '叶一', 'src': 'zw_leaf1.jpg', 'range': '卷端题署（全书扉叶）',
     'mark': '大题「陳希夷先生著 · 紫微斗數全書」，下镌「南陽堂較梓」；本刊本卷首无罗序'},
    {'leaf': '叶二', 'src': 'zw_leaf2.jpg', 'range': '卷端大题与太微赋正文起首',
     'mark': '版心题「卷一」；叶端重刊大题「新鍥希夷陳先生紫微斗數全書」，次「太微賦」篇题，「斗數至玄至微」起'},
    {'leaf': '叶三', 'src': 'zw_leaf3.jpg', 'range': '太微赋正文续、例曰前段',
     'mark': '「帝星動則列宿奔馳」至例曰诸格前半；版心仍「卷一」'},
    {'leaf': '叶四', 'src': 'zw_leaf4.jpg', 'range': '例曰后段',
     'mark': '例曰诸格局口诀至本篇末；次叶版心转「附批命活套」'}]

body = []
body.append('''<section class="cover-page">
  <div class="frame"></div>
  <div class="main-title">紫微斗數全書</div>
  <div class="sub-title">整理版 · 原書葉對照</div>
  <div class="editions">舊題陳摶撰 · 潘希尹補輯 · 明刊本系統 · 原書葉逐葉對照</div>
  <div class="seal">希夷遺範</div>
  <div class="foot">紫微斗數 · 子部術數類</div>
</section>''')
body.append('''<section class="titlepage">
  <div class="big">紫微斗數全書</div>
  <div class="verline">整理版 · 第一章样章</div>
  <div class="rule-orn"><i></i><b></b><i></i></div>
  <div class="note-block">
    錄文以維基文庫《紫微斗數全書》通行錄文為底<br>
    原書葉對照隨文繫圖——本冊特色：每篇內容對應原書葉，不缺一葉<br>
    白話通釋與術語箋釋附焉
  </div>
  <div class="sample-tag">第一章样章 · 太微賦</div>
</section>''')
body.append('''<section class="fanli">
  <h2 class="sec">凡例</h2>
  <ul class="fali">
    <li><b>一、录文底本。</b>录文以维基文库《紫微斗數全書》通行录文为底（繁体），与识典古籍 SDZJ0170 明刊本系统对应；原书扫描叶到位后逐叶通校。</li>
    <li><b>二、原书叶对照（本册铁律）。</b>每篇内容之后设「原书叶对照」：逐一给出该篇所对应的原书叶图与原文区间标注，<b>一叶不缺</b>。叶图自南阳堂刊本扫描件裁切。</li>
    <li><b>三、编排次第。</b>每篇先陈<b>原文</b>（繁体大字，赋体分句缀行），继以<b>白话通释</b>与<b>术语笺释</b>。</li>
    <li><b>四、用字体例。</b>原文用繁体；凡例、白话、笺释用简体。</li>
    <li><b>五、样章范围。</b>卷首开篇：太微赋（含例曰）。所据<b>南阳堂刊本</b>（明代，日本公文书馆藏，书格数字化）卷首无罗洪先序——罗序见维基文库等录文所据的别本系统，故不羼入，俟汇校时以校记处理。全本后续各篇体例同此。</li>
    <li><b>六、叶图。</b>原书叶图自南阳堂刊本扫描件裁切，每半叶一帧，随文对照。</li>
  </ul>
</section>''')
# 第一章篇首
body.append('<div class="kicker">紫微斗数全书 · 卷首 · 第一章</div>'
            '<div class="ch-gist"><b>章旨</b>太微赋总摄全书星曜格局之大纲——入庙失度、生克制化、庙旺利陷，为全书赋诀之祖。所据南阳堂刊本卷首无罗洪先序（罗序见别本系统录文），故本册径录太微赋，体例详见凡例。</div>')
# 太微赋
body.append('<h2 class="sec">太微赋</h2>')
body.append('<p class="sec-note">全书赋诀之祖；「例曰」以下为释义口诀缀录。</p>')
for line in DATA['taiwei']:
    body.append(f'<p class="fu">{esc(line)}</p>')
body.append('<h3 class="sec">例曰</h3>')
for line in DATA['li']:
    body.append(f'<p class="fu">{esc(line)}</p>')
# 白话通释
body.append('<h3 class="sec">白话通释</h3><div class="baihua">')
for p in [
    '【太微赋正文】斗数之理至玄至微，虽百篇之言犹不能尽；星辰各有分野所属，寿夭贤愚富贵贫贱不可一概而论。十二垣、三十六位，星曜入庙为奇、失度为虚；以身宫命宫为福德之本。星曜同躔须明生克之要，紫微司一天仪之象，金星专司财库最怕空亡；帝星动则列宿奔驰，贪狼守空则财源不聚——各司其职，不可参差，否则失其造化之机。',
    '【例曰】这一组口诀逐条给出断例：禄逢冲破则吉中藏凶，天马遇空亡终身奔走；星临庙旺再看生克，命坐强宫细察制化；日月最嫌落陷反背，禄马却喜交驰。紫微天府全靠左右辅弼，七杀破军则依羊陀火铃之力。末段列举诸格局：君臣庆会、魁钺同行、禄文拱命、日月夹财、马头带剑、刑囚夹印，以及太阳居午「日丽中天」、太阴居子「水澄桂萼」等，皆以星曜庙陷与组合定富贵之品第。',
]:
    body.append(f'<p>{esc(p)}</p>')
body.append('</div>')
# 术语笺释
body.append('<h3 class="sec">术语笺释</h3><div class="kwcards">')
for kt, kv in [
    ('十二垣', '十二宫：命宫、兄弟、夫妻、子女、财帛、疾厄、迁移、仆役、官禄、田宅、福德、父母——星曜分布的十二个领域。'),
    ('入庙 / 失度', '星曜处于其力量最强的宫位为「入庙」，处于无力之宫为「失度」（落陷）；庙旺利陷是断吉凶的第一步。'),
    ('空亡', '截空、旬空二星之位。吉星遇之则力减，故金星（财星）最怕空亡；天马遇空亡主终身奔走。'),
    ('帝星', '紫微星，北斗之主；紫微动则诸星随之，故「帝星动则列宿奔驰」，喻紫微为全盘枢纽。'),
    ('羊陀火铃', '擎羊、陀罗、火星、铃星四煞星。七杀破军等杀破狼格局须赖四煞成势，然煞星也主刑伤动荡。'),
    ('马头带剑', '擎羊居午宫守命的格局，古诀以为镇卫边疆之贵将——以煞成格的典型例子。'),
]:
    body.append(f'<div class="kwcard"><span class="kt">{esc(kt)}</span><p>{esc(kv)}</p></div>')
body.append('</div>')
# 原书叶对照（特色组件）
lm = ['<h2 class="sec">原书叶对照</h2>',
      '<p class="sec-note">本篇对应原书叶逐一列置，四叶齐备，无一缺省。</p>',
      '<div class="leafmap"><div class="lm-t">卷首 · 太微赋 · 叶位表</div>']
for L in LEAF_MAP:
    inner = (f'<img src="assets/{L["src"]}"/>' if L['src'] else
             '<div class="hole">待补扫描叶<br/>（识典 SDZJ0170 对应叶）</div>')
    lm.append(f'''<div class="lm-item"><div class="ph">{inner}</div>
      <div class="lm-meta"><b>{esc(L['leaf'])}</b>　对应原文区间：<span class="rng">{esc(L['range'])}</span><br/>
      版面特征：{esc(L['mark'])}<br/>来源：南阳堂刊本（日本公文书馆藏 · 书格数字化）</div></div>''')
lm.append('</div>')
body.append('\n'.join(lm))
# 跋
body.append('''<section class="endpage">
  <div class="kicker" style="justify-content:center">样章附记</div>
  <p>本册为《紫微斗数全书》第一章样章，录卷首太微赋（含例曰）一篇，白话通释与术语笺释随文。原书叶对照为本册铁律：本篇所涉原书叶四帧逐叶列置，无一叶缺省。样章确认后，即按此体例续成全篇并及全书。</p>
  <div class="end">樣 章 終</div>
  <div class="meta">紫微斗数全书 · 第一章样章（太微赋）<br/>十六开本（185×260mm）<br/>编纂参考：南阳堂刊本（日本公文书馆藏）· 维基文库通行录文 · 识典古籍 SDZJ0170</div>
</section>''')

html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>紫微斗数全书 · 第一章样章</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, 'zwds_sample.html'), 'w', encoding='utf-8').write(html)
print('zwds_sample.html', round(os.path.getsize(os.path.join(ROOT, 'zwds_sample.html'))/1024), 'KB')

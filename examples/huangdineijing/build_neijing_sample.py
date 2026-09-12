#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》第一章样章生成器 —— 上古天真論篇第一（篇首第一节样章）
体例（依 SKILL.md）：
  经文以通行王冰注本系统录文，与元至元古林書堂刻本叶面通校（书影随文）；
  王冰注/新校正语随文系录；白话、笺释用简体；经文注文用繁体。
产出：neijing_sample.html（Edge 渲染 PDF）
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

CSS = '''
:root{
  --paper:#F8F4E9; --ink:#2C2824; --ink2:#4E4738; --note:#8A8069;
  --cinnabar:#9E2F23; --dark:#1F2B38; --dark2:#16202B;
  --rule:#C9B98A; --rule-soft:#DDD3B4; --gold:#B79B5E;
  --song:"Noto Serif TC","Songti SC",serif;
  --kai:"LXGW WenKai","Noto Serif TC",serif;
}
*{ margin:0; padding:0; box-sizing:border-box; }
/* 纸面纯白（SKILL.md §4）：整页奶油底色会让白色页边距读作窗口背景 */
html,body{ background:#FFFFFF; }
body{ font-family:var(--song); color:var(--ink); font-kerning:normal; }

@page{ size:185mm 260mm; margin:20mm 20mm 17mm; }
@page :first{ margin:0; }
/* 命名页 full：深蓝收束页满版，与流式页边距解耦（SKILL.md §4 命名页规范） */
@page full{ size:185mm 260mm; margin:0; }

/* ---------- 封面（@page:first 满版） ---------- */
.cover-page{ width:185mm; height:260mm; position:relative; overflow:hidden;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%);
  color:#EDE3C8; page-break-after:always; }
.cover-page .frame{ position:absolute; inset:7mm; border:.6pt solid rgba(183,155,94,.55);
  outline:1.4pt double rgba(183,155,94,.28); outline-offset:1.8mm; }
.cover-page .main-title{ position:absolute; top:19mm; right:23mm; writing-mode:vertical-rl;
  font-family:var(--kai); font-weight:700; font-size:52pt; letter-spacing:.24em; line-height:1.15; }
.cover-page .sub-title{ position:absolute; top:26mm; right:82mm; writing-mode:vertical-rl;
  font-size:14pt; letter-spacing:.52em; color:#C8B98D; }
.cover-page .editions{ position:absolute; top:24mm; left:26mm; writing-mode:vertical-rl;
  font-size:9.5pt; letter-spacing:.36em; color:rgba(200,185,141,.85); height:118mm; }
.cover-page .quote{ position:absolute; bottom:36mm; left:26mm; writing-mode:vertical-rl;
  font-size:9pt; letter-spacing:.3em; color:rgba(200,185,141,.6); height:70mm; }
.cover-page .seal{ position:absolute; bottom:23mm; right:23mm; width:16mm; height:16mm;
  background:var(--cinnabar); color:#F6EBD9; display:flex; align-items:center; justify-content:center;
  writing-mode:vertical-rl; text-orientation:upright; font-size:8.2pt; letter-spacing:.14em;
  line-height:1.25; border-radius:1mm; }
.cover-page .foot{ position:absolute; bottom:11mm; left:0; right:0; text-align:center;
  font-size:7.5pt; letter-spacing:.5em; color:rgba(200,185,141,.55); }

/* ---------- 扉页 ---------- */
.titlepage{ page-break-after:always; text-align:center; padding-top:32mm; }
.titlepage .big{ writing-mode:vertical-rl; font-family:var(--song); font-weight:900;
  font-size:36pt; letter-spacing:.3em; height:108mm; display:inline-block; }
.titlepage .verline{ margin-top:11mm; font-size:11.5pt; letter-spacing:.4em; color:var(--ink2); }
.titlepage .rule-orn{ margin:10mm auto 8mm; display:flex; align-items:center; justify-content:center; gap:3mm; }
.titlepage .rule-orn i{ width:26mm; height:.5pt; background:var(--rule); }
.titlepage .rule-orn b{ width:2.6mm; height:2.6mm; background:var(--cinnabar); transform:rotate(45deg); }
.titlepage .note-block{ text-align:center; font-size:9.5pt; line-height:2.15; color:var(--ink2); letter-spacing:.1em; }
.titlepage .sample-tag{ margin-top:12mm; font-size:8.5pt; letter-spacing:.4em; color:var(--note); }

/* ---------- 通用 ---------- */
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

/* ---------- 章首隔页 ---------- */
.ch-head{ page:full; break-before:page; text-align:center; padding-top:74mm; width:185mm; height:260mm; }
.ch-head .no{ font-family:var(--song); font-size:10pt; letter-spacing:.5em; color:var(--cinnabar); margin-bottom:5mm; }
.ch-head .ti{ font-family:var(--kai); font-weight:700; font-size:26pt; letter-spacing:.2em;
  color:var(--ink); margin-bottom:5mm; }
.ch-head .rule{ display:flex; align-items:center; justify-content:center; gap:3mm; margin-bottom:7mm; }
.ch-head .rule i{ width:34mm; height:.5pt; background:var(--rule); }
.ch-head .rule b{ width:2.4mm; height:2.4mm; background:var(--cinnabar); transform:rotate(45deg); }
.ch-head .gist{ display:inline-block; text-align:justify; max-width:118mm;
  padding:3.8mm 4.6mm; background:rgba(158,47,35,.055); border-left:1pt solid var(--cinnabar);
  font-size:9.8pt; line-height:1.95; color:var(--ink); }
.ch-head .gist b{ font-family:var(--song); font-size:8.5pt; letter-spacing:.35em; color:var(--cinnabar); margin-right:2.4mm; }

/* ---------- 原文 ---------- */
p.yw{ font-size:12.5pt; line-height:2.3; letter-spacing:.05em; text-align:justify;
  color:var(--ink); margin-bottom:4.5mm; }
.xuzhu{ font-size:9.8pt; line-height:1.95; color:var(--ink2); text-align:justify;
  margin:-1mm 0 4.5mm; break-inside:avoid; }
.xuzhu .xtag{ display:inline-block; font-family:var(--song); font-size:9.2pt; font-weight:700; color:var(--cinnabar);
  border:.6pt solid var(--cinnabar); border-radius:.8mm; padding:0 1.8mm; margin-right:2.2mm; }
.xuzhu.jiao .xtag{ color:#775A28; border-color:#775A28; }

/* ---------- 白话 ---------- */
.baihua p{ font-size:10.5pt; line-height:2.1; text-align:justify; color:var(--ink2); margin-bottom:4mm; }

/* ---------- 术语卡 ---------- */
.kwcards{ display:grid; grid-template-columns:1fr 1fr; gap:4.6mm; margin-bottom:2mm; }
.kwcard{ border:.6pt solid var(--rule); background:#FBF7EC; padding:4.2mm 4.6mm; break-inside:avoid; }
.kwcard .kt{ display:inline-block; font-family:var(--song); font-weight:700; font-size:9.5pt;
  color:#F6EFDD; background:var(--ink2); padding:.4mm 2.6mm; margin-bottom:2mm; letter-spacing:.15em; }
.kwcard p{ font-size:8.8pt; line-height:1.9; color:var(--ink2); text-align:justify; }

/* ---------- 版本对读 ---------- */
.plate{ text-align:center; break-inside:avoid; margin:6mm 0; }
.plate img{ max-width:100%; max-height:150mm; width:auto; border:.7pt solid var(--rule); padding:2.4mm; background:#FDFBF4; }
.plates{ display:grid; grid-template-columns:1fr 1fr; gap:5mm; }
.plates .plate img{ max-height:105mm; }
figcaption{ font-size:8pt; color:var(--note); margin-top:2.2mm; text-align:center; }
figcaption .ft{ font-family:var(--song); font-weight:700; font-size:9pt; letter-spacing:.18em; color:var(--ink); }
figcaption .ft i{ font-style:normal; color:var(--cinnabar); margin-right:2mm; }
figcaption .fs{ display:block; margin-top:1.2mm; font-size:7.8pt; color:var(--note); letter-spacing:.06em; }
.banben p{ font-size:9.6pt; line-height:2.0; text-align:justify; color:var(--ink2); margin-bottom:3.6mm; }
.banben b{ font-family:var(--song); color:var(--ink); }

/* ---------- 跋（深蓝满版收束） ---------- */
.endpage{ page:full; break-before:page; text-align:center; padding-top:78mm;
  width:185mm; height:260mm;
  background:linear-gradient(168deg, var(--dark) 0%, var(--dark2) 100%); }
.endpage .kicker{ color:#C8B98D; }
.endpage .kicker::before{ display:none; }
.endpage p{ text-align:justify; font-size:10pt; line-height:2.2; color:#CFC5AC;
  margin:6mm 8mm 0; }
.endpage .end{ margin-top:14mm; font-size:10pt; letter-spacing:.7em; color:#C8B98D; }
.endpage .meta{ margin-top:10mm; font-size:7.5pt; letter-spacing:.3em; color:rgba(200,185,141,.62); line-height:2; }
'''

body = []
# 封面
body.append('''<section class="cover-page">
  <div class="frame"></div>
  <div class="main-title">黃帝內經素問</div>
  <div class="sub-title">上古天真論篇第一 · 樣章</div>
  <div class="editions">王冰注 · 林億等校正 · 元至元古林書堂刻本叶面對讀</div>
  <div class="quote">法於陰陽　和於術數</div>
  <div class="seal">上古天真</div>
  <div class="foot">素問 · 靈樞 · 子部醫家類</div>
</section>''')
# 扉页
body.append('''<section class="titlepage">
  <div class="big">黃帝內經素問</div>
  <div class="verline">上古天真論篇第一 · 篇首樣章</div>
  <div class="rule-orn"><i></i><b></b><i></i></div>
  <div class="note-block">
    底本：元至元五年胡氏古林書堂刻本《新刊補註釋文黃帝內經素問》<br>
    參校：金刻本《黃帝內經素問》（存十三卷） · 通行王冰注本系統<br>
    經文繁體大字　王冰注新校正語隨文　白話箋釋附焉
  </div>
  <div class="sample-tag">第一章样章 · 篇首第一节</div>
</section>''')
# 凡例
body.append('''<section class="fanli">
  <h2 class="sec">凡例</h2>
  <ul class="fali">
    <li><b>一、底本与参校。</b>文字以<b>元至元五年胡氏古林書堂刻本《新刊補註釋文黃帝內經素問》</b>为底本影写之据（书影随文）；参校<b>金刻本《黃帝內經素問》</b>（王冰注、林億等校正，存卷三至五、十一至十八、二十凡十三卷，國家圖書館藏）。经文录文从通行王冰注本系统，与元刻叶面通校；王冰注录通行本，与叶面互勘，节其要者随文。</li>
    <li><b>二、编排次第。</b>每篇先陈<b>原文</b>（繁体大字，王冰注以「注」随文缩排），继以<b>白话通释</b>、<b>术语笺释</b>与<b>版本对读</b>。</li>
    <li><b>三、用字体例。</b>经文、王冰注、新校正语用繁体字；凡例、白话、笺释、按语用简体字。叶面俗字、讳字一律照录后随文出注。</li>
    <li><b>四、可核实原则。</b>书影只标注能对文字负责的版本信息；元刻叶面朱圈句读、墨钉等版刻特征，随文如实记入「版本对读」。</li>
    <li><b>五、样章范围。</b>本册为上古天真論篇<b>篇首第一节</b>（「昔在黃帝」至「德全不危」）样章；全篇及后续各篇体例同此。</li>
  </ul>
</section>''')
# 卷首书影
body.append('''<section class="shuying">
  <h2 class="sec">卷首书影</h2>
  <p class="sec-note">底本与参校本的版刻原貌；元刻为全本（卷一起），金刻存十三卷（卷三起）。</p>
  <div class="plates">
    <figure class="plate"><img src="assets/yuan_juan1.png" alt="元刻本卷之一首叶"/>
      <figcaption><span class="ft"><i>图一</i>《新刊補註釋文黃帝內經素問》卷之一首叶</span>
      <span class="fs">元至元五年胡氏古林書堂刻本 · 「上古天真論篇第一」篇题与起首经文可见朱圈句读</span></figcaption></figure>
    <figure class="plate"><img src="assets/jin_juan3.png" alt="金刻本卷第三端叶"/>
      <figcaption><span class="ft"><i>图二</i>《黃帝內經素問》卷第三端叶</span>
      <span class="fs">金刻本 · 國家圖書館藏 · 存十三卷，卷一已佚，故第一章无金刻叶可对</span></figcaption></figure>
  </div>
</section>''')
# 章首隔页
body.append('''<section class="ch-head">
  <div class="no">素問 · 卷之一 · 第 一 篇</div>
  <div class="ti">上古天真論篇第一</div>
  <div class="rule"><i></i><b></b><i></i></div>
  <div class="gist"><b>章旨</b>本篇为《素问》开篇，借黄帝与岐伯问答立「养生总纲」：以「法于阴阳，和于术数」摄生却老，以「恬惔虚无」养神存真；论肾气盛衰之序（女子七七、男子八八），列真人、至人、圣人、贤人四等。样章录其篇首第一节。</div>
</section>''')
# 原文
body.append('<h3 class="sec">原文</h3>'
            '<p class="sec-note">繁体大字；「注」为王冰注，随文缩排，注文与元刻叶面互勘节录。</p>')
for seg in [
    ('p', '昔在黃帝，生而神靈，弱而能言，幼而徇齊，長而敦敏，成而登天。'),
    ('xu', '注：按《史記》云：黃帝者，有熊國君少典之子，姓公孫……故號曰軒轅黃帝。後鑄鼎於橋山，鼎成，日升天，羣臣葬衣冠於橋山，墓今在……'),
    ('p', '迺問於天師曰：余聞上古之人，春秋皆度百歲，而動作不衰；今時之人，年半百而動作皆衰者，時世異耶？人將失之耶？'),
    ('p', '岐伯對曰：上古之人，其知道者，法於陰陽，和於術數，食飲有節，起居有常，不妄作勞，故能形與神俱，而盡終其天年，度百歲乃去。'),
    ('p', '今時之人不然也，以酒為漿，以妄為常，醉以入房，以欲竭其精，以耗散其真，不知持滿，不時御神，務快其心，逆於生樂，起居無節，故半百而衰也。'),
    ('p', '夫上古聖人之教下也，謂之虛邪賊風，避之有時，恬惔虛無，真氣從之，精神內守，病安從來。'),
    ('p', '是以嗜欲不能勞其目，淫邪不能惑其心，愚智賢不肖，不懼於物，故合於道。所以能年皆度百歲而動作不衰者，以其德全不危也。'),
]:
    if seg[0] == 'p':
        body.append(f'<p class="yw">{seg[1]}</p>')
    else:
        cls = 'xuzhu jiao' if seg[0] == 'jiao' else 'xuzhu'
        tag = '校正' if seg[0] == 'jiao' else '注'
        body.append(f'<div class="{cls}"><span class="xtag">{tag}</span>{seg[1].split("：", 1)[1]}</div>')
# 白话通释
body.append('<h3 class="sec">白话通释</h3><div class="baihua">')
for p in [
    '上古时代的黄帝，生下来就神异灵慧，很小就会说话，幼年时对事物理解得又快又透彻，长大后敦厚勤敏，成年后功成名就而登天子之位。',
    '于是他问天师岐伯：我听说上古的人，年龄都能过百岁，动作还不显衰老；现在的人，才五十岁动作就都衰退了——这是时代环境不同呢，还是人违背了养生之道呢？',
    '岐伯回答：上古懂得养生之道的人，取法于天地阴阳变化的规律，调和于养生的技术方法，饮食有节制，起居有规律，不过度操劳，所以能形体与精神都健全，活到自然赋予的寿命尽头，度过百岁才离开人世。',
    '现在的人就不是这样了：把酒当作水浆来喝，把放纵妄为当作生活常态，醉了还行房事，让欲望耗竭精气、让无度挥霍真元，不懂得保持精气充满，不善于调养精神，只图一时的痛快，违背生命的真正乐趣，起居毫无规律——所以五十岁就衰老了。',
    '上古的圣人教导民众时说：虚邪贼风这些致病因素，要按时节避开；心境保持恬静淡泊、虚无清静，真气自然顺畅，精神守持于内，疾病还从哪里来呢？',
    '因此过度的嗜欲不能劳损他们的目力，淫乱邪念不能惑乱他们的心志，无论愚者智者贤者不肖者都不为外物所惊扰，所以合乎养生之道。他们之所以都能活过百岁而动作不衰，正因为养生的德行完备、没有危殆的损耗啊。',
]:
    body.append(f'<p>{p}</p>')
body.append('</div>')
# 术语笺释
body.append('<h3 class="sec">术语笺释</h3><div class="kwcards">')
for kt, kv in [
    ('天師', '黄帝对岐伯的尊称。岐伯为黄帝之臣，主答医问，后世称医道为「岐黄之术」本此。'),
    ('天年', '天赋的自然寿限，古人以百岁为期。「尽终其天年」谓活满自然寿命而不夭折。'),
    ('術數', '调养精气的方法，如导引、按跷、吐纳之类，与「法于阴阳」相对，一为顺天，一为练形。'),
    ('恬惔虛無', '内心安静淡泊、不为物欲所扰的精神状态。王冰谓「恬惔虚无，静也」；真气由此而从顺。'),
    ('真氣', '先天的元气与后天的宗气、营卫之气的总称，受养则从顺，受耗则竭绝。'),
    ('德全不危', '养生之德完备，则不遭危殆的损耗。德，兼指合乎道的修养行为。'),
]:
    body.append(f'<div class="kwcard"><span class="kt">{kt}</span><p>{kv}</p></div>')
body.append('</div>')
# 版本对读
body.append('''<section class="banben">
  <h3 class="sec">版本对读</h3>
  <p class="sec-note">底本叶面实察记录，凡未经叶面核实者不出校。</p>
  <p><b>一、卷端题署。</b>元刻卷之一首叶卷端题「新刊補註釋文黃帝內經素問卷之一」，次行题「啓玄子次註　林億孫奇高保衡等奉勅校正　孫兆重改誤」，与卷首总目所载刊刻题署相合；篇题作「○上古天真論篇第一」，篇名前冠以圈号，为元刻各篇通例。</p>
  <p><b>二、句读朱圈。</b>元刻经文加朱圈句读，本文所录「昔在黃帝」至「德全不危」诸句，叶面圈分段落与通行本句读一致；「夫上古聖人之教下也」一句叶面即于「也」字下圈绝，可证此句古读自有分别。</p>
  <p><b>三、墨钉。</b>「成而登天」句下接「天師曰」处，元刻叶面见墨钉一方（未刻之字位），通行本此处为「迺問於」三字连读。墨钉所代何字待考，录文仍从通行本；金刻本存卷无卷一，无从对勘，姑记于此。</p>
  <p><b>四、注文双行。</b>王冰注刻为双行小字，随经文之后；「昔在黃帝」句下注引《史記》黄帝事迹（有熊國君少典之子、姓公孫名軒轅、鑄鼎橋山、羣臣葬衣冠云云），与通行本注文相合，可证元刻注文系统即王冰注旧文。</p>
  <p><b>五、参校格局。</b>金刻本存卷三至五、十一至十八、二十凡十三卷，卷一已佚；故本书卷一诸篇以元刻为唯一叶面依据，卷三以下各篇则可获元刻、金刻双本对读，体例于各篇「版本对读」下分别注明。</p>
</section>''')
# 跋
body.append('''<section class="endpage">
  <div class="kicker" style="justify-content:center">样章附记</div>
  <p>本册为《黃帝內經素問》第一章样章，录上古天真論篇首第一节。经文以通行王冰注本系统录文，与元至元古林書堂刻本叶面通校；卷端题署、篇题圈号、朱圈句读、注文双行、墨钉等版刻特征均出叶面实察。样章确认后，即以此体例续成全篇并及全书。</p>
  <div class="end">樣 章 終</div>
  <div class="meta">黃帝內經素問 · 第一章样章（篇首第一节）<br/>十六开本（185×260mm）<br/>编纂参考：国家图书馆藏元至元胡氏古林書堂刻本 · 金刻本 · 通行王冰注本系统</div>
</section>''')

html = (f'<!DOCTYPE html>\n<html lang="zh-Hans"><head><meta charset="UTF-8">\n'
        f'<title>黃帝內經素問 · 第一章样章</title>\n'
        f'<link rel="stylesheet" href="fonts/fullface.css">\n'
        f'<style>{CSS}</style></head>\n<body>\n' + '\n'.join(body) + '\n</body></html>')
open(os.path.join(ROOT, 'neijing_sample.html'), 'w', encoding='utf-8').write(html)
print('neijing_sample.html', round(os.path.getsize(os.path.join(ROOT, 'neijing_sample.html'))/1024), 'KB')

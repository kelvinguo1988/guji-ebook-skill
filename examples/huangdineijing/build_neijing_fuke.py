#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》B 版复刻本生成器 —— 紫微斗数全书定稿样式移植
· 样式：逐叶一一对应对页（左半原书叶真图 · 右半复刻叶）、近满幅页框、
  齊伋体+双重偏移活字、朱砂毛笔句读圈、郭仲和藏書长条朱文印（用户定稿）
· 行款：元至元本实测——半叶 13 行、行 23 字、双行墨注（王冰注）/朱注（新校正）
· 数据：book_data.json（经 p / 王冰注 zhu / 新校正 xiao）+ 殆知阁标点（句读对齐）
"""
import re, os, json, sys, difflib, math
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
_PAPER_XREF = None                 # 宣纸背景只嵌一次，跨页复用 xref

# ---------- 画布与版框（vRain 实测参数，px@240dpi；PXP: px→pt=72/240） ----------
PXP = 72.0/240
def px(v): return v*PXP
CV_W, CV_H = 2480, 1860
GUT_CX = CV_W/2                    # 1240
LCW = 120                          # 书口宽
FR_X0, FR_X1 = 150, 2300           # 版框左右（再放大：半叶 1015px×10 列 = 列宽 101.5）
FR_Y0, FR_Y1 = 100, 1760           # 版框上下（再放大：框高 1660，上下边距 85/85 含外框线）
HALF_W = (FR_X1-FR_X0-LCW)/2       # 805
LEAF_COL = 10                      # 半叶 10 行（列）
ROWS = 23                          # 行 23 字（南阳堂叶面实测）
COL_W = HALF_W/LEAF_COL            # 80.5
ROW_H = (FR_Y1-FR_Y0)/ROWS         # 59.57
OUT_W, OUT_H = 10, 1               # 外框粗线 / 内框细线 px
INK = (0.08, 0.07, 0.065)
RED = (0.53, 0.27, 0.20)           # vRain 圈注色 #874434
BIG = 89*PXP                       # 正文 72px ≈ 0.95×行高·密排
DATI = 95*PXP                      # 卷端大题（16 字均布全列·行距 1.4375 行；84 会压框）
PIANTI = 96*PXP                    # 篇题（行距 1.5 行）
BJ = 77*PXP                        # 牌记
SMALL = 65*PXP                     # 篇题下署
NOTE = 46.5*PXP                      # 双行小注：半列宽 40.25px 内 ≤0.94×列宽（vRain 注/列比例换算）
STROKE_W = 1.0
WHITE = (0.97, 0.94, 0.87)

import fitz
KAI = os.environ.get('FK_FONT', os.path.join(ROOT, 'fonts', 'qiji-combo.ttf'))
FONT = fitz.Font(fontfile=KAI)
def tlen(ch, size): return FONT.text_length(ch, fontsize=size)

DZ_PUNCT_FILE = '/tmp/suwen_daizhige.txt'

def load_punct_index():
    """殆知阁标点文本 → {篇号: (汉字流, 圈点缝隙集合)}"""
    txt = open(DZ_PUNCT_FILE, encoding='utf-8').read().replace('\ufeff', '')
    paras = [re.sub(r'^[\s\u3000]+', '', x) for x in txt.split('\n')]
    idx_d, cur, num = {}, None, 0
    CN = '一二三四五六七八九十'
    def c2n(cn):
        dd = {c: i+1 for i, c in enumerate(CN)}
        if cn in dd: return dd[cn]
        if cn.startswith('十'): return 10 + (dd.get(cn[1:], 0) if len(cn) > 1 else 0)
        if '十' in cn:
            a, b2 = cn.split('十', 1)
            return dd.get(a, 0)*10 + (dd.get(b2, 0) if b2 else 0)
        if cn.startswith('二十'): return 20 + dd.get(cn[2:], 0)
        if cn.startswith('三十'): return 30 + dd.get(cn[2:], 0)
        return 0
    for pp in paras:
        m = re.match(r'^([\u4e00-\u9fff（）]{2,14}篇第[一二三四五六七八九十百零]+)$', pp)
        if m:
            num = c2n(re.search(r'第([一二三四五六七八九十百零]+)', m.group(1)).group(1))
            cur = m.group(1); idx_d[num] = ''
            continue
        if num and cur and not pp.startswith('卷第'):
            idx_d[num] += pp
    out = {}
    for nn, tx in idx_d.items():
        chs, mks = [], set()
        for c in tx:
            if '\u4e00' <= c <= '\u9fff':
                chs.append(c)
            elif c in '。？！；':
                mks.add(len(chs))
        out[nn] = (''.join(chs), mks)
    return out

# ---------- 句读对齐 ----------
def align_marks(main_stream, dz_stream, dz_marks):
    """句读对齐（快速版）：逐句锚定——句末前 12 字为 key 顺序 find（C 层），
    顺序推进防雪崩。dz_stream=带标点源流的汉字流、dz_marks=句末缝隙集合。"""
    out = set()
    i = 0
    for mpos in sorted(dz_marks):
        if mpos < 1 or mpos > len(dz_stream):
            continue
        key = dz_stream[max(0, mpos-12):mpos]
        if len(key) < 4:
            continue
        p = main_stream.find(key, i)
        if p < 0:
            continue
        out.add(p + len(key) - 1)
        i = p + 1
    return out

# ---------- 排版：卷端固定列 + 正文流 + 平衡式双行朱注 ----------
class Leaf:
    def __init__(self): self.cells = []   # (col,row,size,ch,color,gi,lane)  color: ink/red/note; lane: 0整列/1右小列/2左小列

COLORMAP = {'ink': INK, 'red': RED, 'note': RED, 'inknote': INK}

def parse_note(text):
    """注文串 → (字符流, 句读圈位集合, 书名线区间)；注内标点不占字位，圈随注色"""
    stream, marks, books = [], set(), []
    open_at = None
    for c in text:
        if c == '《':
            open_at = len(stream); continue
        if c == '》':
            if open_at is not None: books.append((open_at, len(stream)-1)); open_at = None
            continue
        if c in '，。、；：！？':
            if stream: marks.add(len(stream)-1)
            continue
        if '\u4e00' <= c <= '\u9fff':
            stream.append(c)
    return ''.join(stream), marks, books

def typeset(body_stream, dz=(None, set()), notes=None, pian_title='上古天真論篇第一'):
    """素问卷端（元刻实察）：col0 大题 DATI、col1 题署 BJ 满列、col2 ○+篇题（PIANTI）后正文接排；
    注=锚点触发、同锚多注连排（王冰注 inknote 墨双行 / 新校正 note 朱双行），
    每注独占双行列段（右小列满→左小列→溢出续列），注毕同列续排。"""
    leaves = [Leaf()]
    L = leaves[0]
    for r, ch in enumerate('新刊補註釋文黃帝內經素問卷之一'):
        L.cells.append((0, r*1.4375, DATI, ch, 'ink', None, 0))
    for r, ch in enumerate('啓玄子次註林億孫奇高保衡等奉勅校正孫兆重改誤'):
        L.cells.append((1, r, BJ, ch, 'ink', None, 0))
    L.cells.append((2, 0, PIANTI*0.8, '○', 'ink', None, 0))
    for r, ch in enumerate(pian_title):
        L.cells.append((2, 1+r*1.5, PIANTI, ch, 'ink', None, 0))
    from opencc import OpenCC
    _t2s = OpenCC('t2s')
    main_s = _t2s.convert(body_stream)
    if len(main_s) == len(body_stream) and dz[0]:
        marks = align_marks(main_s, dz[0], dz[1])
    else:
        marks = set()
    notes_at = {}
    for anchor, ntexts in (notes or []):
        pos = body_stream.find(anchor)
        assert pos >= 0, '注文锚点未命中: ' + anchor
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)
    gi = 0
    col, row = 2, int(2 + len(pian_title)*1.5)

    def new_col():
        nonlocal col, row
        col += 1
        row = 0
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0

    for ch in body_stream:
        if row >= ROWS:
            new_col()
        leaves[-1].cells.append((col, row, BIG, ch, 'ink', gi, 0))
        gi += 1
        row += 1
        nlist = notes_at.get(gi - 1)
        if not nlist:
            continue
        col += 1
        row = 0
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0
        for kind, ntext in nlist:
            nstream, nmarks, nbooks = parse_note(ntext)
            i2 = 0
            while i2 < len(nstream):
                for lane in (1, 2):
                    seg = nstream[i2:i2+ROWS]
                    if not seg:
                        break
                    for k, c2 in enumerate(seg):
                        leaves[-1].cells.append((col, k, NOTE, c2, kind, None, lane))
                    for m in nmarks:
                        if i2 <= m < i2 + len(seg):
                            leaves[-1].cells.append((col, m-i2, NOTE, '', kind, 'mark', lane))
                    for (b0, b1) in nbooks:
                        lo, hi = max(b0, i2), min(b1, i2+len(seg)-1)
                        for j in range(lo, hi+1):
                            leaves[-1].cells.append((col, j-i2, NOTE, '', kind, 'bookline', lane))
                    i2 += len(seg)
                col += 1
                if col >= LEAF_COL:
                    leaves.append(Leaf()); col = 0
        row = 0
    return leaves, marks

def put_char(page, x, y, ch, size, color):
    """居中落字 + 双重偏移模拟活字墨涨（render_mode=2 在 CID 字体会糊死）"""
    tw = tlen(ch, size)
    for dx in (0.0, STROKE_W*PXP):
        page.insert_text((x-tw/2+dx, y+size*0.36), ch, fontname='kai',
                         fontsize=size, color=color, fill=color)

def brush_circle(page, cx, cy, r, color, seed):
    """毛笔句读圈：变宽闭合环（起笔顿厚→行笔渐细→收笔回叠），微椭圆+内外缘起伏，
    种子=字符位置，同一版每次渲染完全一致"""
    rnd = (seed * 2654435761) & 0x7FFFFFFF | 1
    def frac():
        nonlocal rnd
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        return rnd / 0x7FFFFFFF
    p1, p2 = frac()*6.283, frac()*6.283
    dx, dy = r*0.16*(frac()-0.5), r*0.16*(frac()-0.5)   # 内孔偏心→环宽自然不匀
    N = 48
    pts = []
    for i in range(N+1):                                # 外缘：正序
        t = i / N * 6.283
        ro = r * (1 + 0.06*math.sin(2*t + p1))
        pts.append(fitz.Point(cx + ro*math.cos(t), cy + ro*math.sin(t)*0.95))
    for i in range(N, -1, -1):                          # 内缘：逆序闭合
        t = i / N * 6.283
        w = 0.32 + 0.08*math.sin(3*t + p2)              # 行笔起伏
        if t < 1.1: w += 0.20*(1 - t/1.1)               # 起笔顿
        if t > 5.3: w += 0.16*(t - 5.3)/0.983           # 收笔叠回起笔
        ri = r * max(0.30, 1 - w)
        pts.append(fitz.Point(cx+dx + ri*math.cos(t), cy+dy + ri*math.sin(t)*0.95))
    page.draw_polyline(pts, fill=color, color=None)   # 外缘正序+内缘逆序，fill 自动闭合成环

def draw_halfleaf(page, leaf, right_edge, marks):
    """right_edge: 该半叶正文区右缘 canvas px（右叶=FR_X1，左叶=FR_X0+HALF_W）；列自右起
    句读圈一律朱砂毛笔圈（用户定稿），圈位 x+.42em y+.45em（vRain nop x.45/y.5）
    注列（虞初新志式）：整列双小列，列中缝画朱细线，书名号→字左朱侧线"""
    note_cols = {}
    for (col, row, size, ch, color, gi, lane) in leaf.cells:
        if lane:
            rng = note_cols.setdefault(col, [99, -1])
            rng[0] = min(rng[0], row); rng[1] = max(rng[1], row)
    for col, (r0, r1) in note_cols.items():
        lx = px(right_edge - COL_W*(col+0.5))
        page.draw_line(fitz.Point(lx, px(FR_Y0 + ROW_H*(r0+0.5)) - px(ROW_H*0.5)),
                       fitz.Point(lx, px(FR_Y0 + ROW_H*(r1+0.5)) + px(ROW_H*0.5)),
                       color=RED, width=px(1))
    for (col, row, size, ch, color, gi, lane) in leaf.cells:
        cx = right_edge - COL_W*(col+0.5)
        if lane == 1: cx += COL_W*0.25
        elif lane == 2: cx -= COL_W*0.25
        x = px(cx)
        y = px(FR_Y0 + ROW_H*(row+0.5))
        colr = COLORMAP[color]
        if ch == '':
            if gi == 'mark':
                cy = min(y + size*0.45, px(FR_Y1) - size*0.18 - px(9))
                brush_circle(page, x + size*0.42, cy, size*0.17, RED, int(col*131 + row*17))
            elif gi == 'bookline':
                lx = x - size*0.55
                page.draw_line(fitz.Point(lx, y-px(ROW_H*0.5)), fitz.Point(lx, y+px(ROW_H*0.5)),
                               color=RED, width=px(2))
            continue
        put_char(page, x, y, ch, size, colr)
        if isinstance(gi, int) and gi in marks:
            cy = min(y + size*0.45, px(FR_Y1) - size*0.18 - px(9))
            brush_circle(page, x + size*0.42, cy, size*0.17, RED, gi)   # 朱砂毛笔圈（用户定稿）

SEAL_PNG = os.path.join(ROOT, 'assets', 'seal_gzh.png')   # 朱文古玺（make_seal.py 合成，用户定稿）

def draw_shuyin(page, x, y, w, h):
    page.insert_image(fitz.Rect(x, y, x + w, y + h), filename=SEAL_PNG)

def page_chrome(doc):
    """对页公共版式：宣纸底+做旧、双线版框、书口双细线、鱼尾、书口题名、天头条章+书眉；返回 page（叶次由调用方盖）"""
    global _PAPER_XREF
    page = doc.new_page(width=px(CV_W), height=px(CV_H))
    page.insert_font(fontname='kai', fontfile=KAI)
    rect = fitz.Rect(0, 0, px(CV_W), px(CV_H))
    if _PAPER_XREF is None:
        _PAPER_XREF = page.insert_image(rect, filename=os.path.join(ROOT, 'assets', 'paper_vr.jpg'),
                                        keep_proportion=False, xref=0)
    else:
        page.insert_image(rect, xref=_PAPER_XREF)
    # 做旧：整体压一层淡茶色（vRain 纸偏黄，直接贴图偏白）
    page.draw_rect(rect, fill=(0.72, 0.60, 0.42), color=None, fill_opacity=0.10)
    # 版框：粗外框 + 细内框围全对页（vRain 24_*.cfg: outline 10 / inline 1 / 距 5）
    page.draw_rect(fitz.Rect(px(FR_X0-15), px(FR_Y0-15), px(FR_X1+15), px(FR_Y1+15)),
                   color=INK, width=px(OUT_W))
    page.draw_rect(fitz.Rect(px(FR_X0), px(FR_Y0), px(FR_X1), px(FR_Y1)),
                   color=INK, width=px(OUT_H))
    # 书口双细线
    for gx in (GUT_CX-LCW/2, GUT_CX+LCW/2):
        page.draw_line(fitz.Point(px(gx), px(FR_Y0)), fitz.Point(px(gx), px(FR_Y1)), color=INK, width=px(OUT_H))
    # 鱼尾：实心垂带五边形（rect 50 + tri 30），上贴版框顶、下贴版框底（对鱼尾）
    l, r = GUT_CX-LCW/2, GUT_CX+LCW/2
    page.draw_line(fitz.Point(px(l), px(105)), fitz.Point(px(r), px(105)), color=INK, width=px(1))
    page.draw_polyline([fitz.Point(px(p[0]), px(p[1])) for p in
                        [(l,110),(r,110),(r,190),(GUT_CX,150),(l,190),(l,110)]], color=INK, width=0, fill=INK)
    page.draw_polyline([fitz.Point(px(p[0]), px(p[1])) for p in
                        [(l,1750),(r,1750),(r,1670),(GUT_CX,1710),(l,1670),(l,1750)]], color=INK, width=0, fill=INK)
    # 书口题名
    tsize = 86*PXP
    cy = px(652) + tsize*0.36
    for ch in '黃帝內經素問':
        put_char(page, px(GUT_CX), cy, ch, tsize, INK)
        cy += px(94)
    # 天头右上：藏书印 + 书眉竖排书名
    draw_shuyin(page, px(20), px(1470), px(104), px(312))   # 长条鉴藏章「郭仲和藏書」置左下角（用户定稿）
    hy, msz, mcol = px(110), 46*PXP, (0.30, 0.27, 0.24)
    for ch in '黃帝內經素問':
        tw = tlen(ch, msz)
        for dx, dy in ((0, 0), (2.2*PXP, 0), (0, 2.2*PXP), (2.2*PXP, 2.2*PXP)):
            page.insert_text((px(2400)-tw/2+dx, hy+msz*0.36+dy), ch, fontname='kai',
                             fontsize=msz, color=mcol, fill=mcol)
        hy += px(74)
    return page

CN_NUM = ['〇','一','二','三','四','五','六','七','八','九','十',
          '十一','十二','十三','十四','十五','十六','十七','十八','十九','二十']

def render_pair_page(doc, leaf, folio, marks, src=None, cap=None):
    """一一对应对页（用户定稿）：左半=原书叶截图、右半=对应复刻叶；无扫描则左半留白叶（画界栏）
    叶图按原叶比例整叶完整（宽≤半叶区-60、高≤1520），题注居中于图下"""
    page = page_chrome(doc)
    # 右半：复刻叶（界栏 + 正文）
    for c in range(1, LEAF_COL):
        x = FR_X1 - COL_W*c
        page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    draw_halfleaf(page, leaf, FR_X1, marks)
    fs = CN_NUM[folio] if folio < len(CN_NUM) else str(folio)
    put_char(page, px(GUT_CX), px(1510), fs, 41*PXP, INK)
    # 左半：原书叶截图或白叶
    cx_l = (FR_X0 + (GUT_CX - LCW/2)) / 2
    if src:
        im = Image.open(os.path.join(ROOT, 'assets', src))
        sc = min((HALF_W-60)/im.width, 1520/im.height)
        w, h = im.width*sc, im.height*sc
        x = cx_l - w/2
        y = FR_Y0 + 40 + (1520-h)/2
        page.insert_image(fitz.Rect(px(x), px(y), px(x+w), px(y+h)),
                          filename=os.path.join(ROOT, 'assets', src))
        page.draw_rect(fitz.Rect(px(x), px(y), px(x+w), px(y+h)), color=INK, width=px(2))
        if cap:
            cfs = 9.2
            tw = FONT.text_length(cap, fontsize=cfs)
            page.insert_text((px(cx_l)-tw/2, px(FR_Y1)-px(14)), cap,
                             fontname='kai', fontsize=cfs, color=(0.35, 0.32, 0.28))
    else:
        for c in range(1, LEAF_COL):
            x = FR_X0 + COL_W*c
            page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))

def render_spread(doc, lf_r, lf_l, folio, marks, cover=False):
    page = page_chrome(doc)
    # 界栏（有内容的半叶才画；封面叶以书影代正文，不画右半界栏）
    if lf_r is not None and not cover:
        for c in range(1, LEAF_COL):
            x = FR_X1 - COL_W*c
            page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    if lf_l is not None:
        for c in range(1, LEAF_COL):
            x = FR_X0 + COL_W*c
            page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    if folio is not None:
        fs = CN_NUM[folio] if folio < len(CN_NUM) else str(folio)
        put_char(page, px(GUT_CX), px(1510), fs, 41*PXP, INK)
    if cover:
        # 封面叶：右半嵌卷端书影（原叶扫描裁框，含诸家藏印）——vRain 天头/卷端嵌真叶书影的做法
        iw, ih = 900, int(900*2034/1172)
        ix = ((GUT_CX+LCW/2) + FR_X1)/2 - iw/2      # 书影置右半（前片惯例）
        iy = (FR_Y0 + FR_Y1)/2 - ih/2
        page.insert_image(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)),
                          filename=os.path.join(ROOT, 'assets', 'yuan_cover.jpg'))
        page.draw_rect(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)), color=INK, width=px(2))
    else:
        if lf_r is not None: draw_halfleaf(page, lf_r, FR_X1, marks)
    if lf_l is not None: draw_halfleaf(page, lf_l, FR_X0+HALF_W, marks)

def main():
    import json
    BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))
    n = 1
    e = BOOK[str(n)]
    pian_title = e['title']
    punct = load_punct_index()
    punct_stream = punct.get(n, ('', set()))[0] if n in punct else ''
    body_stream, notes = [], []
    last_p_tail = ''
    for pp in e['paras']:
        for k, t in pp:
            t = t.strip()
            if not t:
                continue
            if k == 'p':
                clean = re.sub(r'[，。：；！？、「」『』（）〔〕\s]', '', t)
                body_stream.append(clean)
                last_p_tail = clean[-12:]
            elif k in ('zhu', 'xiao'):
                anchor = last_p_tail
                kind = 'inknote' if k == 'zhu' else 'note'
                notes.append((anchor, [(kind, t)]))
    body = ''.join(body_stream)
    leaves, marks = typeset(body, punct.get(n, ('', set())), notes, pian_title)

    # 越界断言（vRain 定稿规范）
    n_body = sum(1 for lf in leaves for c in lf.cells if isinstance(c[5], int))
    assert n_body == len(body), (n_body, len(body))
    for lf in leaves:
        for (col, row, size, ch, color, gii, lane) in lf.cells:
            assert 0 <= col < LEAF_COL and 0 <= row < ROWS, (col, row, ch)

    doc = fitz.open()
    render_spread(doc, None, None, None, marks, cover=True)
    # 逐叶一一对应：元刻卷一第 1 半叶起（PDF index 11 右半起，每页双半叶）
    dsrc = fitz.open('/Users/sec-t/Downloads/黄帝内经/ZHSY000605 新刊補注釋文黄帝內經素問十二卷 (唐)王冰 注(宋)林億等 校正(宋)孫兆 改誤 元至元五年胡氏古林書堂刻本/001.pdf')
    def half_img(k):     # 卷一第 k 半叶 → 裁切图文件
        out = f'/tmp/yuan_h{k}.jpg'
        if not os.path.exists(out):
            pidx = 11 + (k-1)//2
            side_left = (k-1) % 2 == 1
            pg = dsrc[pidx]
            r = pg.rect
            x0 = 0 if side_left else r.width/2
            pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(x0, 0, x0 + r.width/2, r.height))
            pix.save(out, jpg_quality=85)
        return out
    for i, lf in enumerate(leaves):
        src = half_img(i+1)
        # 题注：该叶首末经文字
        bigs = [c[3] for c in lf.cells if c[2] == BIG]
        cap = f'原書葉　{bigs[0] if bigs else ""}…{bigs[-1] if bigs else ""}' if bigs else '原書葉'
        render_pair_page(doc, lf, i+1, marks, src, cap)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = os.path.join(ROOT, '復刻-素問·上古天真論篇第一.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 卷首封面 1 + {len(leaves)} 对页（左原叶右复刻一一对应）, 正文 {n_body} 字, 句读圈 {len(marks)}')

if __name__ == '__main__':
    main()

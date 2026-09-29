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
LEAF_COL = 13                      # 半叶 13 行（元刻素问著录：每半叶十三行）
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

# ---------- 元刻叶切分表（第一章·上古天真論，叶图逐叶目验锚定） ----------
# 锚：叶2首=「天」（成而登天跨叶）；叶5起=「岐伯曰女子七」；叶6起=帝曰人年老（材力）；
#     叶7起≈腎者主水段注；叶8起=真人段；叶9顶=四氣調神篇題（天真論止于叶8末）
LEAF_ANCHORS = [None, '成而登天', '女子七歲', '帝曰人年老', '腎者主水', '余聞上古有真人者', None]

def compute_cuts(body_stream, n_leaves_target=None):
    """按锚点在经文流中定位切点；缺锚处按剩余容量插值。返回切点索引列表（含 0 与 len）。"""
    cuts = []
    for a in LEAF_ANCHORS:
        if a is None:
            cuts.append(None)
        else:
            i = body_stream.find(a)
            cuts.append(i if i >= 0 else None)
    cuts[1] = body_stream.find('成而登天') + len('成而登天') - 1   # 叶2自「天」起
    n = len(body_stream)
    # 缺锚插值：在已知锚之间按剩余字数均分
    known = [i for i, c in enumerate(cuts) if c is not None]
    for bi in range(len(known) - 1):
        lo, hi = known[bi], known[bi + 1]
        gap_leaves = (bi + 1, known[bi + 1] and bi + 1)
    for i in range(len(cuts)):
        if cuts[i] is not None:
            continue
        prev_k = max([j for j in range(i) if cuts[j] is not None], default=-1)
        next_k = min([j for j in range(i + 1, len(cuts)) if cuts[j] is not None], default=len(cuts))
        prev_pos = 0 if prev_k < 0 else cuts[prev_k]
        next_pos = n if next_k >= len(cuts) else cuts[next_k]
        span = next_pos - prev_pos
        k = (i - prev_k) / (next_k - prev_k)
        cuts[i] = prev_pos + int(span * k)
    cuts[-1] = n
    ordered = sorted(set(max(0, min(n, c)) for c in cuts))
    return ordered

def typeset(body_stream, dz, notes=None, pian_title='上古天真論篇第一', cuts=None):
    """分叶模式：按元刻叶边界（cuts）切分内容，每叶独立排版（13 列×23 行），
    注随文夹注（双行）；叶内溢出时字号自适应收缩——左右内容逐叶严格一致。"""
    global BIG, NOTE
    if cuts is None:
        cuts = [0, len(body_stream)]
    notes_at = {}
    for anchor, ntexts in (notes or []):
        pos = body_stream.find(anchor)
        if pos < 0:
            continue
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)
    leaves = []
    for li in range(len(cuts) - 1):
        lo, hi = cuts[li], cuts[li + 1]
        seg = body_stream[lo:hi]
        seg_notes_d = {}
        for pos, v in notes_at.items():
            if lo <= pos < hi:
                seg_notes_d[pos - lo] = v
        seg_notes = sorted(seg_notes_d.items(), key=lambda x: x[0])
        # 字号自适应：从 1.0 起排，列溢出则收缩重排（最多 6 档）
        scale = 1.0
        for _ in range(6):
            tl, _mk = typeset_leaf(seg, seg_notes, pian_title if li == 0 else None, scale)
            if len(tl) == 1:
                break
            scale *= 0.94
        leaves.extend(tl)
    return leaves, align_marks_cache.get('marks', set()) if False else _last_marks

_last_marks = set()

def typeset_leaf(seg, seg_notes, lead, scale, pian_title="上古天真論篇第一"):
    """单叶排版：lead=卷端列（仅叶 1）。返回 [Leaf]（通常 1 个；极端溢出可 2 个）。"""
    global _last_marks
    big = BIG * scale
    note = NOTE * scale
    leaves = [Leaf()]
    L = leaves[0]
    col, row = 0, 0
    if lead:
        for r, ch in enumerate('新刊補註釋文黃帝內經素問卷之一'):
            L.cells.append((0, r*1.4375, DATI*scale, ch, 'ink', None, 0))
        for r, ch in enumerate('啓玄子次註林億孫奇高保衡等奉勅校正孫兆重改誤'):
            L.cells.append((1, r, BJ*scale, ch, 'ink', None, 0))
        L.cells.append((2, 0, PIANTI*scale*0.8, '○', 'ink', None, 0))
        for r, ch in enumerate(pian_title):
            L.cells.append((2, 1+r*1.5, PIANTI*scale, ch, 'ink', None, 0))
        col, row = 2, int(2 + len(pian_title)*1.5)
    gi0 = typeset_leaf.base_gi
    gi = 0

    def new_col():
        nonlocal col, row
        col += 1
        row = 0
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0

    for ch in seg:
        if row >= ROWS:
            new_col()
        leaves[-1].cells.append((col, row, big, ch, 'ink', gi0 + gi, 0))
        gi += 1
        row += 1
        nlist = dict(seg_notes).get(gi - 1) or []
        for kind, ntext in nlist:
            # 随文夹注（元刻原貌）：注嵌当前列剩余行（双行平衡），注毕同列/续列接排经文
            chars = [c2 for c2 in ntext if c2.strip()]
            nstream = ''.join(chars)
            nmarks, nbooks = parse_note(ntext)[1:3]
            n2 = len(nstream)
            if n2 == 0:
                continue
            i2 = 0
            while i2 < n2:
                room = ROWS - row
                if room <= 0:
                    new_col()
                    continue
                take = min(n2 - i2, room * 2)
                tr = (take + 1) // 2
                for k, c2 in enumerate(nstream[i2:i2+take]):
                    lane = 1 if k < tr else 2
                    r2 = row + (k if k < tr else k - tr)
                    leaves[-1].cells.append((col, r2, note, c2, kind, None, lane))
                for m in nmarks:
                    if i2 <= m < i2 + take:
                        r2 = row + min(m - i2, tr - 1)
                        lane = 1 if (m - i2) < tr else 2
                        leaves[-1].cells.append((col, r2, note, '', kind, 'mark', lane))
                for (b0, b1) in nbooks:
                    lo2, hi2 = max(b0, i2), min(b1, i2+take-1)
                    for j in range(lo2, hi2+1):
                        r2 = row + min(j - i2, tr - 1)
                        lane = 1 if (j - i2) < tr else 2
                        leaves[-1].cells.append((col, r2, note, '', kind, 'bookline', lane))
                i2 += take
                row += tr
                if i2 < n2 and row >= ROWS:
                    new_col()
    typeset_leaf.base_gi = gi0 + gi
    _last_marks = set()
    return leaves

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
    punct_stream, punct_marks = punct.get(n, ('', set()))
    body_stream, notes, last_p_tail = [], [], ''
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
                kind = 'inknote' if k == 'zhu' else 'note'
                notes.append((last_p_tail, [(kind, t)]))
    body = ''.join(body_stream)
    from opencc import OpenCC
    main_s = OpenCC('t2s').convert(body)
    dz0, dzm = punct_stream, punct_marks
    marks = align_marks(main_s, dz0, dzm)
    # 注按切点分叶（全局 pos → 叶区间）
    notes_at = {}
    for anchor, ntexts in notes:
        pos = body.find(anchor)
        if pos < 0:
            continue
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)

    # 逐叶对应（用户定稿）：自由流排版（密度=元刻行款 13 行 23 字·注随文夹注）→
    # 每 13 列满自动断叶 → 叶内容与元刻逐叶自然对应；元刻锚点用于校验偏移
    notes_at = {}
    for anchor, ntexts in notes:
        pos = body.find(anchor)
        if pos < 0:
            continue
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)

    typeset_leaf.base_gi = 0
    all_marks = set()
    tls = typeset_leaf(body, sorted(notes_at.items(), key=lambda x: x[0]), pian_title, 1.0)
    doc = fitz.open()
    render_spread(doc, None, None, None, set(), cover=True)
    folio = 0
    anchors_read = ['新刊補註釋文', '天(成而登天跨叶)', '廿五(注)', '數始於七(注)', '岐伯曰女子七',
                    '材力(注)', '五臟主(注)', '(天真論末)', '四氣調神(次篇)']
    for tli, lf in enumerate(tls):
        folio += 1
        bigs = [c[3] for c in lf.cells if c[2] == BIG]
        src = half_img(tli + 1)
        cap = f'原書葉　卷一　第{tli+1}叶　{bigs[0] if bigs else ""}…{bigs[-1] if bigs else ""}' if bigs else '原書葉'
        render_pair_page(doc, lf, folio, all_marks, src, cap)
        anchor_hit = ''
        t1 = ''.join(bigs)
        for ai, a2 in enumerate(['成而登天', '岐伯曰女子七', '材力', '腎者主水', '余聞上古有真人者']):
            if a2[:4] in t1:
                anchor_hit = f'↔元刻锚: {anchors_read[ai+1] if ai+1 < len(anchors_read) else a2}'
        print(f'  叶{tli+1}: 首={"".join(bigs[:3])} 末={"".join(bigs[-3:])} {anchor_hit}', flush=True)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = os.path.join(ROOT, '復刻-素問·上古天真論篇第一.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 封面 1 + {folio} 对页（左原叶右复刻逐叶对应）, 正文 {len(body)} 字')

def half_img(k):
    out = f'/tmp/yuan_h{k}.jpg'
    if not os.path.exists(out):
        import fitz as _f
        dsrc = _f.open('/Users/sec-t/Downloads/黄帝内经/ZHSY000605 新刊補注釋文黄帝內經素問十二卷 (唐)王冰 注(宋)林億等 校正(宋)孫兆 改誤 元至元五年胡氏古林書堂刻本/001.pdf')
        pidx = 11 + (k-1)//2
        side_left = (k-1) % 2 == 1
        pg = dsrc[pidx]
        r = pg.rect
        x0 = 0 if side_left else r.width/2
        pix = pg.get_pixmap(matrix=_f.Matrix(2, 2), clip=_f.Rect(x0, 0, x0 + r.width/2, r.height))
        pix.save(out, jpg_quality=85)
    return out

if __name__ == '__main__':
    main()

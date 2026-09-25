#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗数全书》复刻本生成器 —— 品类 B：直排刻本风格（对页 spread，对齐 vRain 样板 010.png）
· 行款：南阳堂刊本叶面实测——半叶 10 行、行 23 字、四周单边粗框、白口对鱼尾
· 版式对齐 vRain（实测 010.png + canvas/*.cfg + canvas.pl）：
  - 单一粗外框(10px)+细内框(1px)围全对页，书口双细线 120px 居中
  - 上/下鱼尾=实心垂带五边形（rect50+tri30）贴版框，书口大题书名+页码
  - 版框 y245..1615（上下天头/地脚对称 245px；书眉+藏书印居右margin带），界栏细线通高
  - 句读圈一律朱砂色 #874434（用户定稿），位 x+.42em,y+.45em，末行 clamp 不压栏线
  - 注文体系：平衡式双小列（右ceil/左floor），朱色 #874434、0.75×正文，书名号→左侧黑侧线
  - 卷首封面叶：右半嵌卷端原叶书影（含南阳堂诸藏印），左半白叶
  - 正文字号≈行高 0.95（密排），双重偏移描边模拟活字墨涨
· 数据：zw_ch1_data.json（太微赋+例曰，维基文库录文）；朱圈句读由标点对齐生成
用法：python3 build_zwds_fuke.py（输出 复刻-太微赋.pdf）"""
import re, os, json, sys, difflib, math
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, 'zw_ch1_data.json'), encoding='utf-8'))
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

# ---------- 句读对齐 ----------
def align_marks(main_stream, punct_stream):
    marks = set()
    n = 0
    for c in punct_stream:
        if '\u4e00' <= c <= '\u9fff':
            n += 1
        elif c in '。？！；，、':   # 句点+读点皆圈（旧刻圈点密度≈每列3-6处）
            marks.add(n)
    dz2main = {}
    sm = difflib.SequenceMatcher(None, main_stream, ''.join(c for c in punct_stream if '\u4e00' <= c <= '\u9fff'), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2-i1):
                dz2main[j1+k] = i1+k
    out = set()
    for m in marks:
        for back in range(4):
            if m-1-back in dz2main:
                out.add(dz2main[m-1-back]); break
    return out

# ---------- 排版：卷端固定列 + 正文流 + 平衡式双行朱注 ----------
class Leaf:
    def __init__(self): self.cells = []   # (col,row,size,ch,color,gi,lane)  color: ink/red/note; lane: 0整列/1右小列/2左小列

COLORMAP = {'ink': INK, 'red': RED, 'note': RED}

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

def typeset(body_stream, punct_stream, notes=None):
    leaves = [Leaf()]
    # 卷端（leaf 1）固定列（大题/篇题用分数行距避免大字叠压）
    L = leaves[0]
    for r, ch in enumerate('新鋟希夷陳先生紫微斗數全書卷之一'):
        L.cells.append((0, r*1.4375, DATI, ch, 'ink', None, 0))
    for ci, col in enumerate(['江西負鼎子潘希尹補輯', '閩關西後裔楊一字參閱', '書林葆和堂葉']):
        for r, ch in enumerate(col):
            L.cells.append((1+ci, 10+r, BJ, ch, 'ink', None, 0))
    for r, ch in enumerate('梓行'):
        L.cells.append((3, 18+r, BJ, ch, 'ink', None, 0))
    for r, ch in enumerate('太微賦'):
        L.cells.append((4, 0.5+r*1.5, PIANTI, ch, 'ink', None, 0))
    for r, ch in enumerate('函實'):
        L.cells.append((4, 17+r, SMALL, ch, 'ink', None, 0))
    # 正文流：卷端自第 5 列起，每叶 10 列；注=平衡式双小列占 ceil(n/2) 大字行，注毕同列续排
    marks = align_marks(body_stream, punct_stream)
    notes_at = {}
    for anchor, ntext in (notes or []):
        pos = body_stream.find(anchor)
        assert pos >= 0, '注文锚点未命中: ' + anchor
        notes_at[pos + len(anchor) - 1] = ntext
    gi = 0
    col = 5; row = 0
    def new_col():
        nonlocal col, row
        col += 1; row = 0
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0
    for ch in body_stream:
        if row >= ROWS: new_col()
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0; row = 0
        leaves[-1].cells.append((col, row, BIG, ch, 'ink', gi, 0))
        gi += 1; row += 1
        ntext = notes_at.get(gi - 1)
        if not ntext: continue
        nstream, nmarks, nbooks = parse_note(ntext)
        n = len(nstream)
        if not n: continue
        # 整列让位：注独占列（右小列先满→左小列→溢出另起注列），注毕正文续次列
        col += 1; row = 0
        if col >= LEAF_COL: leaves.append(Leaf()); col = 0
        i = 0
        while i < n:
            for lane in (1, 2):
                seg = nstream[i:i+ROWS]
                if not seg: break
                for k, c2 in enumerate(seg):
                    leaves[-1].cells.append((col, k, NOTE, c2, 'note', None, lane))
                for m in nmarks:
                    if i <= m < i + len(seg):
                        leaves[-1].cells.append((col, m-i, NOTE, '', 'note', 'mark', lane))
                for (b0, b1) in nbooks:
                    lo, hi = max(b0, i), min(b1, i+len(seg)-1)
                    for j in range(lo, hi+1):
                        leaves[-1].cells.append((col, j-i, NOTE, '', 'note', 'bookline', lane))
                i += len(seg)
            col += 1
            if col >= LEAF_COL: leaves.append(Leaf()); col = 0
        row = 0
    return leaves, marks

# ---------- 渲染 ----------
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
    for ch in '紫微斗數全書':
        put_char(page, px(GUT_CX), cy, ch, tsize, INK)
        cy += px(94)
    # 天头右上：藏书印 + 书眉竖排书名
    draw_shuyin(page, px(20), px(1470), px(104), px(312))   # 长条形鉴藏章（vYinn 式）置左下角（用户定稿）
    hy, msz, mcol = px(110), 46*PXP, (0.30, 0.27, 0.24)
    for ch in '紫微斗數全書':
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
        iw, ih = 900, int(900*1340/875)
        ix = ((GUT_CX+LCW/2) + FR_X1)/2 - iw/2      # 书影置右半（前片惯例）
        iy = (FR_Y0 + FR_Y1)/2 - ih/2
        page.insert_image(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)),
                          filename=os.path.join(ROOT, 'assets', 'zw_cover_shiying.jpg'))
        page.draw_rect(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)), color=INK, width=px(2))
    else:
        if lf_r is not None: draw_halfleaf(page, lf_r, FR_X1, marks)
    if lf_l is not None: draw_halfleaf(page, lf_l, FR_X0+HALF_W, marks)

def main():
    taiwei = ''.join(DATA['taiwei'])
    li = ''.join(DATA['li'])
    punct = taiwei + li
    body_stream = re.sub(r'[，。：；！？、「」『』（）〔〕]', '', punct)
    leaves, marks = typeset(body_stream, punct, DATA.get('notes'))
    n_body = sum(1 for lf in leaves for c in lf.cells if isinstance(c[5], int))
    assert n_body == len(body_stream), (n_body, len(body_stream))
    for lf in leaves:
        for (col, row, size, ch, color, gi, lane) in lf.cells:
            assert 0 <= col < LEAF_COL and 0 <= row < ROWS, (col, row, ch)
    doc = fitz.open()
    render_spread(doc, None, None, None, marks, cover=True)   # 卷首：封面叶（卷端书影+真藏印）
    # 逐叶一一对应（用户定稿）：左半原书叶截图、右半对应复刻叶。
    # 叶位对应按原书叶面实察（原件：WorkBuddy/书籍/新鋟希夷陳先生紫微斗数全書１.pdf 第5-6开）：
    # 复刻叶一↔卷端大题叶；叶二↔「乎紫微舍躔…例曰起」；叶三↔「文拱命貴…」；
    # 叶四↔「文曲於妻宮…」；叶五↔「…至此誠玄微矣」次接形性賦
    PAIRS = {0: ('zw_leaf2.jpg', '原書葉　卷端大題與太微賦起首'),
             1: ('zw_leaf5.jpg', '原書葉　太微賦續與例曰起首'),
             2: ('zw_leaf4.jpg', '原書葉　太微賦例曰諸格'),
             3: ('zw_leaf6.jpg', '原書葉　例曰諸格續　蟾宮折桂之條'),
             4: ('zw_leaf7.jpg', '原書葉　例曰篇末　次接形性賦　南陽堂刊本、書格日本公文書馆藏本')}
    for i, lf in enumerate(leaves):
        src, cap = PAIRS.get(i, (None, None))
        render_pair_page(doc, lf, i+1, marks, src, cap)
    out = os.path.join(ROOT, '复刻-太微赋.pdf')
    try:
        doc.subset_fonts()
    except Exception:
        pass
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 卷首封面 1 + {len(leaves)} 对页（左原叶右复刻一一对应）, 正文 {n_body} 字, 句读圈 {len(marks)}, 朱注字 {sum(1 for lf in leaves for c in lf.cells if c[4] == "note")}')

if __name__ == '__main__':
    main()

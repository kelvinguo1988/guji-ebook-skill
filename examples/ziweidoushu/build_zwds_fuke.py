#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗数全书》复刻本生成器 —— 品类 B：直排刻本风格（对页 spread，vRain 式）
· 行款：南阳堂刊本实测——半叶 10 行、行 20 字、四周双边、白口对鱼尾
· 数据：zw_ch1_data.json（太微赋+例曰，维基文库录文）；朱圈句读由标点对齐生成
· 版心：上下鱼尾 + 书名「紫微斗數全書」+ 页码；卷端页含大题/牌记/篇题
用法：python3 build_zwds_fuke.py（输出 复刻-太微赋.pdf）"""
import re, os, json, sys, difflib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, 'zw_ch1_data.json'), encoding='utf-8'))

# ---------- 行款（南阳堂实测） ----------
PX = 240/25.4
PXP = 72.0/240
CV_W, CV_H = 2480, 1860
M_TOP, M_BOT, M_SIDE = 200, 50, 50
LEAF_COL = 10                        # 每半叶 10 行
ROWS = 20                            # 行 20 字
GUTTER = 120
HALF_PX = (CV_W - 2*M_SIDE - GUTTER) / 2     # 1130
COL_W = HALF_PX / LEAF_COL / PX
ROW_H = (CV_H - M_TOP - M_BOT) / ROWS / PX
PAGE_W, PAGE_H = CV_W/PX, CV_H/PX
BIG = 104*PXP                        # 大字 104px（行20字·满格密排）
SMALL = 0                            # 本篇无注文，全大字
STROKE_W = 1.0
INK = (0.08, 0.07, 0.065)
RED = (0.66, 0.14, 0.10)
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
        elif c in '。？！；':
            marks.add(n)
    dz2main = {}
    sm = difflib.SequenceMatcher(None, main_stream, ''.join(c for c in punct_stream if '\u4e00' <= c <= '\u9fff'), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2-i1): dz2main[j1+k] = i1+k
    out = set()
    for m in marks:
        for back in range(4):
            if m-1-back in dz2main:
                out.add(dz2main[m-1-back]); break
    return out

# ---------- 排版 ----------
class Leaf:
    def __init__(self): self.cells = []

def typeset(items, marks_main_ref):
    """items: [(kind, text)] kind: p(经文)/lead(卷端题署，逐列)/biaoji(牌记)/title(篇题)
    返回 leaves, mark_positions"""
    leaves = [Leaf()]
    col = row = 0
    def new_leaf():
        nonlocal col, row
        leaves.append(Leaf()); col = row = 0
    def next_col():
        nonlocal col, row
        col += 1; row = 0
        if col >= LEAF_COL: new_leaf()
    def put_big(ch):
        nonlocal col, row
        if row >= ROWS: next_col()
        leaves[-1].cells.append((col, row, 'big', ch, False))
        row += 1
    def put_red(ch):   # 朱字（篇题等强调，本篇篇题用墨+圈）
        put_big(ch)
    # 卷端：大题列 / 牌记列 / 篇题列 各自起列
    gi = -1
    main_chars = []
    for it_idx, (kind, txt) in enumerate(items):
        for ch in txt:
            if not ch.strip(): continue
            if ch == '○':
                if row >= ROWS: next_col()
                leaves[-1].cells.append((col, row, 'big', '○', False))
                row += 1
                continue
            if row >= ROWS: next_col()
            leaves[-1].cells.append((col, row, 'big', ch, kind == 'red'))
            if kind == 'p':
                main_chars.append(ch); gi += 1
            row += 1
        if kind in ('lead', 'biaoji', 'title'):
            next_col()
    main_stream = ''.join(main_chars)
    mark_positions = align_marks(main_stream, marks_main_ref) if marks_main_ref else set()
    return leaves, mark_positions

# ---------- 渲染 ----------
PXT2 = 72.0/240
def px(v): return v*PXT2

def draw_halfleaf(page, leaf, x0, y0, marks, maps):
    bw, bh = px(1130), px(1610)
    page.draw_rect(fitz.Rect(x0, y0, x0+bw, y0+bh), color=INK, width=px(10))
    page.draw_rect(fitz.Rect(x0+px(6), y0+px(6), x0+bw-px(6), y0+bh-px(6)), color=INK, width=px(1))
    colw = px(HALF_PX/LEAF_COL)
    for c in range(1, LEAF_COL):
        x = x0 + c*colw
        page.draw_line(fitz.Point(x, y0+px(6)), fitz.Point(x, y0+bh-px(6)), color=INK, width=px(1))
    CW = px(HALF_PX/LEAF_COL); RH = px(1610/ROWS)
    for (col, row, kind, ch, red) in leaf.cells:
        if ch == '○':
            x = x0 + (LEAF_COL-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            page.draw_circle(fitz.Point(x, y), min(CW, RH)*0.38, color=INK, width=px(2))
            continue
        x = x0 + (LEAF_COL-1-col)*CW + CW/2
        y = y0 + row*RH + RH/2
        size = BIG
        color = RED if red else INK
        tw = tlen(ch, size)
        # 加粗用双重偏移绘制（render_mode=2 描边在 CID 字体上会糊死字形）
        for dx in (0.0, STROKE_W):
            page.insert_text((x-tw/2+dx, y+size*0.36), ch, fontname='kai', fontsize=size,
                             color=color, fill=color)
        gi = maps.get((col, row))
        if gi is not None and gi in marks:
            page.draw_circle(fitz.Point(x-CW*0.34, y+RH*0.34), min(CW, RH)*0.14,
                             color=RED, width=px(1.5))

def draw_shuyin(page, x, y, text4):
    side = px(150)
    page.draw_rect(fitz.Rect(x, y, x+side, y+side), color=RED, width=px(6))
    order = [0, 2, 1, 3]; cell = side/2
    for i, ch in enumerate(text4):
        ccx = x + (1 if order[i] in (0, 2) else 0)*cell + cell/2
        ccy = y + (0 if order[i] in (0, 1) else 1)*cell + cell/2
        size = px(52); tw = tlen(ch, size)
        page.insert_text((ccx-tw/2, ccy+size*0.36), ch, fontname='kai', fontsize=size, color=RED, fill=RED)

def render_spread(doc, lf_r, lf_l, folio, maps_r, maps_l, marks_main=set()):
    page = doc.new_page(width=px(CV_W), height=px(CV_H))
    page.insert_font(fontname='kai', fontfile=KAI)
    page.insert_image(fitz.Rect(0, 0, px(CV_W), px(CV_H)),
                      filename=os.path.join(ROOT, 'assets', 'paper_vr.jpg'), keep_proportion=False)
    x_r = px(M_SIDE + HALF_PX + GUTTER); x_l = px(M_SIDE); y0 = px(M_TOP)
    cx = px(CV_W/2)
    page.draw_line(fitz.Point(cx, px(12)), fitz.Point(cx, px(CV_H-12)), color=INK, width=px(0.8))
    def fishtail(fy, flip=False):
        lcw = px(GUTTER); fh2 = px(80)
        if not flip:
            pts = [(cx-lcw/2, fy), (cx+lcw/2, fy), (cx+lcw/2, fy+fh2), (cx, fy+fh2*0.62), (cx-lcw/2, fy+fh2)]
            lw_y = fy - px(5)
        else:
            pts = [(cx-lcw/2, fy+fh2), (cx+lcw/2, fy+fh2), (cx+lcw/2, fy+fh2*0.38), (cx, fy+fh2), (cx-lcw/2, fy+fh2*0.38)]
            lw_y = fy + fh2 + px(5)
        page.draw_line(fitz.Point(cx-lcw/2, lw_y), fitz.Point(cx+lcw/2, lw_y), color=INK, width=px(15))
        page.draw_polyline([fitz.Point(*p) for p in pts] + [fitz.Point(*pts[0])],
                           color=INK, width=px(1.5), fill=INK)
    fishtail(px(450)); fishtail(px(1550-80), flip=True)
    # 版心书名 + 页码
    tsize = px(65)
    cy = px(1250) - 7*tsize*0.9/2 + tsize
    for ch in '紫微斗數全書':
        for dx in (0.0, 0.4):
            page.insert_text((cx-tlen(ch, tsize)/2+dx, cy), ch, fontname='kai', fontsize=tsize, color=INK, fill=INK)
        cy += tsize*0.9
    cn = ['〇','一','二','三','四','五','六','七','八','九','十']
    fs = cn[folio] if folio <= 10 else ('十'+cn[folio-10] if folio < 20 else '二十')
    psz = px(30)
    page.insert_text((cx-tlen(fs, psz)/2, px(540)+psz), fs, fontname='kai', fontsize=psz, color=INK, fill=INK)
    draw_shuyin(page, px(CV_W-320), px(60), '繭齋藏書')
    hsz = px(30); hy = px(60)
    for ch in '紫微斗數全書':
        page.insert_text((px(CV_W-70)-tlen(ch, hsz)/2, hy), ch, fontname='kai', fontsize=hsz,
                         color=(0.35, 0.32, 0.28), fill=(0.35, 0.32, 0.28))
        hy += hsz*1.3
    if lf_r is not None: draw_halfleaf(page, lf_r, x_r, y0, marks_main, maps_r)
    if lf_l is not None: draw_halfleaf(page, lf_l, x_l, y0, marks_main, maps_l)

def main():
    taiwei = ''.join(DATA['taiwei'])
    li = ''.join(DATA['li'])
    punct = taiwei + li
    # 复刻流：正文无标点（维基文库标点仅用于句读对齐）
    body_stream = re.sub(r'[，。：；！？、「」『』（）〔〕]', '', punct)
    items = [('lead', '新鍥希夷陳先生紫微斗數全書卷之一'),
             ('biaoji', '江西閔子潘希尹補輯　閩關西後商楊一字參閱　書林葉貴和堂'),
             ('title', '○太微赋'),
             ('p', body_stream)]
    punct_stream = punct
    leaves, mark_positions = typeset(items, punct_stream)
    maps_per_leaf = []
    gi = 0
    for lf in leaves:
        m = {}
        for (col, row, kind, ch, red) in lf.cells:
            if ch not in ('○', '■'):
                m[(col, row)] = gi; gi += 1
        maps_per_leaf.append(m)
    doc = fitz.open()
    spreads = [(leaves[i], leaves[i+1] if i+1 < len(leaves) else None, i+1)
               for i in range(0, len(leaves), 2)]
    for lf_r, lf_l, folio in spreads:
        render_spread(doc, lf_r, lf_l, folio, maps_per_leaf[folio-1],
                      maps_per_leaf[folio] if folio < len(leaves) else {}, mark_positions)
    out = os.path.join(ROOT, '复刻-太微赋.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: {len(leaves)} 叶 / {len(spreads)} 对页, 大字 {gi}, 句读 {len(mark_positions)}')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《紫微斗數全書》全书复刻生成器（南阳堂刊本）
数据源：/tmp/zwalign_out.json（align_zwds_full.py 产物：录文流 + 逐叶对齐）
版式（沿用第一章定稿）：
 · text 叶 → 对照页：左半原书叶图、右半复刻叶（一一对应）
 · 卷端/篇题 title 叶 → 复刻题叶（大题+篇题大字列，右半）
 · other 叶（图/表/命例/无录文）→ 整版原叶仿页：两半叶原图并置（或单叶居中）
 · 卷首封面叶复用第一章（zw_cover_shiying.jpg）
用法：python3 build_zwds_fuke_full.py"""
import os, json, sys
import fitz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_zwds_fuke as E
from build_zwds_fuke import px, PXP, CV_W, CV_H, GUT_CX, LCW, FR_X0, FR_X1, FR_Y0, FR_Y1, \
    HALF_W, LEAF_COL, ROWS, COL_W, ROW_H, INK, RED, BIG, DATI, PIANTI, OUT_W, OUT_H, \
    page_chrome, draw_halfleaf, put_char, Leaf

ROOT = os.path.dirname(os.path.abspath(__file__))
ALIGN = json.load(open('/tmp/zwalign_out.json', encoding='utf-8'))
STREAM, LEAVES = ALIGN['stream'], ALIGN['leaves']
STREAM_MARKS = None  # 由 marks 字段自带

CAP = LEAF_COL * ROWS   # 230 字/叶

def cn_num(n):
    if n < len(E.CN_NUM): return E.CN_NUM[n]
    d = '〇一二三四五六七八九'
    s = str(n)
    if len(s) == 2: return ('' if s[0] == '1' else d[int(s[0])]) + '十' + (d[int(s[1])] if s[1] != '0' else '')
    if len(s) == 3: return d[int(s[0])] + '百' + (d[int(s[1])] if s[1] != '0' else '') + '十' + (d[int(s[2])] if s[2] != '0' else '')
    return s

def half_img(name):
    p = os.path.join(ROOT, 'assets', 'full_embed', name + '.jpg')
    if not os.path.exists(p):
        p = os.path.join(ROOT, 'assets', 'full', name + '.jpg')
    return p if os.path.exists(p) else None

def place_half_image(page, path, right_edge_x0, cap_text=None):
    """把一个半叶原图放入版框左/右半区（x0,x1 区间），保持原叶比例、整叶完整"""
    from PIL import Image
    x0, x1 = right_edge_x0
    im = Image.open(path)
    sc = min((x1 - x0 - 60) / im.width, 1520 / im.height)
    w, h = im.width * sc, im.height * sc
    x = (x0 + x1) / 2 - w / 2
    y = FR_Y0 + 40 + (1520 - h) / 2
    page.insert_image(fitz.Rect(px(x), px(y), px(x + w), px(y + h)), filename=path)
    page.draw_rect(fitz.Rect(px(x), px(y), px(x + w), px(y + h)), color=INK, width=px(2))
    if cap_text:
        cfs = 9.2
        tw = E.FONT.text_length(cap_text, fontsize=cfs)
        page.insert_text(((x0 + x1) / 2 * PXP - tw / 2, px(FR_Y1) - px(14)), cap_text,
                         fontname='kai', fontsize=cfs, color=(0.35, 0.32, 0.28))

def put_vnum(page, cx, cy, s, size):
    """书口叶次竖排：逐字沿中线堆叠（横排三字即溢出 120px 书口）"""
    sp = size * 1.22
    for i, ch in enumerate(s):
        put_char(page, px(cx), px(cy - (len(s) - 1) * sp / 2 + i * sp), ch, size * PXP, INK)

def render_pair(doc, leaf, marks, seq):
    """对照页：左原叶、右复刻"""
    lf = Leaf()
    text = STREAM[leaf['start']:leaf['end']]
    for col in range(LEAF_COL):
        for row in range(ROWS):
            i = col * ROWS + row
            if i < len(text):
                lf.cells.append((col, row, BIG, text[i], 'ink', i, 0))
    page = page_chrome(doc)
    for c in range(1, LEAF_COL):
        x = FR_X1 - COL_W * c
        page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    draw_halfleaf(page, lf, FR_X1, marks)
    put_vnum(page, GUT_CX, 1510, cn_num(seq), 41)
    p = half_img(leaf['name'])
    if p:
        place_half_image(page, p, (FR_X0, GUT_CX - LCW / 2),
                         '原書葉　' + leaf['name'].replace('_', ' '))
    else:
        for c in range(1, LEAF_COL):
            x = FR_X0 + COL_W * c
            page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))

def render_title(doc, leaf, seq):
    """卷端/篇题复刻叶：右半大字题列，左半原叶图"""
    page = page_chrome(doc)
    for c in range(1, LEAF_COL):
        x = FR_X1 - COL_W * c
        page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    lf = Leaf()
    title = leaf['anchor'].replace('○', '')
    body = title[:20] if title else ''
    for r, ch in enumerate(body):
        lf.cells.append((0, r, DATI, ch, 'ink', None, 0))
    draw_halfleaf(page, lf, FR_X1, set())
    put_vnum(page, GUT_CX, 1510, cn_num(seq), 41)
    p = half_img(leaf['name'])
    if p:
        place_half_image(page, p, (FR_X0, GUT_CX - LCW / 2), '原書葉　' + leaf['name'].replace('_', ' '))
    else:
        for c in range(1, LEAF_COL):
            x = FR_X0 + COL_W * c
            page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))

def render_faximile(doc, names, seq, cap='原書葉　南陽堂刊本　無録文存世・整版呈現'):
    """整版仿页：左右半各贴原叶图（同一物理对页的两半叶）或单叶居中"""
    page = page_chrome(doc)
    if len(names) == 2:
        r, l = names            # 阅读序 R 前 L 后；物理右半=R、左半=L
        p = half_img(r)
        if p: place_half_image(page, p, (GUT_CX + LCW / 2, FR_X1))
        p = half_img(l)
        if p: place_half_image(page, p, (FR_X0, GUT_CX - LCW / 2))
    else:
        p = half_img(names[0])
        if p: place_half_image(page, p, (FR_X0, GUT_CX - LCW / 2))
    put_vnum(page, GUT_CX, 1510, cn_num(seq), 41)
    tw = E.FONT.text_length(cap, fontsize=9.2)
    page.insert_text((px((FR_X0 + FR_X1) / 2) - tw / 2, px(FR_Y1) - px(6)), cap,
                     fontname='kai', fontsize=9.2, color=(0.35, 0.32, 0.28))

def main():
    # 段界与缺图容错：text 叶段超容量（夹注混流）或过短（假锚点）→ 降级为整版仿页
    hits = [i for i, l in enumerate(LEAVES) if l['kind'] == 'text']
    for j, i in enumerate(hits):
        l = LEAVES[i]
        if 'end' not in l:
            continue
        n = l['end'] - l['start']
        if n > CAP or (n < 40 and j < len(hits) - 1):
            l['kind'] = 'other'
            l['demoted'] = True
    dem = [l['name'] for l in LEAVES if l.get('demoted')]
    doc = fitz.open()
    E._PAPER_XREF = None
    E.render_spread(doc, None, None, None, set(), cover=True)   # 封面叶（复用第一章定稿）
    seq = 0
    i = 0
    n = len(LEAVES)
    pending_other = []
    def flush_other():
        nonlocal seq
        if not pending_other: return
        seq += 1
        if len(pending_other) == 2 and pending_other[0][:-1] == pending_other[1][:-1] \
           and pending_other[0].endswith('R') and pending_other[1].endswith('L'):
            render_faximile(doc, list(pending_other), seq)   # 同一物理对页：右R左L
        else:
            for nm in pending_other:
                render_faximile(doc, [nm], seq if nm == pending_other[0] else seq + 1)
            seq += len(pending_other) - 1
        pending_other.clear()
    while i < n:
        l = LEAVES[i]
        if l['kind'] == 'text':
            flush_other()
            seq += 1
            render_pair(doc, l, set(l.get('marks', [])), seq)
        elif l['kind'] == 'title':
            flush_other()
            seq += 1
            render_title(doc, l, seq)
        else:
            pending_other.append(l['name'])
            if len(pending_other) == 2:
                flush_other()
        i += 1
    flush_other()
    out = os.path.join(ROOT, '复刻-紫微斗数全书.pdf')
    try:
        doc.subset_fonts()
    except Exception:
        pass
    doc.save(out, garbage=4, deflate=True)
    ntext = sum(1 for l in LEAVES if l['kind'] == 'text')
    ntit = sum(1 for l in LEAVES if l['kind'] == 'title')
    noth = sum(1 for l in LEAVES if l['kind'] == 'other')
    cov = sum(l['end'] - l['start'] for l in LEAVES if l['kind'] == 'text')
    print(f'{out}: {seq} 页（text {ntext} / title {ntit} / other {noth}·降级 {len(dem)}）覆盖 {cov}/{len(STREAM)}')
    if dem: print('降级叶:', dem)

if __name__ == '__main__':
    main()

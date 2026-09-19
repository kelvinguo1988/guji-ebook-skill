#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》复刻本生成器 —— 品类 B：古籍刻本风格直排复刻（参考 vRain 思路）
· 行款参数取自元刻实测：半叶十三行、行二十三字、小字双行同、黑口、四周双边、框高205mm宽124mm
· 数据：book_data.json（经 p / 王冰注 zhu / 新校正 xiao 三层，单一来源与整理本共享）
· 朱圈句读：以殆知阁标点录文对齐经文，还原元刻朱圈句读位置
· 版式：直排右起、界行、双行夹注、版心（鱼尾+卷次篇名+叶次）
用法：python3 build_neijing_fuke.py [篇次=1..81]（默认 1，输出复刻 PDF）"""
import re, os, json, sys, math

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from content_nj import TITLES

BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))

# ---------- 行款参数（元刻实测） ----------
PAGE_W, PAGE_H = 178, 268          # mm，半叶比例放大
BOX_W, BOX_H = 124, 205            # 版框：宽124 × 高205（元刻框宽×框高）
COLS, ROWS = 13, 23                # 十三行，行二十三字
MARGIN_X = (PAGE_W - BOX_W) / 2
MARGIN_TOP, MARGIN_BOT = 30, 33    # 天头/地头（地头含版心）
COL_W = BOX_W / COLS
ROW_H = BOX_H / ROWS
BIG = COL_W * 0.78 * 72 / 25.4     # 大字 pt（≈23pt）
SMALL = BIG * 0.52                 # 小字（双行注）

import fitz as _fitz
KAI = os.path.join(ROOT, 'fonts', 'LXGWWenKai-Medium.ttf')
FONT = _fitz.Font(fontfile=KAI)

def tlen(ch, size):
    return FONT.text_length(ch, fontsize=size)
KAI_R = os.path.join(ROOT, 'fonts', 'LXGWWenKai-Regular.ttf')

# ---------- 句读对齐 ----------
DZ_PUNCT_FILE = '/tmp/suwen_daizhige.txt'

def load_punct_index():
    """殆知阁标点文本 → {篇号: [(汉字流, 圈点位置集合)]}"""
    s = open(DZ_PUNCT_FILE, encoding='utf-8').read().replace('\ufeff', '')
    paras = [re.sub(r'^[\s\u3000]+', '', x) for x in s.split('\n')]
    idx, cur, num = {}, None, 0
    CN = '一二三四五六七八九十'
    def c2n(cn):
        d = {c: i+1 for i, c in enumerate(CN)}
        if cn in d: return d[cn]
        if cn.startswith('十'): return 10 + (d.get(cn[1:], 0) if len(cn) > 1 else 0)
        if '十' in cn:
            a, b = cn.split('十', 1)
            return d.get(a, 0)*10 + (d.get(b, 0) if b else 0)
        return 0
    for p in paras:
        m = re.match(r'^([\u4e00-\u9fff（）]{2,14}篇第[一二三四五六七八九十百零]+)$', p)
        if m:
            num = c2n(re.search(r'第([一二三四五六七八九十百零]+)', m.group(1)).group(1))
            cur = m.group(1); idx[num] = ''
            continue
        if num and cur and not p.startswith('卷第'):
            idx[num] += p
    out = {}
    for n, txt in idx.items():
        chars, marks = [], set()
        for c in txt:
            if '\u4e00' <= c <= '\u9fff':
                chars.append(c)
            elif c in '。？！；':
                marks.add(len(chars))   # 圈点画在该句末字之后的缝隙
        out[n] = (''.join(chars), marks)
    return out

def align_marks(main_stream, dz_stream, dz_marks):
    """把殆知阁句读位置对齐到复刻正文流：difflib 全局对齐（容异体/异文）"""
    import difflib
    sm = difflib.SequenceMatcher(None, main_stream, dz_stream, autojunk=False)
    dz2main = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                dz2main[j1 + k] = i1 + k
    out = set()
    for mpos in dz_marks:
        for back in range(0, 4):
            if mpos - 1 - back in dz2main:
                out.add(dz2main[mpos - 1 - back])
                break
    return out

# ---------- 排版核心 ----------
class Leaf:
    def __init__(self):
        self.cells = []   # (col, row, kind, char) kind: big/small_r/small_l  行=格号(0-based 自上而下)
        self.col_used_small = {}  # col -> 已用小字数（右小列与左小列合计，交替填充）

def typeset_pian(n, vol_label, pian_title, stream_items, marks):
    """stream_items: [(kind, text)] kind: p/zhu/xiao；返回叶列表"""
    leaves = [Leaf()]
    col, row = 0, 0            # col 0 = 最右列
    small_state = None         # None | ('r', count) | ('l', count)：当前注列填充状态

    def new_leaf():
        nonlocal col, row, small_state
        leaves.append(Leaf()); col, row, small_state = 0, 0, None

    def next_col():
        nonlocal col, row, small_state
        col += 1; row = 0; small_state = None
        if col >= COLS:
            new_leaf()

    def put_big(ch):
        nonlocal col, row
        leaves[-1].cells.append((col, row, 'big', ch))
        row += 1
        if row >= ROWS:
            next_col()

    def put_note(text):
        """注段双行小字：左右小列平衡（右列 ceil(n/2) 字、左列 floor(n/2) 字），
        占 ceil(n/2) 个大字行；当前列放不下则整列起排。注毕经文同列续排。"""
        nonlocal col, row
        chars = [ch for ch in text if ch.strip()]
        n = len(chars)
        if n == 0:
            return
        while n > 0:
            room = ROWS - row
            span = (n + 1) // 2
            if room <= 0:
                next_col()
                continue
            take = min(n, room * 2 if room < span else n)
            tr = (take + 1) // 2          # 本轮右小列字数
            len_r = (n + 1) // 2 if take == n else room
            # 放置：take 个字 → 右小列 tr 字 + 左小列 take-tr 字
            for k, ch in enumerate(chars[:take]):
                if k < tr:
                    leaves[-1].cells.append((col, row + k, 'r', ch))
                else:
                    leaves[-1].cells.append((col, row + (k - tr), 'l', ch))
            row += tr
            n -= take
            chars = chars[take:]
            if n > 0:
                next_col()

    # 篇首：卷端大题 + 题署 + 篇题（各自起列，原书卷端式）
    lead = [('p', f'新刊補註釋文黃帝內經素問{vol_label}'),
            ('p', '啓玄子次註林億孫奇高保衡等奉勅校正孫兆重改誤'),
            ('p', f'○{pian_title}')]
    items = list(stream_items)
    lead_len = len(lead)
    # 墨钉还原（元刻实察：「成而登天」下接「天師曰」处墨钉一方，通行本为「廼問於」三字）
    MORDANTS = {1: [('成而登天', 1)]}
    for key, cnt in MORDANTS.get(n, []):
        for i, (k2, t2) in enumerate(items):
            if k2 == 'p' and key in t2:
                items.insert(i + 1, ('mordant', '■' * cnt))
                break
    items = lead + items

    # 句读：先拼接主流字符流（大字部分）与位置映射
    body_chars = []
    for it_idx, (kind, txt) in enumerate(items):
        if it_idx >= lead_len and kind == 'p':
            for ch in txt:
                if '\u4e00' <= ch <= '\u9fff':
                    body_chars.append(ch)
    body_stream = ''.join(body_chars)
    from opencc import OpenCC
    _t2s = OpenCC('t2s')
    bs_s = _t2s.convert(body_stream)
    if marks and len(bs_s) == len(body_stream):
        mark_positions = align_marks(bs_s, marks[0], marks[1])
    else:
        mark_positions = set()

    gi = -1   # 大字编号（跳过 ○，与 mark_positions 同体系）
    for it_idx, (kind, txt) in enumerate(items):
        if kind == 'mordant':
            put_big('■')
            continue
        if kind == 'p':
            for ch in txt:
                if not ch.strip() and ch != '○':
                    continue
                if ch == '○':
                    put_big('○')
                    continue
                put_big(ch)
                if it_idx >= lead_len:
                    gi += 1
        else:
            put_note(txt)
        if it_idx < lead_len - 1:
            next_col()   # 卷端题、题署各自起列；篇题后经文连排
    return leaves, mark_positions, gi

# ---------- 渲染 ----------
def draw_leaf(page, leaf, pian_title, vol_label, folio, marks_main, char_pos_map):
    import fitz
    mm = 72 / 25.4
    W, H = PAGE_W*mm, PAGE_H*mm
    x0 = MARGIN_X*mm
    y0 = MARGIN_TOP*mm + 1.6*mm
    bw, bh = BOX_W*mm, BOX_H*mm
    # 纸底色（宣纸白）
    page.draw_rect(fitz.Rect(0, 0, W, H), color=None, fill=(0.993, 0.984, 0.955))
    # 四周双边：外粗内细
    page.draw_rect(fitz.Rect(x0, y0, x0+bw, y0+bh), color=(0.15, 0.13, 0.11), width=1.6)
    page.draw_rect(fitz.Rect(x0+1.2*mm, y0+1.2*mm, x0+bw-1.2*mm, y0+bh-1.2*mm), color=(0.15, 0.13, 0.11), width=0.7)
    # 界行（13 列 → 12 条内线）
    for c in range(1, COLS):
        x = x0 + c*COL_W*mm
        page.draw_line(fitz.Point(x, y0+1.2*mm), fitz.Point(x, y0+bh-1.2*mm), color=(0.25, 0.22, 0.19), width=0.55)
    # 版心（地头区域，居中）
    cx = W/2
    ban_y = y0 + bh + 3.2*mm
    # 鱼尾（黑色，朝下）
    fw = 4.6*mm; fh = 3.0*mm
    # 黑口：上下象鼻黑带
    page.draw_rect(fitz.Rect(cx-11*mm, ban_y-2.2*mm, cx+11*mm, ban_y-0.6*mm), color=None, fill=(0.12, 0.10, 0.09))
    page.draw_rect(fitz.Rect(cx-11*mm, ban_y+fh+0.5*mm, cx+11*mm, ban_y+fh+3.0*mm), color=None, fill=(0.12, 0.10, 0.09))
    fish = [fitz.Point(cx, ban_y), fitz.Point(cx+fw/2, ban_y+fh), fitz.Point(cx, ban_y+fh*0.62), fitz.Point(cx-fw/2, ban_y+fh)]
    page.draw_polyline([fish[0], fish[1], fish[2], fish[3], fish[0]], color=(0.1, 0.09, 0.08), width=0.8, fill=(0.1, 0.09, 0.08))
    # 版心文字：卷次 + 篇名首三字 + 叶次
    page.insert_font(fontname='kai', fontfile=KAI)
    # 白口行分列：鱼尾右侧=卷次，左侧=篇名首四字；叶次独立于行末（原书叶次在下鱼尾下）
    tw = tlen(vol_label, 8.5)
    page.insert_text((cx + 3*mm, ban_y + fh + 6.2*mm), vol_label, fontname='kai', fontsize=8.5, color=(0.2, 0.18, 0.15))
    pn = pian_title[:4]
    tpn = tlen(pn, 8.5)
    page.insert_text((cx - 3*mm - tpn, ban_y + fh + 6.2*mm), pn, fontname='kai', fontsize=8.5, color=(0.2, 0.18, 0.15))
    cn = ['〇','一','二','三','四','五','六','七','八','九','十']
    if folio <= 10: fs = cn[folio]
    elif folio < 20: fs = '十' + cn[folio-10]
    elif folio == 20: fs = '二十'
    else: fs = '二十' + cn[folio-20]
    fw2 = tlen(fs, 8.5)
    page.insert_text((cx - 3*mm - tpn - 6*mm - fw2, ban_y + fh + 6.2*mm), fs, fontname='kai', fontsize=8.5, color=(0.62, 0.16, 0.11))

    page.insert_font(fontname='kai', fontfile=KAI)
    page.insert_font(fontname='kair', fontfile=KAI_R)
    CW, RH = COL_W*mm, ROW_H*mm
    for (col, row, kind, ch) in leaf.cells:
        if ch == '■':
            x = x0 + (COLS-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            page.draw_rect(fitz.Rect(x-CW*0.36, y-RH*0.36, x+CW*0.36, y+RH*0.36),
                           color=None, fill=(0.12, 0.10, 0.09))
            continue
        if ch == '■':
            x = x0 + (COLS-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            page.draw_rect(fitz.Rect(x-CW*0.36, y-RH*0.36, x+CW*0.36, y+RH*0.36),
                           color=None, fill=(0.12, 0.10, 0.09))
            continue
        if ch == '○':
            # 墨圈：画圈
            x = x0 + (COLS-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            r = min(CW, RH)*0.30
            page.draw_circle(fitz.Point(x, y), r, color=(0.2, 0.18, 0.15), width=1.0)
            continue
        if kind == 'big':
            x = x0 + (COLS-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            size = BIG
        else:
            side_off = -CW*0.24 if kind == 'r' else CW*0.24
            x = x0 + (COLS-1-col)*CW + CW/2 + side_off
            y = y0 + row*RH + RH/2
            size = SMALL
        tw = tlen(ch, size)
        ty = y + size*0.36
        page.insert_text((x - tw/2, ty), ch, fontname='kai', fontsize=size, color=(0.13, 0.11, 0.10))
        # 朱圈句读：大字且在句读位置 → 圈在字格左下
        if kind == 'big':
            gi = char_pos_map.get((col, row))
            if gi is not None and gi in marks_main:
                page.draw_circle(fitz.Point(x - CW*0.33, y + RH*0.33), min(CW,RH)*0.13,
                                 color=(0.62, 0.16, 0.11), width=0.8)

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    e = BOOK[str(n)]
    vol = next(v for v, (a, b) in [(v, (a, b)) for v, (a, b) in
        {1:(1,7),2:(8,16),3:(17,20),4:(21,30),5:(31,38),6:(39,45),7:(46,55),
         8:(56,61),9:(62,67),10:(68,70),11:(71,74),12:(75,81)}.items() if a <= n <= b])
    vol_label = f'卷之{["一","二","三","四","五","六","七","八","九","十","十一","十二"][vol-1]}'
    pian_title = e['title']
    punct = load_punct_index()
    marks = punct.get(n, ('', set()))
    items = [(k, t.strip()) for pp in e['paras'] for k, t in pp if t.strip()]
    leaves, mark_positions, big_total = typeset_pian(
        n, vol_label, pian_title, items, marks)

    # 大字格位 → 全局大字编号（跳过○，与句读对齐同体系）
    maps_per_leaf = []
    gi = 0
    for li, lf in enumerate(leaves):
        m = {}
        for (col, row, kind, ch) in lf.cells:
            if kind == 'big' and ch != '○':
                m[(col, row)] = gi
                gi += 1
        maps_per_leaf.append(m)

    import fitz
    doc = fitz.open()
    for li, lf in enumerate(leaves):
        page = doc.new_page(width=PAGE_W*72/25.4, height=PAGE_H*72/25.4)
        draw_leaf(page, lf, pian_title, vol_label, li+1, mark_positions, maps_per_leaf[li])
    out = os.path.join(ROOT, f'复刻-上古天真論篇第一.pdf') if n == 1 else os.path.join(ROOT, f'复刻-{pian_title}.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: {len(leaves)} 叶, 大字 {gi}, 句读 {len(mark_positions)} 处')

if __name__ == '__main__':
    main()

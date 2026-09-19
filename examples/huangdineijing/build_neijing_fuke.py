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
# 对页几何：1:1 采用 vRain 24 开 cfg 像素几何（2480×1860 @240dpi → 262×197mm）
PX = 240/25.4                       # px → mm 换算（240dpi）
CV_W, CV_H = 2480, 1860             # vRain 画布
M_TOP, M_BOT = 200, 50              # margins_top/bottom
M_SIDE = 50                         # margins_left/right
LEAF_COL = 12                       # 每半叶列数（leaf_col=24 两半叶）
ROWS = 20                           # 每列字数（010.png 样张款：12 列×20 字大字密排）
GUTTER = 120                        # leaf_center_width 书口 px
COL_W = (CV_W - 2*M_SIDE - GUTTER) / 2 / LEAF_COL / PX   # 半叶列宽 mm ≈9.95
ROW_H = (CV_H - M_TOP - M_BOT) / ROWS / PX              # 行距 mm ≈5.7（密排：行距<字号）
PAGE_W, PAGE_H = CV_W/PX, CV_H/PX   # ≈262×197mm
HALF_W = (CV_W - 2*M_SIDE - GUTTER)/2 / PX
BOX_W = HALF_W
MARGIN_X = M_SIDE/PX
MARGIN_TOP = M_TOP/PX
MARGIN_BOT = M_BOT/PX
BOX_H = (CV_H - M_TOP - M_BOT)/PX

COLS = LEAF_COL                    # 排版列数 = 渲染列数（12）
PXP = 72.0/240                      # px → pt（1px@240dpi = 0.3pt）
BIG = 107*PXP                       # 正文 107px → 32.1pt（墨迹 0.75em≈80px≈行距，样张密排）
SMALL = 45*PXP                      # 批注 45px → 13.5pt
STROKE_W = 1.0                      # 大字浓黑描边（vRain fallback_bold=1.2pt 同思路）
STROKE_S = 0.25

import fitz as _fitz
NOTE_RED_BOOKS = ['太素', '甲乙經', '甲乙', '九卷', '鍼經', '靈樞經', '靈樞', '脈經',
                  '全元起', '楊上善', '皇甫士安', '呂廣', '越人', '天元玉冊',
                  '氣交變大論', '五運行', '本病論', '刺法論', '老子', '淮南子', '莊子',
                  '尚書', '易經', '白虎通', '爾雅', '說文', '漢書', '史記']

# 主字体：齊伋體 combo（与 vRain 完全一致，明代凌閔刻本抠字重建的明体）
KAI = os.environ.get('FK_FONT', os.path.join(ROOT, 'fonts', 'qiji-combo.ttf'))
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
        if row >= ROWS:
            next_col()
        leaves[-1].cells.append((col, row, 'big', ch, False))
        row += 1

    def put_note(text):
        """注段双行小字：左右小列平衡（右列 ceil(n/2) 字、左列 floor(n/2) 字），
        占 ceil(n/2) 个大字行；当前列放不下则整列起排。注毕经文同列续排。"""
        nonlocal col, row
        chars = [ch for ch in text if ch.strip()]
        full = ''.join(chars)
        # 书名染红：在拼接文本上匹配词典，映射回字符位
        red_flags = [False] * len(chars)
        pos = 0
        for k, ch in enumerate(chars):
            if not ch.strip():
                red_flags[k] = red_flags[k-1] if k else False
        # 重建带位置映射的扫描：逐词查找
        joined = ''.join(chars)
        for w in NOTE_RED_BOOKS:
            start = 0
            while True:
                i = joined.find(w, start)
                if i < 0: break
                for k in range(i, i + len(w)):
                    red_flags[k] = True
                start = i + 1
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
                    leaves[-1].cells.append((col, row + k, 'r', ch, red_flags[k]))
                else:
                    leaves[-1].cells.append((col, row + (k - tr), 'l', ch, red_flags[k]))
            row += tr
            n -= take
            chars = chars[take:]
            if row >= ROWS and (n > 0 or True):
                next_col()
            elif n > 0:
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

# ---------- 渲染：vRain 24 开几何 1:1（canvas.pl + 24 cfg 参数） ----------
import fitz
PXT = 72.0/240                      # px → pt（@240dpi）
def px(v): return v * PXT           # px → pt

INK = (0.08, 0.07, 0.065)
RED = (0.66, 0.14, 0.10)
WHITE = (0.97, 0.94, 0.87)

def draw_halfleaf(page, leaf, x0, y0, marks_main, maps, side):
    """半叶：外框 10px、内线 1px、界行；x0/y0 以 pt 计（半叶框左上角）"""
    bw, bh = px(HALF_W*PX), px(BOX_H*PX)
    bw, bh = px(1130), px(1610)     # 半叶框 1130×1610px
    page.draw_rect(fitz.Rect(x0, y0, x0+bw, y0+bh), color=INK, width=px(10))
    page.draw_rect(fitz.Rect(x0+px(6), y0+px(6), x0+bw-px(6), y0+bh-px(6)),
                   color=INK, width=px(1))
    # 界行（12 列 → 11 条内线）
    colw = px(1130/LEAF_COL)
    for c in range(1, LEAF_COL):
        x = x0 + c*colw
        page.draw_line(fitz.Point(x, y0+px(6)), fitz.Point(x, y0+bh-px(6)),
                       color=INK, width=px(1))
    CW = px(1130/LEAF_COL)
    RH = px(1610/ROWS)
    for (col, row, kind, ch, red) in leaf.cells:
        if ch == '■':
            x = x0 + (LEAF_COL-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            page.draw_rect(fitz.Rect(x-CW*0.33, y-RH*0.34, x+CW*0.33, y+RH*0.34),
                           color=None, fill=INK)
            continue
        if ch == '○':
            x = x0 + (LEAF_COL-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            page.draw_circle(fitz.Point(x, y), min(CW, RH)*0.38, color=INK, width=px(2))
            continue
        if kind == 'big':
            x = x0 + (LEAF_COL-1-col)*CW + CW/2
            y = y0 + row*RH + RH/2
            size = BIG
        else:
            side_off = -CW*0.25 if kind == 'r' else CW*0.25
            x = x0 + (LEAF_COL-1-col)*CW + CW/2 + side_off
            y = y0 + row*RH + RH/2
            size = SMALL
        if kind != 'big' and red:
            # 红底白字出处签
            page.draw_rect(fitz.Rect(x-CW*0.22, y-RH*0.42, x+CW*0.22, y+RH*0.42),
                           color=None, fill=RED)
            tw = tlen(ch, size)
            draw_text(page, x-tw/2, y+size*0.36, ch, size, WHITE)
        else:
            tw = tlen(ch, size)
            draw_text(page, x-tw/2, y+size*0.36, ch, size, INK)
        if kind == 'big':
            gi = maps.get((col, row))
            if gi is not None and gi in marks_main:
                page.draw_circle(fitz.Point(x - CW*0.34, y + RH*0.34), min(CW,RH)*0.14,
                                 color=RED, width=px(1.5))

def draw_text(page, x, y, ch, size, color=INK, bold=False):
    page.insert_text((x, y), ch, fontname='kai', fontsize=size, color=color, fill=color)

def draw_fishtail(page, cx, fy, rect_h, tri_h, flip=False):
    """vRain 鱼尾五边形：书口宽顶线 + 两侧下垂 rect_h+tri_h + 中央 V 口 tri_h 深"""
    lcw = px(GUTTER)
    y1 = fy + px(rect_h + tri_h)
    ym = fy + px(rect_h)
    if not flip:
        pts = [(cx-lcw/2, fy), (cx+lcw/2, fy), (cx+lcw/2, y1), (cx, ym), (cx-lcw/2, y1)]
    else:
        pts = [(cx-lcw/2, y1), (cx+lcw/2, y1), (cx+lcw/2, fy+px(rect_h)),
               (cx, fy), (cx-lcw/2, fy+px(rect_h))]
        ym, y1 = fy+px(rect_h), fy
    # 鱼尾上/下粗分割线（fish_linewidth 15px）
    lw_y = fy - px(5) if not flip else fy + px(rect_h+tri_h) + px(5)
    page.draw_line(fitz.Point(cx-lcw/2, lw_y), fitz.Point(cx+lcw/2, lw_y), color=INK, width=px(15))
    page.draw_polyline([fitz.Point(*p) for p in pts] + [fitz.Point(*pts[0])],
                       color=INK, width=px(1.5), fill=INK)

def render_spread(doc, lf_r, lf_l, folio, pian_title, vol_label, marks_main, maps_r, maps_l):
    page = doc.new_page(width=px(CV_W), height=px(CV_H))
    page.insert_font(fontname='kai', fontfile=KAI)
    # vRain 同款宣纸扫描背景
    page.insert_image(fitz.Rect(0, 0, px(CV_W), px(CV_H)),
                      filename=os.path.join(ROOT, 'assets', 'paper_vr.jpg'),
                      keep_proportion=False)
    # 两半叶框位置
    x_r = px(M_SIDE + 1130 + GUTTER)
    x_l = px(M_SIDE)
    y0 = px(M_TOP)
    # 书口：上鱼尾 450、版心书名 1250、页码 540、下鱼尾 1550（cfg 权威值）
    cx = px(CV_W/2)
    draw_fishtail(page, cx, px(450), 50, 30, flip=False)
    draw_fishtail(page, cx, px(1550), 50, 30, flip=True)
    # 版心书名：竖排墨黑 65px（title_y=1250 起，向上排？vRain y 为基线起点向下）
    tsize = px(65)
    chars = list('素問' + vol_label)   # 版心短名（vRain title=书名）
    cy = px(1250) - len(chars)*tsize*0.9/2 + tsize
    for ch in chars:
        page.insert_text((cx - tlen(ch, tsize)/2, cy), ch, fontname='kai', fontsize=tsize,
                         color=INK, fill=INK)
        cy += tsize*0.9
    # 页码（pager_y=540，30px）
    cn = ['〇','一','二','三','四','五','六','七','八','九','十']
    if folio <= 10: fs = cn[folio]
    elif folio < 20: fs = '十' + cn[folio-10]
    elif folio == 20: fs = '二十'
    else: fs = '二十' + cn[folio-20]
    psz = px(30)
    page.insert_text((cx - tlen(fs, psz)/2, px(540) + psz), fs,
                     fontname='kai', fontsize=psz, color=INK, fill=INK)
    # 书房名 logo（底部 y=1680，40px 朱色——仿 cfg logo_position）
    lsz = px(40)
    ltxt = '繭齋藏書'
    ly = px(1680)
    for ch in ltxt:
        page.insert_text((cx - tlen(ch, lsz)/2, ly), ch, fontname='kai', fontsize=lsz,
                         color=RED, fill=RED)
        ly += lsz*1.1
    # 藏书印：右上（样张位置）
    draw_shuyin(page, px(CV_W - 320), px(60), '繭齋藏書')
    # 书眉（框外右上竖排书名，样张右缘）
    hsz = px(30)
    hy = px(60)
    for ch in '黃帝內經素問':
        page.insert_text((px(CV_W - 70) - tlen(ch, hsz)/2, hy), ch, fontname='kai', fontsize=hsz,
                         color=(0.35, 0.32, 0.28), fill=(0.35, 0.32, 0.28))
        hy += hsz*1.3
    if lf_r is not None:
        draw_halfleaf(page, lf_r, x_r, y0, marks_main, maps_r, 'r')
    if lf_l is not None:
        draw_halfleaf(page, lf_l, x_l, y0, marks_main, maps_l, 'l')
    return page

def draw_shuyin(page, x, y, text4):
    side = px(150)
    page.draw_rect(fitz.Rect(x, y, x+side, y+side), color=RED, width=px(6))
    order = [0, 2, 1, 3]
    cell = side/2
    for i, ch in enumerate(text4):
        ccx = x + (1 if order[i] in (0, 2) else 0)*cell + cell/2
        ccy = y + (0 if order[i] in (0, 1) else 1)*cell + cell/2
        size = px(52)
        tw = tlen(ch, size)
        page.insert_text((ccx - tw/2, ccy + size*0.36), ch, fontname='kai', fontsize=size,
                         color=RED, fill=RED)

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
        for (col, row, kind, ch, _red) in lf.cells:
            if kind == 'big' and ch != '○':
                m[(col, row)] = gi
                gi += 1
        maps_per_leaf.append(m)

    doc = fitz.open()
    spreads = []
    for li in range(0, len(leaves), 2):
        rf = leaves[li]
        lf2 = leaves[li+1] if li+1 < len(leaves) else None
        spreads.append((rf, lf2, li+1))
    for lf_r, lf_l, folio in spreads:
        maps_r = maps_per_leaf[folio-1]
        maps_l = maps_per_leaf[folio] if folio < len(leaves) else {}
        render_spread(doc, lf_r, lf_l, folio, pian_title, vol_label, mark_positions, maps_r, maps_l)
    out = os.path.join(ROOT, '复刻-上古天真論篇第一.pdf') if n == 1 else os.path.join(ROOT, f'复刻-{pian_title}.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: {len(leaves)} 叶 / {len(spreads)} 对页, 大字 {gi}, 句读 {len(mark_positions)} 处')

if __name__ == '__main__':
    main()

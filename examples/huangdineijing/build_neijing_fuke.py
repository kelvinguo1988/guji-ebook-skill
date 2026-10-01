#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》B 版复刻本 —— 紫微斗数全书定稿样式引擎（元刻行款 13 行 23 字）
· 逐叶一一对应对页：左半=元刻原书叶真图、右半=对应复刻叶（内容逐叶一致）
· 注=随文夹注：王冰注墨双行 / 新校正朱双行，小行高 0.52×大字行（元刻注密度）
· 朱砂毛笔句读圈 + 郭仲和藏書长条朱文印（vYinn make_seal 合成，用户定稿）
用法：python3 build_neijing_fuke.py   → 復刻-素問·上古天真論篇第一.pdf"""
import re, os, json, sys, math, difflib

ROOT = os.path.dirname(os.path.abspath(__file__))
BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))

# ---------- 画布与行款（vRain 24 开几何 + 元刻行款 13 行 23 字） ----------
PXP = 72.0/240
def px(v): return v*PXP
CV_W, CV_H = 2480, 1860
GUT_CX = CV_W/2
LCW = 120
FR_X0, FR_X1 = 150, 2300
FR_Y0, FR_Y1 = 100, 1760
HALF_W = (FR_X1-FR_X0-LCW)/2
LEAF_COL = 13                          # 元刻：每半叶十三行
ROWS = 23                              # 行二十三字
COL_W = HALF_W/LEAF_COL
ROW_H = (FR_Y1-FR_Y0)/ROWS
OUT_W, OUT_H = 10, 1
INK = (0.08, 0.07, 0.065)
RED = (0.53, 0.27, 0.20)
BIG = 89*PXP
DATI = 95*PXP
PIANTI = 96*PXP
BJ = 77*PXP
NOTE = 37*PXP                          # 注小字（≈0.42×正文，元刻注密度）
NOTE_H = 0.52                          # 注小行高 = 0.52×大字行
STROKE_W = 1.0
WHITE = (0.97, 0.94, 0.87)

from PIL import Image
import fitz
KAI = os.path.join(ROOT, 'fonts', 'qiji-combo.ttf')
FONT = fitz.Font(fontfile=KAI)
def tlen(ch, size): return FONT.text_length(ch, fontsize=size)

_PAPER_XREF = None
SEAL_PNG = os.path.join(ROOT, 'assets', 'seal_gzh.png')

DZ_PUNCT_FILE = '/tmp/suwen_daizhige.txt'

def load_punct_index():
    """殆知阁标点文本 → {篇号: (汉字流, 句末缝隙集合)}"""
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


def align_marks(main_stream, dz_stream, dz_marks):
    """句读对齐（定稿38a24be快速版）：逐句锚定——句末前 12 字为 key 顺序 find（C 层），
    顺序推进防雪崩。dz_stream=汉字流、dz_marks=句末缝隙集合。
    （并行会话曾改为 difflib+逗号重扫版：源流已被滤成纯汉字、标点恒扫不到 → 句读圈 0 回归）"""
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
# （Leaf/COLORMAP 唯一定义在 brush_circle 之后；此处曾有并行会话重复块，已清）

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

class Leaf:
    def __init__(self): self.cells = []   # (col,row,size,ch,color,gkey,lane)

COLORMAP = {'ink': INK, 'red': RED, 'note': RED, 'inknote': INK}


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
            elif gi == 'inkcircle':
                page.draw_circle(fitz.Point(x, y + size*0.06), size*0.40, color=INK, width=px(4.5))
            elif gi == 'bookline':
                lx = x - size*0.55
                page.draw_line(fitz.Point(lx, y-px(ROW_H*0.5)), fitz.Point(lx, y+px(ROW_H*0.5)),
                               color=RED, width=px(2))
            continue
        put_char(page, x, y, ch, size, colr)
        if isinstance(gi, int) and gi in marks:
            cy = min(y + size*0.45, px(FR_Y1) - size*0.18 - px(9))
            brush_circle(page, x + size*0.42, cy, size*0.17, RED, gi)   # 朱砂毛笔圈（用户定稿）

_PAPER_XREF = None
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
    draw_shuyin(page, px(20), px(1470), px(104), px(312))   # 长条形鉴藏章（vYinn 式）置左下角（用户定稿）
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


def main():
    import json
    from opencc import OpenCC
    t2s = OpenCC('t2s').convert
    BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))
    e = BOOK['1']
    pian_title = e['title']
    punct = load_punct_index()
    punct_stream, dz_marks = punct.get(1, ('', set()))
    body, notes, tail = [], [], ''
    for pp in e['paras']:
        for k, t in pp:
            t = t.strip()
            if not t: continue
            if k == 'p':
                clean = re.sub(r'[，。：；！？、「」『』（）〔〕\s]', '', t)
                body.append(clean)
                tail = clean[-12:]
            elif k in ('zhu', 'xiao'):
                kind = 'note'    # 用户定稿：王冰注/新校正均朱双行，与黑色正文区分
                # 连续 zhu 之间无正文=同一条注文被录文拆行（集成本核对证实）→ 合并为一双行连注；
                # 新校正自成一节：合并后按「 新校正」前空格切块
                if k == 'zhu' and notes and notes[-1][0] == tail and notes[-1][2] == 'zhu':
                    lt = notes[-1][1][-1][1]
                    notes[-1][1][-1] = (kind, lt + t)
                else:
                    notes.append((tail, [(kind, t)], k))
            else:
                continue
    notes = [(tl, [(kind, part)
                   for kind, tx in nt
                   for part in re.split(r'\s+(?=新校)', tx) if part.strip()], src)
             for tl, nt, src in notes]
    body_stream = ''.join(body)
    main_s = t2s(body_stream)
    if len(main_s) != len(body_stream):
        main_s = body_stream
    marks = align_marks(main_s, punct_stream, dz_marks)

    # ---------- 元刻逐列锚定（yuan_leaf_anchors.json·目验建表） ----------
    # 叶界与列槽首字全部取自锚定表：复刻第 k 槽首大字 == 元刻第 k 槽首大字
    VAR = str.maketrans('歳眞蓋寫', '嵗真葢冩')
    cstream = body_stream.translate(VAR)
    def afind(key, frm):
        key = key.translate(VAR)
        for n in (len(key), 4, 2, 1):
            p = cstream.find(key[:n], frm)
            if p >= 0: return p
        return -1
    ANCH = json.load(open(os.path.join(ROOT, 'yuan_leaf_anchors.json'), encoding='utf-8'))['leaves']
    notes_at = {}
    for anchor, ntexts, _src in notes:
        pos = body_stream.find(anchor) if anchor else -1
        if not anchor:
            notes_at.setdefault(-1, []).extend(ntexts)   # 正文前之注=篇题下注
        elif pos >= 0:
            notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)
    # 解析锚 → 全局位置；叶界=每叶首个大字锚
    cursor, leaf_slots, starts = 0, [], [0]
    for ent in ANCH:
        sl = []
        for s in ent['slots']:
            if s is None: sl.append(None)
            elif s == 'F': sl.append('F')
            else:
                p = afind(s, cursor)
                if p < 0:
                    print(f'  !! 叶{ent["leaf"]} 锚「{s}」未命中 → 自由排')
                    sl.append('F')
                else:
                    sl.append(p); cursor = p + 1
        leaf_slots.append((ent['leaf'], sl))
        first = next((x for x in sl if isinstance(x, int)), None)
        if first is not None and first not in starts:
            starts.append(first)
    cuts = sorted(set(starts)) + [len(body_stream)]
    assert all(cuts[i] < cuts[i+1] for i in range(len(cuts)-1)), cuts
    print('叶界(锚定):', cuts)

    # ---------- 分叶排版（列锚驱动，注宽预估+溢出续列，行高/行距自适应） ----------
    notes_file = os.path.join(ROOT, 'yuan_leaf1_notes.json')
    lead1 = {'pian': pian_title,
             'pre_notes': '', 'title_note': ''}
    if os.path.exists(notes_file):
        j = json.load(open(notes_file, encoding='utf-8'))
        lead1['pre_notes'] = j.get('merged', '')
        lead1['title_note'] = j.get('col12', '')
    all_marks = set(marks)
    leaves = []
    pending = []          # 跨叶注溢出队列 [(kind, chars, started)]
    for li, (kno, sl) in enumerate(leaf_slots):
        lo = cuts[li]; hi = cuts[li+1] if li + 1 < len(cuts) else len(body_stream)
        seg = body_stream[lo:hi]
        slots_local = []
        for s in sl:
            slots_local.append(s - lo if isinstance(s, int) else s)
        seg_notes = {pos - lo: v for pos, v in notes_at.items() if lo <= pos < hi}
        report = []
        lf = typeset_leaf_slots(seg, seg_notes, slots_local,
                                lead1 if kno == 1 else None,
                                1.0, lo, all_marks, pending, report)
        leaves.append(lf)
        for r in report:
            print(f'  叶{kno} 槽{r[0]}: {r[1]} {r[2]}')
        print(f'  叶{kno}: 大字{len(seg)} 槽锚{sum(1 for x in sl if isinstance(x,int))} 溢出续注{len(pending)}', flush=True)

    # ---------- 比对验证：复刻各槽首大字 vs 元刻锚 ----------
    tot = hit = 0
    for li, (kno, sl) in enumerate(leaf_slots):
        firstb = {}
        for c in leaves[li].cells:
            if c[6] == 0 and c[2] >= BIG*0.999 and c[0] not in firstb:
                firstb[c[0]] = c[3]
        misses = []
        for j, s in enumerate(sl):        # sl 为全局位置
            if isinstance(s, int):
                tot += 1
                if firstb.get(j) == body_stream[s]: hit += 1
                else: misses.append((j+1, body_stream[s], firstb.get(j, '∅')))
        if misses: print(f'  叶{kno} 锚不合: {misses}')
    print(f'列锚命中率: {hit}/{tot}')
    # 注字总量审计：录文注（除被卷端目验转录替代的篇题下注）应全部落版
    exp = sum(len(re.sub(r'\W', '', t)) for pos, lst in notes_at.items() if pos >= 0
              for kind, t in lst)
    placed = sum(1 for lf in leaves for c in lf.cells if c[6])
    lead_lane = sum(1 for c in leaves[0].cells if c[6])
    left = sum(len(ch) for _, ch, _ in pending)
    print(f'注字审计: 应排 {exp} | 实排 {placed - lead_lane} | 卷端目验注列 {lead_lane} | 未消化 {left}')

    # 文本映射导出（EPUB 等下游与 PDF 同源：逐叶大字流 + 锚位注文）
    tmap = {'pian': pian_title, 'lead': lead1, 'leaves': []}
    for li, (kno, sl) in enumerate(leaf_slots):
        lo, hi = cuts[li], cuts[li + 1]
        tmap['leaves'].append({
            'leaf': kno, 'text': body_stream[lo:hi],
            'marks': [m - lo for m in marks if lo <= m < hi],
            'notes': [[pos - lo, v] for pos, v in sorted(notes_at.items()) if lo <= pos < hi]})
    with open(os.path.join(ROOT, 'fuke_text_map.json'), 'w', encoding='utf-8') as f:
        json.dump(tmap, f, ensure_ascii=False, indent=1)

    # 渲染：封面 + 逐叶 pair page（左元刻原叶 / 右复刻叶）
    doc = fitz.open()
    cp = page_chrome(doc)   # 封面叶：右半嵌卷端书影（vRain 卷端嵌真叶书影惯例）
    iw, ih = 900, int(900*2034/1172)
    ix = ((GUT_CX+LCW/2) + FR_X1)/2 - iw/2
    iy = (FR_Y0 + FR_Y1)/2 - ih/2
    cp.insert_image(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)),
                    filename=os.path.join(ROOT, 'assets', 'yuan_cover.jpg'))
    cp.draw_rect(fitz.Rect(px(ix), px(iy), px(ix+iw), px(iy+ih)), color=INK, width=px(2))
    for c in range(1, LEAF_COL):
        x = FR_X0 + COL_W*c
        cp.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(OUT_H))
    dsrc = fitz.open('/Users/sec-t/Downloads/黄帝内经/ZHSY000605 新刊補注釋文黄帝內經素問十二卷 (唐)王冰 注(宋)林億等 校正(宋)孫兆 改誤 元至元五年胡氏古林書堂刻本/001.pdf')
    for li, lf in enumerate(leaves):
        k = li + 1
        pidx = 11 + (k-1)//2
        side_left = (k-1) % 2 == 1
        pg = dsrc[pidx]; r = pg.rect
        x0 = 0 if side_left else r.width/2
        jpg = f'/tmp/yuan_h{k}.jpg'
        if not os.path.exists(jpg):
            dsrc[pidx].get_pixmap(matrix=fitz.Matrix(2, 2),
                clip=fitz.Rect(x0, 0, x0 + r.width/2, r.height)).save(jpg, jpg_quality=85)
        bigs = [c[3] for c in lf.cells if c[2] == BIG]
        cap = f'原書葉　卷一　第{CN_NUM[k] if k < len(CN_NUM) else k}葉'   # 汉字叶次（qiji 无阿拉伯数字形，用数字会成空白）
        render_pair_page(doc, lf, k, all_marks, jpg, cap)
        print(f'  对页{k}: 左=元刻半叶{k} 右=复刻叶{k} 首={"".join(bigs[:3])}', flush=True)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = os.path.join(ROOT, '復刻-素問·上古天真論篇第一.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 封面 1 + {len(leaves)} 对页, 正文 {len(body_stream)} 字, 句读圈 {len(marks)}')

def draw_lead_leaf1(L, lead, scale):
    """叶1 卷端（元刻叶1实察·6x目验）：col0大题、col1题署、col2-9新校正序注双行
    （行距≈1.1×大字行·每行约21字——卷端注疏朗，非随文密注）、col10 ○篇题+题下注起、
    col11 题下注续；正文自 col12（元刻col13）起。"""
    for r, ch in enumerate('新刊補註釋文黃帝內經素問卷之一'):
        L.cells.append((0, r*1.4375, DATI*scale, ch, 'ink', None, 0))
    for r, ch in enumerate('啓玄子次註林億孫奇高保衡等奉勅校正孫兆重改誤'):
        L.cells.append((1, r, BJ*scale, ch, 'ink', None, 0))
    def note_lanes(col, row0, text, kind, h, lane_len):
        chars = [c for c in text if c.strip()]
        nr = min((len(chars)+1)//2, lane_len)
        for j, ch in enumerate(chars[:lane_len*2]):
            ln = 1 if j < nr else 2
            L.cells.append((col, row0 + (j if j < nr else j-nr)*h, NOTE*scale, ch, kind, None, ln))
        return chars[lane_len*2:]
    if lead.get('pre_notes'):
        rest = lead['pre_notes'][:21*2*8]          # 元刻序注实占 col3-10 共8槽，溢出不刻（护篇题列）
        for c0 in range(2, 10):
            if not rest: break
            rest = note_lanes(c0, 0, rest, 'note', 1.1, 21)
    L.cells.append((10, 0, PIANTI*scale, '', 'red', 'inkcircle', 0))   # 篇题墨圈○（矢量绘制，避字体缺字）
    for r, ch in enumerate(lead['pian']):
        L.cells.append((10, 1 + r*1.1, PIANTI*scale, ch, 'ink', None, 0))
    if lead.get('title_note'):
        note_lanes(10, 10, lead['title_note'][:26], 'note', 0.95, 13)
        tail = lead['title_note'][26:]
        if tail:                                   # note_lanes 返回值只含入参切片的余量，续列须直接取全串尾部
            note_lanes(11, 0, tail, 'note', 1.0, 16)

def typeset_leaf_slots(seg, seg_notes, slots, lead, scale, gi0, marks_all, pending, report):
    """列锚驱动排版（用户定稿方案）：slots[k]=该槽首大字在 seg 内的位置 / None=纯注槽 / 'F'=自由续排。
    每槽首大字顶格（头尾段落句子对齐的硬不变式）；注宽=双小行容量预估，
    放不下→整条溢出到下一槽（纯注槽顶格或首大字之后），复刻元刻跨列/跨叶溢注形态。"""
    L = Leaf()
    big = BIG*scale; note = NOTE*scale; nh = NOTE_H
    def lane(col, row, kind, chars):
        n = (len(chars)+1)//2
        for i, ch in enumerate(chars):
            ln = 1 if i < n else 2
            L.cells.append((col, row + (i if i < n else i-n)*nh, note, ch, kind, None, ln))
        return n*nh
    def flush(col, row, until=ROWS):
        while pending and row < until:
            kind, chars, started = pending[0]
            cap = int((until - row)/nh)*2
            if cap < 2: break
            take, rest = chars[:cap], chars[cap:]
            row += lane(col, row, kind, take)
            if rest: pending[0] = (kind, rest, True); break
            pending.pop(0)
        return row
    if lead is not None:
        draw_lead_leaf1(L, lead, scale)
    start_col = 12 if lead is not None else 0
    flow = None
    for k in range(start_col, 13):
        col = k; row = 0.0
        s = slots[k] if k < len(slots) else 'F'
        if flow is None:
            flow = s if isinstance(s, int) else 0
        if s is None:
            row = flush(col, row)
            if row == 0:
                report.append((k+1, 'EMPTY', '注短于元刻，纯注槽无内容'))
            continue
        if s == 'F':
            p0 = flow; p1 = None
        else:
            p0 = s
            rest = [slots[j] if j < len(slots) else 'F' for j in range(k+1, 13)]
            p1 = next((x for x in rest if isinstance(x, int)), None)
            if p1 is None and 'F' not in rest:
                p1 = len(seg)
        if p0 >= len(seg):
            row = flush(col, 0.0)          # 大字已尽而仍有溢注→此列顶格续排
            continue
        L.cells.append((col, 0, big, seg[p0], 'ink', gi0+p0, 0))   # 锚字顶格
        gp = p0 + 1; row = 1.0
        # 首字之注（注随其字——锚在槽首大字下的注，如叶2「天」下王冰注）先于溢注排
        for kind, ntext in seg_notes.get(p0, []):
            chars = [c for c in ntext if c.strip()]
            if not chars: continue
            cap_rows = ROWS - (p1 - p0 - 1) if p1 is not None else ROWS
            h = ((len(chars)+1)//2)*nh
            if row + h <= cap_rows:
                row += lane(col, row, kind, chars)
            else:
                pending.append((kind, chars, False))
        # 溢注接排于锚字后；但须给本槽大字留足行（p1-p0 行），否则溢注续到纯注槽
        until = ROWS if p1 is None else max(1, 1 + ROWS - (p1 - p0))
        row = flush(col, row, until)
        while gp < len(seg) and (p1 is None or gp < p1) and row < ROWS:
            L.cells.append((col, row, big, seg[gp], 'ink', gi0+gp, 0))
            row += 1.0
            for kind, ntext in seg_notes.get(gp, []):
                chars = [c for c in ntext if c.strip()]
                if not chars: continue
                cap_rows = ROWS if p1 is None else ROWS - (p1 - gp - 1)  # 本槽大字到达锚前仍需的行
                h = ((len(chars)+1)//2)*nh
                if row + h <= cap_rows:
                    row += lane(col, row, kind, chars)
                else:
                    pending.append((kind, chars, False))            # 整条溢出续下列
            gp += 1
        if p1 is not None and gp < p1:
            report.append((k+1, 'ANCHOR_BREAK', f'槽满溢出大字{p1-gp}，后续锚弃'))
            for j in range(k+1, len(slots)):
                if isinstance(slots[j], int): slots[j] = 'F'
        flow = gp
    return L

if __name__ == '__main__':
    main()

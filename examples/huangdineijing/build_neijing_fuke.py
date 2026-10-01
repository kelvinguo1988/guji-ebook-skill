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
                kind = 'inknote' if k == 'zhu' else 'note'
                notes.append((tail, [(kind, t)]))
    body_stream = ''.join(body)
    main_s = t2s(body_stream)
    if len(main_s) != len(body_stream):
        main_s = body_stream
    marks = align_marks(main_s, punct_stream)

    # 元刻 8 叶边界：锚点（逐叶目验）+ 缺锚插值
    # 元刻 8 叶末句锚（逐叶目验，公文书馆藏元刻卷一）——切点=每叶末字之后
    # 元刻叶界（逐叶首列实察）——切点=各叶首句之前
    END_CUTS = [
        body_stream.find('成而登天') + 2,          # 叶1止「成而登」；叶2首=「天」
        body_stream.find('度百嵗乃去') + 5,        # 叶2止；叶3起=度百嵗段注末
        body_stream.find('虚无真氣從之'),                  # 叶3止；叶4起=恬惔段注/经文
        body_stream.find('岐伯曰女子七嵗'),        # 叶4止；叶5起=岐伯曰女子七歲
        body_stream.find('形壞而無子也'),          # 叶5止；叶6起=形壞而無子也
        body_stream.find('乃能冩') + 3,            # 叶6止；叶7起=真人段中
        body_stream.find('此其道生') + 4,          # 叶7止；叶8起=圣人段注
        len(body_stream)]
    cuts = [0] + END_CUTS
    assert all(cuts[i] < cuts[i+1] for i in range(len(cuts)-1)), cuts
    print('叶切分点:', cuts)
    notes_at = {}
    for anchor, ntexts in notes:
        pos = body_stream.find(anchor)
        if pos < 0: continue
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)
    cuts.append(len(body_stream))
    assert all(cuts[i] < cuts[i+1] for i in range(len(cuts)-1)), cuts
    print('叶切分点:', cuts)
    notes_at = {}
    for anchor, ntexts in notes:
        pos = body_stream.find(anchor)
        if pos < 0: continue
        notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)

    # 分叶排版（每叶独立，注随文、字号自适应）
    all_marks = marks
    leaves = []
    gi0 = 0
    for li in range(len(cuts) - 1):
        lo, hi = cuts[li], cuts[li+1]
        seg = body_stream[lo:hi]
        seg_notes = {}
        for pos, v in notes_at.items():
            if lo <= pos < hi:
                seg_notes[pos - lo] = v
        scale = 1.0
        for _ in range(6):
            lf = typeset_leaf_suwen(seg, seg_notes, pian_title if li == 0 else None, scale, gi0, marks)
            if len(lf) == 1:
                break
            scale *= 0.93
        for lf2 in lf:
            for c in lf2.cells:
                if isinstance(c[5], int) and c[5] in marks:
                    all_marks.add(c[5])
        for lf2 in lf:
            for c in lf2.cells:
                if isinstance(c[5], int):
                    pass
        leaves.extend(lf)
        gi0 += len(seg)
        print(f'  叶{li+1}: scale={round(scale,3)}', flush=True)

    # 渲染：封面 + 逐叶 pair page（左元刻原叶 / 右复刻叶）
    doc = fitz.open()
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
        cap = f'原書葉　卷一　第{k}叶'
        render_pair_page(doc, lf, k, all_marks, jpg, cap)
        print(f'  对页{k}: 左=元刻半叶{k} 右=复刻叶{k} 首={"".join(bigs[:3])}', flush=True)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = os.path.join(ROOT, '復刻-素問·上古天真論篇第一.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 封面 1 + {len(leaves)} 对页, 正文 {len(body_stream)} 字, 句读圈 {len(marks)}')

def typeset_leaf_suwen(seg, seg_notes, lead, scale, gi0, marks):
    """单叶排版（素问）：卷端列（叶 1）+ 经文大字 + 王冰注墨双行/新校正朱双行随文夹注。
    注小行高 0.52×大字行。返回 [Leaf]。"""
    big = BIG*scale
    note = NOTE*scale
    note_h = NOTE_H
    leaves = [Leaf()]
    L = leaves[0]
    col, row = 0, 0
    gi = gi0
    if lead:
        for r, ch in enumerate('新刊補註釋文黃帝內經素問卷之一'):
            L.cells.append((0, r*1.4375, DATI*scale, ch, 'ink', None, 0))
        for r, ch in enumerate('啓玄子次註林億孫奇高保衡等奉勅校正孫兆重改誤'):
            L.cells.append((1, r, BJ*scale, ch, 'ink', None, 0))
        L.cells.append((2, 0, PIANTI*scale*0.8, '○', 'ink', None, 0))
        for r, ch in enumerate(lead):
            L.cells.append((2, 1+r*1.5, PIANTI*scale, ch, 'ink', None, 0))
        col, row = 2, int(2 + len(lead)*1.5)

    def new_col():
        nonlocal col, row
        col += 1
        row = 0
        if col >= LEAF_COL:
            leaves.append(Leaf()); col = 0

    for ch in seg:
        if row >= ROWS:
            new_col()
        L2 = leaves[-1]
        L2.cells.append((col, row, big, ch, 'ink', gi, 0))
        gi += 1
        row += 1
        nlist = seg_notes.get(gi - 1)
        if not nlist:
            continue
        for kind, ntext in nlist:
            # 注随文夹注：嵌当前列剩余行，双行平衡，注毕接排
            chars = [c for c in ntext if c.strip()]
            n2 = len(chars)
            if n2 == 0: continue
            nr = (n2 + 1) // 2
            span = nr * note_h
            if ROWS - row >= span:
                # 当前列放得下
                for k, c2 in enumerate(chars):
                    lane = 1 if k < nr else 2
                    rr = row + (k if k < nr else k - nr) * note_h
                    leaves[-1].cells.append((col, rr, note, c2, kind, None, lane))
                row += span
            else:
                # 拆两段：当前列填满，剩余续下列
                room_rows = ROWS - row
                take_first = int(room_rows / note_h) * 2
                if take_first <= 0:
                    new_col()
                seg_a, seg_b = chars[:take_first], chars[take_first:]
                tr_a = (len(seg_a) + 1) // 2
                for k, c2 in enumerate(seg_a):
                    lane = 1 if k < tr_a else 2
                    rr = row + (k if k < tr_a else k - tr_a) * note_h
                    leaves[-1].cells.append((col, rr, note, c2, kind, None, lane))
                row = ROWS
                new_col()
                tr_b = (len(seg_b) + 1) // 2
                for k, c2 in enumerate(seg_b):
                    lane = 1 if k < tr_b else 2
                    rr = row + (k if k < tr_b else k - tr_b) * note_h
                    leaves[-1].cells.append((col, rr, note, c2, kind, None, lane))
                row = tr_b * note_h
        # 注毕经文接排（row 已在注末）

    return leaves

if __name__ == '__main__':
    main()

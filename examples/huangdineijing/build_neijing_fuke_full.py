#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》B 版复刻·全書（81 卷章流式，元刻行款 13 列×23 字）
· 全书为纯复刻双半叶对页（左叶+右叶），逐叶翻页——第一章的"左原叶右复刻"逐叶对应需
  元刻全Leaf实察锚定，全书不可得，故全书关闭原叶对照（SKILL §0.5.17 无扫描分支）。
· 卷端大题/篇题入流：卷首新叶 col0 大题，篇题必起新列（○+篇名+篇第N），题下注双行朱。
· 注=随文夹注朱双行（连续注合并/新校正切块，同第一章定稿）；句读=殆知阁标点流对齐朱圈。
· 导出 fuke_text_map_full.json 供全书 EPUB 单一来源。
用法：python3 build_neijing_fuke_full.py"""
import re, os, json, sys
import fitz
from opencc import OpenCC

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import build_neijing_fuke as eng
from build_neijing_fuke import (px, Leaf, COLORMAP, BIG, NOTE, NOTE_H, ROWS, LEAF_COL,
                                DATI, PIANTI, BJ, INK, RED, CN_NUM,
                                CV_W, CV_H, FR_X0, FR_X1, FR_Y0, FR_Y1, LCW, GUT_CX,
                                HALF_W, COL_W, ROW_H, page_chrome, draw_halfleaf,
                                put_char, FONT, KAI)

eng.DZ_PUNCT_FILE = os.path.join(ROOT, 'work', 'suwen_daizhige.txt')
S2T = OpenCC('s2t').convert
s2t_file = eng  # noqa

DIG = '〇一二三四五六七八九'
def cn(n):
    if n < 10: return DIG[n]
    if n < 20: return '十' + (DIG[n % 10] if n % 10 else '')
    s = DIG[n // 10] + '十'
    if n % 10: s += DIG[n % 10]
    return s
def cn_full(n):
    """书口叶次：第二百五十三（勿用廿/卅，qiji 缺此二字概率高）"""
    if n < 100: return cn(n)
    out = DIG[n // 100] + '百'
    r = n % 100
    if r:
        if r < 10: out += '零' + cn(r)
        else: out += cn(r)
    return out

# 元刻总目叶著录（A 版通校结论，SKILL §3 可核实）：十二卷章次区间
JUAN_RANGES = [(1, 7), (8, 16), (17, 20), (21, 30), (31, 38), (39, 45),
               (46, 55), (56, 61), (62, 67), (68, 70), (71, 74), (75, 81)]
def juan_of(num):
    for j, (a, b) in enumerate(JUAN_RANGES, 1):
        if a <= num <= b:
            return j
    return 1

def load_punct_index_best():
    """殆知阁 dump 有重复副本（后副本为无标点旧录）：按篇收全部段流，取句读最多者"""
    txt = open(eng.DZ_PUNCT_FILE, encoding='utf-8').read().replace('\ufeff', '')
    paras = [re.sub(r'^[\s\u3000]+', '', x) for x in txt.split('\n')]
    CN = '一二三四五六七八九十'
    def c2n(cn):
        dd = {c: i + 1 for i, c in enumerate(CN)}
        if cn in dd: return dd[cn]
        if cn.startswith('十'): return 10 + (dd.get(cn[1:], 0) if len(cn) > 1 else 0)
        if '十' in cn:
            a, b2 = cn.split('十', 1)
            return dd.get(a, 0)*10 + (dd.get(b2, 0) if b2 else 0)
        return 0
    segs = {}                       # num -> [stream, ...]
    cur, num = None, None
    for pp in paras:
        m = re.match(r'^([\u4e00-\u9fff（）]{2,14}篇第[一二三四五六七八九十百零]+)$', pp)
        if m:
            num = c2n(re.search(r'第([一二三四五六七八九十百零]+)', m.group(1)).group(1))
            segs.setdefault(num, []).append('')
            cur = num
            continue
        if cur is not None and num is not None and not pp.startswith('卷第'):
            segs[cur][-1] += pp
    out = {}
    for nn, lst in segs.items():
        best = ('', set())
        for tx in lst:
            chs, mks = [], set()
            for c in tx:
                if '\u4e00' <= c <= '\u9fff':
                    chs.append(c)
                elif c in '。？！；':
                    mks.add(len(chs))
            if len(mks) > len(best[1]):
                best = (''.join(chs), mks)
        out[nn] = best
    return out

def load_book():
    """book_data.json 81 章 → 全局章流列表 [{num, juan, title, body, notes_at, marks}]"""
    BOOK = json.load(open(os.path.join(ROOT, 'book_data.json'), encoding='utf-8'))
    punct = load_punct_index_best()
    chapters = []
    t2s = OpenCC('t2s').convert
    for num in range(1, 82):
        e = BOOK[str(num)]
        title = S2T(e['title'].strip())
        if '篇第' not in title:
            title += '篇第' + cn(num)
        body, notes, tail = [], [], ''
        for pp in e['paras']:
            for k, t in pp:
                t = t.strip()
                if not t:
                    continue
                if k == 'p':
                    clean = re.sub(r'[，。：；！？、「」『』（）〔〕\s]', '', t)
                    body.append(clean)
                    tail = clean[-12:]
                elif k in ('zhu', 'xiao'):
                    kind = 'note'
                    if k == 'zhu' and notes and notes[-1][0] == tail and notes[-1][2] == 'zhu':
                        lt = notes[-1][1][-1][1]
                        notes[-1][1][-1] = (kind, lt + t)
                    else:
                        notes.append((tail, [(kind, t)], k))
        notes = [(tl, [(kind, part)
                       for kind, tx in nt
                       for part in re.split(r'\s+(?=新校)', tx) if part.strip()], src)
                 for tl, nt, src in notes]
        bs = ''.join(body)
        notes_at = {}
        for anchor, ntexts, _src in notes:
            pos = bs.find(anchor) if anchor else -1
            if not anchor:
                notes_at.setdefault(-1, []).extend(ntexts)
            elif pos >= 0:
                notes_at.setdefault(pos + len(anchor) - 1, []).extend(ntexts)
        main_s = t2s(bs)
        pstream, pmarks = punct.get(num, ('', set()))
        marks = eng.align_marks(main_s, pstream, pmarks)
        chapters.append({'num': num, 'juan': juan_of(num), 'title': title,
                         'body': bs, 'notes_at': notes_at, 'marks': marks})
    return chapters

def typeset(chapters, lead1):
    """全书流式排版：返回 Leaf 列表 + 每章起止叶 + 注字审计。
    规则：卷首=新叶（col0 大题）；篇题=新列顶（○+题）；注放不下整条入 pending，
    列顶先 flush 再排大字/题；题下注（pos=-1）随题列后排双小行。"""
    leaves = []
    pending = []                      # [(kind, chars, started)]
    state = {'lf': None, 'col': 0, 'row': 0.0}
    bounds = {}

    def new_leaf():
        state['lf'] = Leaf(); leaves.append(state['lf'])
        state['col'] = 0; state['row'] = 0.0
    def next_col():
        state['col'] += 1; state['row'] = 0.0
        if state['col'] >= LEAF_COL:
            new_leaf()
    def col_head():
        while state['row'] > 0:
            next_col()
            flush_pending()
    def lane(col, row, kind, chars):
        n = (len(chars) + 1) // 2
        for i, ch in enumerate(chars):
            ln = 1 if i < n else 2
            state['lf'].cells.append((col, row + (i if i < n else i - n) * NOTE_H,
                                      NOTE, ch, kind, None, ln))
        return n * NOTE_H
    def flush_pending():
        while pending and state['row'] < ROWS:
            kind, chars, _ = pending[0]
            cap = int((ROWS - state['row']) / NOTE_H) * 2
            if cap < 2:
                break
            take, rest = chars[:cap], chars[cap:]
            state['row'] += lane(state['col'], state['row'], kind, take)
            if rest:
                pending[0] = (kind, rest, True); break
            pending.pop(0)
    def note_or_pend(kind, text):
        chars = [c for c in text if c.strip()]
        if not chars:
            return
        h = ((len(chars) + 1) // 2) * NOTE_H
        if state['row'] + h <= ROWS:
            state['row'] += lane(state['col'], state['row'], kind, chars)
        else:
            pending.append((kind, chars, False))

    new_leaf()
    if lead1 is not None:
        eng.draw_lead_leaf1(state['lf'], lead1, 1.0)
        state['col'] = 12; state['row'] = 0.0
    for chp in chapters:
        bounds[chp['num']] = len(leaves) + 1
        while pending:                      # 上一章溢注必须先消化尽（题必顶格）
            next_col(); flush_pending()
        if chp['num'] > 1 or lead1 is None:
            if chp['_juan_start']:
                new_leaf()
                for r, chx in enumerate('新刊補註釋文黃帝內經素問卷之' + cn(chp['juan'])):
                    state['lf'].cells.append((0, r * 1.15, DATI, chx, 'ink', None, 0))
                state['col'] = 1; state['row'] = 0.0
            else:
                col_head(); flush_pending(); col_head()
            state['lf'].cells.append((state['col'], 0, PIANTI, '', 'red', 'inkcircle', 0))
            tchars = chp['title']
            for r, chx in enumerate(tchars):
                state['lf'].cells.append((state['col'], 1 + r, PIANTI, chx, 'ink', None, 0))
            state['row'] = len(tchars) + 1
            for kind, tx in chp['notes_at'].get(-1, []):
                note_or_pend(kind, tx)
        bs = chp['body']
        for i, chx in enumerate(bs):
            if state['row'] >= ROWS:
                next_col(); flush_pending()
            if state['row'] >= ROWS:        # flush 又占满（极端）→ 再换列
                next_col()
            state['lf'].cells.append((state['col'], state['row'], BIG, chx, 'ink',
                                      chp['_start'] + i, 0))
            state['row'] += 1.0
            for kind, tx in chp['notes_at'].get(i, []):
                note_or_pend(kind, tx)
    while pending:
        next_col(); flush_pending()
    return leaves, bounds

def main():
    chapters = load_book()
    st = 0
    for chp in chapters:
        chp['_start'] = st
        chp['_juan_start'] = (chp['num'] == 1 or
                              chp['juan'] != chapters[chp['num'] - 2]['juan'])
        st += len(chp['body'])
    lead1 = None
    nf = os.path.join(ROOT, 'yuan_leaf1_notes.json')
    if os.path.exists(nf):
        j = json.load(open(nf, encoding='utf-8'))
        lead1 = {'pian': chapters[0]['title'].replace('篇第一', '') + '篇第一',
                 'pre_notes': j.get('merged', ''), 'title_note': j.get('col12', '')}
    leaves, bounds = typeset(chapters, lead1)

    # ---- 审计 ----
    exp_notes = sum(len(re.sub(r'\s', '', t)) for chp in chapters
                    for pos, lst in chp['notes_at'].items()
                    if not (chp['num'] == 1 and pos == -1) for kind, t in lst)
    got_notes = sum(1 for i, lf in enumerate(leaves) for c in lf.cells if c[6]
                    and not (i == 0 and lead1 is not None))   # 卷端叶序注/题下注=目验转录，另计
    got_body = sum(1 for lf in leaves for c in lf.cells if c[2] == BIG)
    tot_body = sum(len(chp['body']) for chp in chapters)
    oob = [(i, c) for i, lf in enumerate(leaves) for c in lf.cells
           if c[1] >= ROWS or c[0] >= LEAF_COL]
    tot_marks = sum(len(chp['marks']) for chp in chapters)
    lead_lane = sum(1 for c in leaves[0].cells if c[6]) if lead1 is not None else 0
    print(f'全书审计: 大字 {got_body}/{tot_body} | 注字 {got_notes}/{exp_notes} | '
          f'卷端目验注列 {lead_lane} | 句读圈 {tot_marks} | 越界 {len(oob)} | '
          f'叶数 {len(leaves)} = {(len(leaves)+1)//2} 对页')
    assert got_body == tot_body, '大字流失'
    assert abs(got_notes - exp_notes) <= 2, f'注字不配 {got_notes} vs {exp_notes}'
    assert not oob, oob[:3]

    # ---- 文本映射导出（全书 EPUB 单一来源） ----
    tmap = {'chapters': [], 'lead': lead1}
    for chp in chapters:
        tn = chp['notes_at'].get(-1, [])
        tnote = ''.join(t for _, t in tn)
        if chp['num'] == 1 and lead1 is not None:
            tnote = lead1['title_note']          # 第一章题下注=元刻卷端目验全文（录文仅存尾部残段）
        body_notes = [[p, v] for p, v in sorted(chp['notes_at'].items()) if p >= 0]
        tmap['chapters'].append({'num': chp['num'], 'juan': chp['juan'], 'title': chp['title'],
                                 'text': chp['body'], 'marks': sorted(chp['marks']),
                                 'title_note': tnote,
                                 'notes': body_notes, 'lead_leaf': bounds[chp['num']]})
    with open(os.path.join(ROOT, 'fuke_text_map_full.json'), 'w', encoding='utf-8') as f:
        json.dump(tmap, f, ensure_ascii=False)

    # ---- 渲染：封面 + 纯复刻双半叶对页 ----
    if os.environ.get('FUKE_NO_RENDER'):
        print('FUKE_NO_RENDER：跳过 PDF 渲染（仅导出文本映射）')
        return
    doc = fitz.open()
    cp = page_chrome(doc)
    iw, ih = 900, int(900 * 2034 / 1172)
    ix = ((GUT_CX + LCW / 2) + FR_X1) / 2 - iw / 2
    iy = (FR_Y0 + FR_Y1) / 2 - ih / 2
    cp.insert_image(fitz.Rect(px(ix), px(iy), px(ix + iw), px(iy + ih)),
                    filename=os.path.join(ROOT, 'assets', 'yuan_cover.jpg'))
    cp.draw_rect(fitz.Rect(px(ix), px(iy), px(ix + iw), px(iy + ih)), color=INK, width=px(2))
    for c in range(1, LEAF_COL):
        x = FR_X0 + COL_W * c
        cp.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)), color=INK, width=px(1))

    gmarks = set()
    for chp in chapters:
        gmarks.update(chp['_start'] + m for m in chp['marks'])
    nj = (len(leaves) + 1) // 2
    for j in range(nj):
        lr = leaves[2 * j]
        ll = leaves[2 * j + 1] if 2 * j + 1 < len(leaves) else None
        page = page_chrome(doc)
        for half, lf in ((FR_X1, lr), (FR_X0 + HALF_W, ll)):
            for c in range(1, LEAF_COL):
                x = half - COL_W * c
                page.draw_line(fitz.Point(px(x), px(FR_Y0)), fitz.Point(px(x), px(FR_Y1)),
                               color=INK, width=px(1))
            if lf:
                draw_halfleaf(page, lf, half, gmarks)
        f1 = 2 * j + 1
        ys = px(1420)
        for chx in cn_full(f1):             # 书口叶次=右叶奇数号（第一章样版同款，单串竖排）
            put_char(page, px(GUT_CX), ys, chx, 30 * eng.PXP, INK)
            ys += px(34)
        print(f'  对页{j+1}/{nj}', end='\r', flush=True)
    print()
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = os.path.join(ROOT, '復刻-素問全書.pdf')
    doc.save(out, garbage=4, deflate=True)
    print(f'{out}: 封面1 + {nj} 对页, {len(leaves)} 叶, 大字 {tot_body}, 句读圈 {len(gmarks)}')

if __name__ == '__main__':
    main()

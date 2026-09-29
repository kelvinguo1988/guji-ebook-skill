#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全书叶-录文对齐器：读 /tmp/zwtranscripts/*.txt（标签: 首列转录），
以首列为锚点在维基录文流上顺序滑窗匹配，产出 zw_leaves.json。"""
import json, re, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SECS = json.load(open(os.path.join(ROOT, 'zw_full_data.json'), encoding='utf-8'))

# 安全异体等价类（仅真异体，勿放易混字）
for grp in ['亷廉', '眀明', '脩修', '峯峰', '羣群', '眞真', '蔵藏', '內内', '冊册',
            '尙尚', '畒', '並并', '槩概', '祿禄', '數数', '無无', '來来', '東西',
            '者', '爲為']:
    for c in grp[1:]:
        globals().setdefault('_VAR', {})
        globals()['_VAR'][c] = grp[0]
VAR = globals()['_VAR']

def norm(s): return ''.join(VAR.get(c, c) for c in s)

PUNCT = set('，。：；︰！？、（）《》「」『』〔〕…—～·；,.!?():\u3000 \n')
stream_chars, stream_marks = [], []
for si, sec in enumerate(SECS):
    for para in sec['paras']:
        for ch in para:
            if ch in PUNCT or not ('\u4e00' <= ch <= '\u9fff'):
                if ch in '。？！；，、' and stream_chars:
                    stream_marks[len(stream_chars)-1] = True
                continue
            stream_chars.append(ch)
            stream_marks.append(False)
STREAM = ''.join(stream_chars)
NSTREAM = norm(STREAM)
print('stream len', len(STREAM))

def leaf_order():
    names = []
    for tag, n in (('v1', 129), ('v2', 137)):
        for i in range(1, n+1):
            names += [f'{tag}_{i:03d}R', f'{tag}_{i:03d}L']
    return names

TR = {}
for fn in sorted(os.listdir('/tmp/zwtranscripts')):
    for line in open(f'/tmp/zwtranscripts/{fn}', encoding='utf-8'):
        m = re.match(r'^\s*(v[12]_\d{3}[LR])\s*[:：]\s*(.*)$', line)
        if m:
            txt = re.sub(r'[^一-鿿]', '', m.group(2))
            if txt: TR.setdefault(m.group(1), txt)
print('transcripts', len(TR))

def win_score(a, p):
    w = NSTREAM[p:p+len(a)]
    return sum(1 for x, y in zip(a, w) if x == y)/len(a)

def match_anchor(tr, lo, hi):
    """尝试锚点子串（跳过卷端大题/署名等前缀），返回 (pos, score, used_offset, consumed)
    consumed：锚点在流中实际吃掉的字数（转录串可能覆盖 1-3 列，向后贪心延伸，容错 2/10）"""
    best = (None, 0.0, 0)
    for off in (0, 10, 20, 30, 40, 50, 60):
        a = norm(tr[off:off+20])
        L = len(a)
        if L < 8: continue
        hi2 = min(hi, len(NSTREAM)-L)
        for q in range(max(0, lo), hi2+1):
            s = win_score(a, q)
            if s > best[1]: best = (q, s, off)
            if s >= 0.95: break
        if best[0] is not None and best[1] >= 0.90 and best[2] == off:
            break
    if best[0] is None: return best + (0,)
    # 延伸 consumed：从锚窗尾继续对齐转录余文
    q, s, off = best
    consumed = 20
    tail = norm(tr[off+20:])
    bad = 0; k = 0
    while k < len(tail) and q + 20 + k < len(NSTREAM):
        if tail[k] == NSTREAM[q+20+k]:
            bad = 0
        else:
            bad += 1
            if bad > 2: break
        k += 1; consumed += 1
    return (q, s, off, consumed)

leaves = []
p = 0
gap_run = 0
TITLE_RE = re.compile(r'新鋟希夷|卷之[一二三四五六七八九]|目録|註解|活套')
for name in leaf_order():
    img = f'full/{name}.jpg'
    tr = TR.get(name, '')
    window = 600 + 240*gap_run
    pos, score, off, consumed = match_anchor(tr, p, p+window) if tr else (None, 0, 0, 0)
    # 连续失配后（进入图/命例等无录文段），锚点须高分才可重启，防命例引赋句假匹配
    thr = 0.85 if gap_run >= 2 else 0.60
    kind = 'other'
    if pos is not None and score >= thr and len(tr) >= 30:
        kind = 'text'
    elif TITLE_RE.search(tr[:30]) or (tr and len(tr) <= 24):
        kind = 'title'
    rec = {'name': name, 'img': img, 'anchor': tr[:60], 'anchor_off': off,
           'kind': kind, 'start': pos, 'score': round(score, 2)}
    leaves.append(rec)
    if kind == 'text':
        p = pos + consumed
        gap_run = 0
    else:
        gap_run += 1

CAP = LEAF_COL * ROWS if False else 230
# 段界：hits 相邻=start..next start；超限且有中间叶 → 按比例+锚点校验拆分回收
def anchor_in(tr, lo, hi):
    """转录叶锚点在 [lo,hi) 内最优位置与分数（20字窗，off 多试）"""
    bq, bs = None, 0.0
    for off in (0, 10, 20, 30, 40, 50):
        a = norm(tr[off:off+20])
        if len(a) < 8: continue
        for q in range(lo, max(lo, hi-len(a))):
            s = win_score(a, q)
            if s > bs: bq, bs = q, s
    return bq, bs

hits = [i for i, l in enumerate(leaves) if l['kind'] == 'text']
out = []
for j, i in enumerate(hits):
    nxt = leaves[hits[j+1]]['start'] if j+1 < len(hits) else len(STREAM)
    span_leaves = [leaves[k] for k in range(i, hits[j+1] if j+1 < len(hits) else i+1)]
    gap = nxt - leaves[i]['start']
    mids = span_leaves[1:]
    if gap > CAP and mids:
        # 中间叶锚点定位（须在合理容量内）
        cands = []
        lo = leaves[i]['start'] + 20
        for ml in mids:
            if ml['kind'] not in ('other','title') or not ml['anchor']:
                cands = None; break
            q, s = anchor_in(ml['anchor'], lo, nxt)
            if q is None or s < 0.55 or q - lo > CAP or q >= nxt:
                cands = None; break
            cands.append(q); lo = q + 1
        if cands and nxt - cands[-1] <= CAP:
            bounds = [leaves[i]['start']] + cands + [nxt]
            ok = all(bounds[k+1] - bounds[k] <= CAP for k in range(len(bounds)-1))
            if ok:
                for k in range(len(bounds)-1):
                    lf = leaves[i+k]
                    lf['start'], lf['end'] = bounds[k], bounds[k+1]
                    lf['chars'] = bounds[k+1] - bounds[k]
                    lf['marks'] = [t-lf['start'] for t in range(lf['start'], lf['end']) if stream_marks[t]]
                    lf['kind'] = 'text'; lf['split'] = True
                out.append(j)
                continue
    leaves[i]['end'] = nxt
    leaves[i]['chars'] = gap
    s, e = leaves[i]['start'], nxt
    leaves[i]['marks'] = [k-s for k in range(s, e) if stream_marks[k]]
hits = [i for i, l in enumerate(leaves) if l['kind'] == 'text']
# trim-forward：段略超容量（多为异体/小漏字致锚点偏早）→ 把下一命中叶锚点后移重匹配
for j in range(len(hits)-1):
    i, k = hits[j], hits[j+1]
    lk = leaves[k]
    if leaves[i]['end'] - leaves[i]['start'] > 230 and lk['score'] >= 0.85:
        excess = (leaves[i]['end'] - leaves[i]['start']) - 230
        a = norm(lk['anchor'][lk.get('anchor_off', 0):][:20])
        best = None
        for q in range(lk['start']+1, min(lk['start']+excess+25, leaves[i]['end']-40)):
            s = win_score(a, q)
            if s >= 0.9 and (best is None or s > best[1]): best = (q, s)
        if best:
            lk['start'] = best[0]
            leaves[i]['end'] = best[0]
            leaves[i]['chars'] = best[0] - leaves[i]['start']
            leaves[i]['marks'] = [t-leaves[i]['start'] for t in range(leaves[i]['start'], best[0]) if stream_marks[t]]
for j, i in enumerate(hits):
    if 'end' not in leaves[i]:   # 拆分段插入后其后的 hits 需补 end
        nxt = leaves[hits[j+1]]['start'] if j+1 < len(hits) else len(STREAM)
        leaves[i]['end'] = nxt; leaves[i]['chars'] = nxt - leaves[i]['start']
        s, e = leaves[i]['start'], nxt
        leaves[i]['marks'] = [k-s for k in range(s, e) if stream_marks[k]]
covered = sum(l['end']-l['start'] for l in leaves if l['kind']=='text')
print(f'matched {len(hits)} leaves; covered {covered}/{len(STREAM)}')
over = [(l['name'], l['end']-l['start']) for l in leaves if l['kind']=='text' and l['end']-l['start'] > 230]
print('segments >230:', len(over), over[:12])
small = [(l['name'], l['end']-l['start']) for l in leaves if l['kind']=='text' and l['end']-l['start'] < 30]
print('tiny segments:', small[:12])
json.dump({'stream': STREAM, 'leaves': leaves}, open('/tmp/zwalign_out.json', 'w'), ensure_ascii=False, indent=1)
print('wrote /tmp/zwalign_out.json')

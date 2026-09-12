#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《黃帝內經素問》全书数据装配：维基文库四部叢刊本（景明翻北宋本，含王冰注+新校正）
→ 分篇解析 → 以殆知阁录文的段落结构为锚重排经文 → 与元刻/殆知阁双源质检 → book_data.json"""
import re, os, json, glob, sys, unicodedata
import html as _html
from opencc import OpenCC
_cc_t2s = OpenCC('t2s')

WS = '/tmp/ws_suwen'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'book_data.json')

VOLS = {  # 元刻十二卷 → 篇次区间（据元刻总目叶 + 卷端叶实察）
    1: (1, 7), 2: (8, 16), 3: (17, 20), 4: (21, 30), 5: (31, 38), 6: (39, 45),
    7: (46, 55), 8: (56, 61), 9: (62, 67), 10: (68, 70), 11: (71, 74), 12: (75, 81),
}
CN_NUM = '一二三四五六七八九十'

def cnum(n):
    if n <= 10: return CN_NUM[n-1]
    if n < 20: return '十' + CN_NUM[n-11]
    if n == 20: return '二十'
    return '二十' + CN_NUM[n-21]

def hanzi(s):
    return ''.join(c for c in s if '\u3400' <= c <= '\u9fff' or '\uf900' <= c <= '\ufaff')

def clean_html(h):
    h = re.sub(r"<style[^>]*>.*?</style>", "", h, flags=re.S)
    h = re.sub(r'<span class="pagenum[^"]*"[^>]*>.*?</span>', '', h, flags=re.S)
    h = re.sub(r'<sup[^>]*>.*?</sup>', '', h, flags=re.S)
    h = re.sub(r'</p>', '\n\n', h)
    h = re.sub(r'<br[^>]*>', '\n', h)
    h = re.sub(r'<[^>]+>', '', h)
    h = _html.unescape(h)
    return h.replace('&#8203;', '').replace('&amp;', '&').replace('\u3000', ' ').strip()

PAT_TITLE = re.compile(r'^([^\n〈〉\s]{2,16})篇第([一二三四五六七八九十]+)$')

def parse_blocks(h):
    """卷文本 → [(篇题, 篇次, 篇块文本)]：逐行识别篇题行，一行双题则拆开"""
    lines = h.split('\n')
    hits = []
    for li, ln in enumerate(lines):
        t = ln.strip()
        if not t or '篇第' not in t:
            continue
        t = t.split('〈', 1)[0].strip()  # 篇题行常直接跟〈注〉，先截去
        if not t or '篇第' not in t:
            continue
        pairs = []
        for tok in re.split(r'[\s　]+', t):
            m = PAT_TITLE.match(tok)
            if m:
                pairs.append((m.group(1), m.group(2)))
        if pairs:
            hits.append((li, pairs))
    blocks = []
    for k, (li, pairs) in enumerate(hits):
        nxt = hits[k+1][0] if k+1 < len(hits) else len(lines)
        chunk = '\n'.join(lines[li+1:nxt])
        for ti_title, ti_n in pairs:
            blocks.append((ti_title, cn2n(ti_n), chunk))
    return blocks

def tokenize(block):
    """篇块 → 有序 segments [(kind, text)]；kind: p/zhu/xiao"""
    segs = []
    pos = 0
    while True:
        a = block.find('〈', pos)
        if a < 0:
            t = block[pos:].strip()
            if t: segs.append(('p', t))
            break
        t = block[pos:a].strip()
        if t: segs.append(('p', t))
        b = block.find('〉', a)
        if b < 0:
            t = block[a+1:].strip()
            if t: segs.append(('xiao', t))
            break
        t = block[a+1:b].strip()
        if '新校正云' in t[:6]:
            # 拆出前面可能混排的王冰注
            i = t.find('新校正云')
            if i > 0: segs.append(('zhu', t[:i].strip()))
            segs.append(('xiao', t[i:].strip()))
        else:
            segs.append(('zhu', t))
        pos = b + 1
    return segs

def load_daizhige():
    s = open('/tmp/suwen_daizhige.txt', encoding='utf-8').read()
    s = s.replace('\ufeff', '')
    paras = [re.sub(r'^[\s\u3000]+', '', x) for x in s.split('\n')]
    paras = [p for p in paras if p]
    # 篇索引：title -> [段...]
    idx = {}
    cur = None
    for p in paras:
        m = re.match(r'^([\u4e00-\u9fff（）]{2,14}篇第[一二三四五六七八九十百零]+)$', p)
        if m:
            cur = m.group(1); idx[cur] = []
            continue
        if cur and not p.startswith('卷第'):
            idx[cur].append(p)
    return idx

def s2t_stubs(s):
    return _cc_t2s.convert(s)

def main():
    dz = load_daizhige()
    dz_keys = {}
    for k in dz:
        n = re.search(r'第([一二三四五六七八九十百零]+)', k)
        if n:
            num = cn2n(n.group(1))
            dz_keys[num] = (k, dz[k])
    book = {}
    log = []
    files = sorted(glob.glob(os.path.join(WS, '卷第*.html')))
    print('卷文件:', len(files))
    for fp in files:
        h = clean_html(open(fp, encoding='utf-8').read())
        for title, n, block in parse_blocks(h):
            if not (1 <= n <= 81):
                continue
            title = norm_text(title)
            segs = tokenize(block)
            # 段落重排：以殆知阁同篇的段落为锚
            anchor_paras = dz_keys.get(n, (None, []))[1]
            anchors = [len(hanzi(x)) for x in anchor_paras]
            paras = reflow(segs, anchors)
            paras = [[(k2, norm_text(t2)) for k2, t2 in pp] for pp in paras]
            book[n] = {'title': title, 'paras': paras}
            # 质检：与殆知阁首段比对
            if anchor_paras and paras and paras[0]:
                dz_first = hanzi(anchor_paras[0])[:10]
                got_first = hanzi(_cc_t2s.convert(''.join(t for k2, t in paras[0] if k2 == 'p')))[:10]
                if dz_first != got_first:
                    log.append((n, title, '首句差', dz_first, got_first))
            else:
                log.append((n, title, '殆知阁无此篇'))
    # 亡篇 72/73 及任何空篇：回退殆知阁源
    for n in range(1, 82):
        e = book.get(n)
        has_text = e and any(len(hanzi(t)) > 20 for pp in e['paras'] for k2, t in pp if k2 == 'p')
        if (not e or not has_text) and n in dz_keys:
            k, paras = dz_keys[n]
            if paras:
                segs = [('p', p) for p in paras]
                book[n] = {'title': re.sub(r'篇第[一二三四五六七八九十百零]+$', '', k), 'paras': [segs]}
                log.append((n, book[n]['title'], '回退殆知阁源'))
    missing = [n for n in range(1, 82) if n not in book]
    tot_ws = sum(len(hanzi(t)) for e in book.values() for pp in e['paras'] for k2, t in pp if k2 == 'p')
    tot_dz = sum(len(hanzi(p)) for v in dz.values() for p in v)
    print('经文总量(四部叢刊):', tot_ws, '| 殆知阁全库:', tot_dz)
    print('篇数:', len(book), 'missing:', missing)
    for l in log[:30]: print('QC:', l)
    json.dump(book, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('book_data.json written,', round(os.path.getsize(OUT)/1024), 'KB')

NORM = [('隂','陰'),('眞','真'),('寳','寶'),('逺','遠'),('形','形'),('痺','痹'),
        ('欬','咳'),('剌','刺'),('𥙷','補'),('歧伯','岐伯'),
        # 增补区异体字 → 通行正字（Noto 全字库不含增补 B/F 区，须归一）
        ('𠉀','候'),('𤣥','玄'),('𦝫','腰'),('𩕄','囟'),('㑹','會'),('𢘆','恆'),
        ('𨵿','關'),('𦛗','膂'),('𡁲','衄'),('𫝊','傳'),('𤸇','癃'),('𤸷','痹'),
        ('𡨚','冤'),('𬃷','棗'),('𧰼','象'),('𭼠','瘧'),('𥆨','䀮'),('𤼵','發'),
        ('𭰖','泥'),('𤍠','熱'),('𡨋','冥'),('𦟘','瞚'),('𭔃','寄'),('𡖉','卵'),
        ('𠻳','嗽'),('𢙣','惡'),('𫞐','權'),('𫎇','蒙'),('𠋫','候'),('𤾁','衄'),
        ('𦫵','升'),('𩃬','陰'),('𥘉','初'),('𦙼','眥'),('𥚹','褊'),('𤓰','瓜'),
        ('𣡸','鬱'),('𢢑','離'),('𠡠','勅'),('𠋣','倚'),('𩨬','骨'),('𬽦','仇'),
        ('𩆍','霢'),('𭣣','收'),('𥬇','笑'),('𪫟','怵'),('𣪣','殷'),('𩔖','類'),
        ('𭥦','昴'),('𠕋','冊'),('𭥍','甚'),('𠸺','吐'),('𤺛','瞤'),('𨼆','隱'),
        ('𦂳','緊'),('𤋲','燻'),('𤎅','熬'),('𧦽','診'),('𨳩','開'),('𩪯','髕'),
        ('𣣔','欲'),('𨳲','閉'),
        ('𨷖','候'),('𢈔','庾'),('𦘕','聤'),('𤵜','□')]

def norm_text(t):
    for a, b in NORM:
        t = t.replace(a, b)
    return t

def reflow(segs, anchors):
    """按殆知阁段落锚点把经文 run 重新分段；注/校正段保持原位。"""
    if not anchors:
        return [segs] if segs else []
    total = sum(len(hanzi(t)) for k, t in segs if k == 'p')
    if total == 0: return [segs] if segs else []
    cuts = []
    acc = 0
    for a in anchors[:-1]:
        acc += a
        cuts.append(acc)
    out, cur = [], []
    hc = 0
    ci = 0
    for kind, t in segs:
        cur.append((kind, t))
        if kind == 'p':
            hc += len(hanzi(t))
            while ci < len(cuts) and hc >= cuts[ci] - 2:
                out.append(cur); cur = []
                ci += 1
                if ci >= len(cuts): break
    if cur: out.append(cur)
    return [p for p in out if p]

def cn2n(cn):
    if not cn: return 0
    digits = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    if cn in digits: return digits[cn]
    if cn.startswith('十'):
        rest = cn[1:]
        return 10 + (digits.get(rest, 0) if rest else 0)
    if '十' in cn:
        a, b = cn.split('十', 1)
        return digits.get(a,0)*10 + (digits.get(b, 0) if b else 0)
    if cn.startswith('二十'): return 20 + digits.get(cn[2:], 0)
    if cn.startswith('三十'): return 30 + digits.get(cn[2:], 0)
    return 0

if __name__ == '__main__':
    main()

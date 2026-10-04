#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""古籍文字数据抓取器——三站适配 + 防反爬通用层（guji-ebook skill 数据源工具）

站点适配（2026-10 实测）：
  luckclub.cn    全站 SSR 静态 HTML，直连可用（原文+白话+注释一并抽取）
  shidianguji.com 识典古籍，字节 argus 风控：匿名请求返回 JS 挑战页；
                 需用户从浏览器复制登录后 cookie（--cookie-file），脚本限速直连 API
  weread.qq.com  微信读书：搜索/目录匿名可用；正文接口需登录 cookie（WEREAD_COOKIE）

防反爬通用层（勿绕过风控，只做礼貌抓取+会话复用）：
  · 真 Chrome UA/头序 + Accept-Language；每 host 随机限速 2-4.5s
  · 指数退避重试（4 次，抖动）；磁盘缓存 cache/（默认 24h，--no-cache 跳过）
  · JS 挑战页自动识别（gfkadpd/argus 特征）→ 解析挑战 cookie 重放一次 → 仍失败即报错并给指引
  · cookie 注入：--cookie-file cookies.txt（Netscape 或「k=v; …」原文均可）

用法示例：
  python3 fetch_classic_text.py luckclub --book /bazi/001/ --out ysyp.json
  python3 fetch_classic_text.py weread --search 老子道德经
  python3 fetch_classic_text.py weread --book-hash f4f3225072615773f4f6c05 --toc
  python3 fetch_classic_text.py weread --book-id 39933811 --chapter-uid 2 --out ch2.json
  python3 fetch_classic_text.py shidianguji --cookie-file sdj.txt --book SBCK106 --toc
"""
import argparse, hashlib, json, os, random, re, sys, time
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
CACHE_TTL = 24 * 3600
UAS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]
_last_hit = {}

# ---------- 通用层 ----------

def _headers(site, extra=None):
    h = {
        'User-Agent': random.choice(UAS),
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.6',
        'Connection': 'keep-alive',
    }
    if site == 'weread':
        h['Referer'] = 'https://weread.qq.com/'
    elif site == 'shidianguji':
        h['Referer'] = 'https://www.shidianguji.com/'
    elif site == 'luckclub':
        h['Referer'] = 'https://luckclub.cn/'
    if extra:
        h.update(extra)
    return h


def _cache_path(site, url):
    key = hashlib.md5((site + '|' + url).encode()).hexdigest()
    return os.path.join(CACHE_DIR, site, key + '.txt')


def polite_get(url, site, *, params=None, timeout=30, retries=4, use_cache=True, session=None):
    """限速 GET：随机间隔 2-4.5s/host、指数退避重试、磁盘缓存。返回 text 或抛 RuntimeError。"""
    import urllib.parse
    host = urllib.parse.urlparse(url).netloc
    base, span = (1.2, 1.6) if site == 'luckclub' else (2.0, 2.5)   # 静态站宽容、风控站保守
    wait = base + random.random() * span - (_last_hit.get(host, 0) and max(0.0, time.time() - _last_hit[host]))
    if wait > 0:
        time.sleep(min(wait, 4.5))
    cp = _cache_path(site, url + (json.dumps(params, sort_keys=True) if params else ''))
    if use_cache and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < CACHE_TTL:
        return open(cp, encoding='utf-8').read()
    s = session or requests
    err = None
    for i in range(retries):
        try:
            r = (s.get if session else requests.get)(url, params=params, headers=_headers(site),
                                                     timeout=timeout)
            _last_hit[host] = time.time()
            if r.status_code == 200:
                if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'ascii'):
                    r.encoding = r.apparent_encoding or 'utf-8'
                txt = r.text
                if _is_js_challenge(txt):
                    txt2 = _challenge_retry(url, site, txt, s, timeout)
                    if txt2 is not None:
                        txt = txt2
                    else:
                        raise RuntimeError(_CHALLENGE_HINT[site])
                os.makedirs(os.path.dirname(cp), exist_ok=True)
                open(cp, 'w', encoding='utf-8').write(txt)
                return txt
            err = RuntimeError(f'HTTP {r.status_code}: {url}')
            if r.status_code in (403, 412, 429):
                time.sleep((2 ** i) * 3 + random.random() * 2)   # 风控/限频：长退避
                continue
        except requests.RequestException as e:
            err = e
            time.sleep((2 ** i) * 2 + random.random())
    raise RuntimeError(f'抓取失败（已重试 {retries} 次）: {url} — {err}')


def _is_js_challenge(txt):
    return bool(re.search(r'gfkadpd|argus|sdk-glue|Just a moment|challenge', txt[:4000], re.I)) \
        and '<html' in txt[:200].lower()


_CHALLENGE_HINT = {
    'shidianguji': '识典古籍返回 JS 风控挑战页。解法：浏览器登录 www.shidianguji.com 后复制 cookie（F12→Network→任一请求→Cookie 头），'
                   '存为 cookies.txt 后 --cookie-file cookies.txt 重试；cookie 过期（约数日）后需重新复制。',
    'weread': '微信读书需要登录态。解法：浏览器登录 weread.qq.com 后复制 cookie 存入环境变量 WEREAD_COOKIE 或 --cookie-file。',
    'luckclub': 'luckclub 不应出现挑战页，请检查网络。',
}


def _challenge_retry(url, site, challenge_txt, session, timeout):
    """简单挑战（服务端直发 cookie 设定脚本，如 gfkadpd=ver,sub）：解析并重放一次。"""
    m = re.search(r'var e="(\d+)",t="(\d+)"', challenge_txt)
    if not m:
        return None
    cookie = f'gfkadpd={m.group(1)},{m.group(2)}'
    r = session.get(url, headers=_headers(site, {'Cookie': cookie}), timeout=timeout)
    return r.text if r.status_code == 200 and not _is_js_challenge(r.text) else None


def load_cookie_session(cookie_str):
    s = requests.Session()
    s.headers.update({'User-Agent': UAS[0]})
    for kv in cookie_str.replace('\n', ';').split(';'):
        if '=' in kv:
            k, v = kv.strip().split('=', 1)
            s.cookies.set(k, v, domain='.shidianguji.com' if 'shidian' in cookie_str else None)
    return s


def strip_html(html, sep='\n'):
    t = re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', '', html, flags=re.S)
    t = re.sub(r'<[^>]+>', sep, t)
    return re.sub(r'[ \t\u3000]+', ' ', t)

# ---------- luckclub 适配器（SSR 直连） ----------

def luckclub_books(category='bazi'):
    h = polite_get(f'https://luckclub.cn/{category}/', 'luckclub')
    out = []
    for m in re.finditer(r'href="/%s/(\d+)/"[^>]*?title="《?([^》"<]{2,40})》?[^"]*"' % category, h):
        out.append({'path': f'/{category}/{m.group(1)}/', 'title': m.group(2).strip()})
    if not out:   # 兜底：无 title 属性时取链接路径
        for p in sorted(set(re.findall(r'href="/%s/(\d+)/"' % category, h))):
            out.append({'path': f'/{category}/{p}/', 'title': ''})
    return out


def luckclub_chapters(book_path):
    h = polite_get('https://luckclub.cn' + book_path, 'luckclub')
    chs = []
    for m in re.finditer(r'href="(%s(\d+)/)"[^>]*?title="([^"]{2,60})"' % re.escape(book_path), h):
        chs.append({'path': m.group(1), 'idx': int(m.group(2)),
                    'title': re.sub(r'^《|》.*$', '', m.group(3)).strip()})
    if not chs:   # 兜底：无 title 属性
        for p in sorted(set(re.findall(r'href="(%s(?:\d+)/)"' % re.escape(book_path), h))):
            chs.append({'path': p, 'idx': int(p.rstrip('/').rsplit('/', 1)[1]), 'title': ''})
    return chs


def _slice_html(h, start_pat, end_pat):
    """取 start_pat 之后至 end_pat 之前的 HTML 片段，剥标签成段（strong 保留为「」小节标记）。"""
    a = re.search(start_pat, h)
    b = re.search(end_pat, h[a.end():] if a else '')
    if not a:
        return ''
    seg = h[a.end(): a.end() + (b.start() if b else len(h))]
    seg = re.sub(r'<strong[^>]*>(.*?)</strong>', r'「\1」', seg, flags=re.S)
    t = re.sub(r'<[^>]+>', '\n', seg)
    t = re.sub(r'[ \t\u3000]+', ' ', t)
    lines = [l.strip() for l in t.split('\n') if len(l.strip()) >= 2]
    return '\n'.join(lines)


def luckclub_chapter(ch_path):
    """章节页（SSR）：原文在 <article id="article-content">，译文/术语注在
    <div id="pane-translation"> 至页脚——按容器精确抽取，不做简繁猜测。"""
    h = polite_get('https://luckclub.cn' + ch_path, 'luckclub')
    title = (re.search(r'<title>([^<]+)</title>', h) or [None, ''])[1]
    title = re.sub(r'\s*\|.*$', '', title).strip()
    yuan = _slice_html(h, r'<article id="article-content"[^>]*>', r'</article>')
    shiyi = _slice_html(h, r'id="pane-translation"[^>]*>', r'border-t border-brand-gray-800')
    return {'title': title, 'path': ch_path, 'yuanwen': yuan, 'shiyi': shiyi}

# ---------- weread 适配器 ----------

WR = 'https://weread.qq.com'

def weread_search(keyword, count=10):
    h = polite_get(WR + '/web/search/global', 'weread',
                   params={'keyword': keyword, 'maxIdx': 0, 'count': count})
    d = json.loads(h)
    out = []
    for b in d.get('books', []):
        bi = b.get('bookInfo', {})
        out.append({'bookId': bi.get('bookId'), 'title': bi.get('title'),
                    'author': bi.get('author'), 'hash': (bi.get('deepLink') or '').split('v=')[-1]})
    return out


def weread_toc(book_hash):
    h = polite_get(WR + f'/web/reader/{book_hash}', 'weread')
    toc = re.findall(r'"chapterUid":(\d+),"chapterIdx":\d+,"title":"([^"]+)"', h)
    if not toc:
        toc = [(u, t) for u, t in re.findall(r'"chapterUid":(\d+)[^}]*?"title":"([^"]+)"', h)]
    seen, out = set(), []
    for u, t in toc:                      # 页面内嵌正文目录与 AI 大纲目录各一份，按 uid 去重保序
        if u not in seen:
            seen.add(u)
            out.append({'uid': int(u), 'title': t})
    return out


def weread_chapter(book_id, chapter_uid, cookie=None):
    if not cookie:
        raise RuntimeError(_CHALLENGE_HINT['weread'])
    s = requests.Session()
    for kv in cookie.replace('\n', ';').split(';'):
        if '=' in kv:
            k, v = kv.strip().split('=', 1)
            s.cookies.set(k, v)
    r = s.post(WR + '/web/book/chapterInfos', json={'bookId': str(book_id),
               'chapterUids': [str(chapter_uid)]}, headers=_headers('weread', {
                   'Content-Type': 'application/json;charset=UTF-8',
                   'Referer': WR + '/web/reader'}), timeout=30)
    d = r.json()
    if d.get('errCode'):
        raise RuntimeError(f'weread 正文接口错误 {d.get("errCode")}: {d.get("errMsg")}（cookie 失效或无权阅读）')
    chap = (d.get('data', {}).get('chapterInfos') or [{}])[0]
    html = chap.get('content', '')
    text = re.sub(r'<[^>]+>', '\n', html)
    return {'title': chap.get('chapterTitle', ''), 'text': re.sub(r'\n{2,}', '\n', text).strip(),
            'pages': chap.get('pages', [])}

# ---------- shidianguji 适配器（cookie 注入） ----------

SDJ = 'https://www.shidianguji.com'

def sdj_search(keyword, session=None):
    h = polite_get(SDJ + '/api/book/search', 'shidianguji', params={'keyword': keyword}, session=session)
    if h.lstrip().startswith('<'):
        raise RuntimeError(_CHALLENGE_HINT['shidianguji'])
    return json.loads(h)


def sdj_toc(book_id, session=None):
    h = polite_get(SDJ + f'/api/book/detail?book_id={book_id}', 'shidianguji', session=session) \
        if False else polite_get(SDJ + f'/api/book/{book_id}/catalog', 'shidianguji', session=session)
    if h.lstrip().startswith('<'):
        raise RuntimeError(_CHALLENGE_HINT['shidianguji'])
    return json.loads(h)


def sdj_chapter(book_id, chapter_id, session=None):
    h = polite_get(SDJ + f'/api/book/{book_id}/chapter/{chapter_id}', 'shidianguji', session=session)
    if h.lstrip().startswith('<'):
        raise RuntimeError(_CHALLENGE_HINT['shidianguji'])
    return json.loads(h)

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('site', choices=['luckclub', 'weread', 'shidianguji'])
    ap.add_argument('--category', default='bazi', help='luckclub 分类路径名')
    ap.add_argument('--book', help='luckclub 书路径（如 /bazi/001/）')
    ap.add_argument('--search', help='weread/shidianguji 关键词搜索')
    ap.add_argument('--book-hash', help='weread 阅读器 hash（取目录）')
    ap.add_argument('--book-id', help='weread/shidianguji 书 ID')
    ap.add_argument('--chapter-uid', help='weread 章节 uid')
    ap.add_argument('--toc', action='store_true', help='只取目录')
    ap.add_argument('--cookie-file', help='cookie 文件（Netscape 或「k=v; …」原文）')
    ap.add_argument('--no-cache', action='store_true')
    ap.add_argument('--limit', type=int, default=0, help='luckclub 全书抓取最多章数（0=全部），采样用')
    ap.add_argument('--out', help='输出 JSON 文件路径')
    a = ap.parse_args()

    try:
        if a.site == 'luckclub':
            if not a.book:
                books = luckclub_books(a.category)
                res = {'site': 'luckclub', 'category': a.category, 'books': books}
            else:
                chs = luckclub_chapters(a.book)
                if a.toc or not a.out:
                    res = {'site': 'luckclub', 'book': a.book, 'chapters': chs}
                else:
                    res = {'site': 'luckclub', 'book': a.book, 'chapters': []}
                    for c in (chs[:a.limit] if a.limit else chs):
                        res['chapters'].append(luckclub_chapter(c['path']))
        elif a.site == 'weread':
            if a.search:
                res = {'site': 'weread', 'results': weread_search(a.search)}
            elif a.book_hash:
                res = {'site': 'weread', 'bookHash': a.book_hash, 'toc': weread_toc(a.book_hash)}
            elif a.book_id and a.chapter_uid:
                cookie = a.cookie_file and open(a.cookie_file, encoding='utf-8').read() or os.environ.get('WEREAD_COOKIE', '')
                res = weread_chapter(a.book_id, a.chapter_uid, cookie)
            else:
                ap.error('weread 需要 --search / --book-hash / --book-id+--chapter-uid 之一')
        else:
            cookie = a.cookie_file and open(a.cookie_file, encoding='utf-8').read() or os.environ.get('SHIDIANGUJI_COOKIE', '')
            if not cookie:
                raise RuntimeError(_CHALLENGE_HINT['shidianguji'])
            s = load_cookie_session(cookie)
            if a.book_id and a.toc:
                res = sdj_toc(a.book_id, s)
            elif a.book_id:
                res = sdj_chapter(a.book_id, a.chapter_uid, s)
            elif a.search:
                res = sdj_search(a.search, s)
            else:
                ap.error('shidianguji 需要 --search / --book-id(+--toc/--chapter-uid)')
    except RuntimeError as e:
        print('✗ ' + str(e), file=sys.stderr)
        sys.exit(2)
    js = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(js)
        print(f'✓ {a.out}（{len(js)} 字节）')
    else:
        print(js[:1500])


if __name__ == '__main__':
    main()

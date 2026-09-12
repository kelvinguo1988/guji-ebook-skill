#!/usr/bin/env python3
"""穷通宝鉴 FXL 版式本：把 PDF 逐页转成 EPUB3 Fixed Layout，视觉与 PDF 一致。
原理：每页两层——① 抹掉文字后的图形层渲染为背景图（卡片/边框/书影/封面全部保留）；
② 文字 span 从 PDF 提取 bbox/origin，绝对定位重建文字层（真实文本，可选中检索）。
颜色字段因 Type3 字体丢失，按渲染像素反采样后吸附到设计色板；字重按角色规则推断。
用法：python3 build_qtb_fxl.py [源.pdf] [输出.epub]
"""
import fitz, os, sys, re, zipfile, io, subprocess, tempfile, statistics

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '穷通宝鉴笺注-全书.pdf')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '穷通宝鉴笺注-全书-版式本.epub')

K = 2.0                       # pt → px 缩放（视口 1048×1474）
W_PT, H_PT = 523.9, 737.0
VW, VH = round(W_PT * K), round(H_PT * K)

PALETTE = [(0x2C,0x28,0x24),(0x4E,0x47,0x38),(0x8A,0x80,0x69),(0x9E,0x2F,0x23),
           (0xF6,0xEF,0xDD),(0xED,0xE3,0xC8),(0xC8,0xB9,0x8D),(0xB7,0x9B,0x5E),
           (0x23,0x2D,0x3F),(0x14,0x1D,0x2B),(0xC9,0xB9,0x8A),(0xDD,0xD3,0xB4),
           (0x00,0x00,0x00),(0xFF,0xFF,0xFF),(0x8B,0x5A,0x2E),(0x5C,0x54,0x4A)]

def snap(rgb):
    best, bd = None, 1e9
    for p in PALETTE:
        d = (rgb[0]-p[0])**2 + (rgb[1]-p[1])**2 + (rgb[2]-p[2])**2
        if d < bd: bd, best = d, p
    return '#%02X%02X%02X' % best

def span_color(samples, pw, n, bbox, kw, kh):
    # 在整页渲染位图上采样 span 区域：与局部底色距离最远的像素簇均值。
    # 注意：samples/width 必须由调用方提升为局部变量——PyMuPDF 的 Pixmap.samples
    # 属性每次访问都会整体拷贝缓冲，逐像素访问会慢 50 倍。
    x0, y0, x1, y1 = [int(v * kw) for v in bbox]
    x0, y0 = max(0, x0-1), max(0, y0-1)
    x1, y1 = min(pw-1, x1+1), min(pw-1, y1+1)
    if x1 - x0 < 2 or y1 - y0 < 2: return '#2C2824'
    def px(x, y):
        o = (y * pw + x) * n
        return samples[o], samples[o+1], samples[o+2]
    border = [px(x, y) for x, y in
              [(x0,y0),(x1,y0),(x0,y1),(x1,y1),(x0,(y0+y1)//2),(x1,(y0+y1)//2)]]
    br = statistics.median(c[0] for c in border)
    bg = (br, statistics.median(c[1] for c in border), statistics.median(c[2] for c in border))
    cands = []
    step = max(1, (x1-x0)//24)
    for y in range(y0, y1+1, max(1,(y1-y0)//12 or 1)):
        for x in range(x0, x1+1, step):
            c = px(x, y)
            dist = (c[0]-bg[0])**2 + (c[1]-bg[1])**2 + (c[2]-bg[2])**2
            if dist > 3600: cands.append((dist, c))
    if not cands: return snap(bg)
    cands.sort(reverse=True)
    top = cands[:max(1, len(cands)//4)]
    r = round(statistics.mean(c[1][0] for c in top))
    g = round(statistics.mean(c[1][1] for c in top))
    b = round(statistics.mean(c[1][2] for c in top))
    return snap((r, g, b))

def is_bold(size, color, text):
    if size >= 21: return True          # 章题/卷题/封面大题
    if 13.0 <= size <= 14.5: return True  # h2.sec
    if 11.0 <= size <= 12.0: return True  # h3.sec
    if color == '#F6EFDD': return True    # 深底标签字
    if size >= 30: return True
    return False

def kai_font(size, text, page_no):
    # 楷体角色：封面大题/副题、今人按语问句
    if page_no == 0 and size >= 13: return True
    if '？' in text and 10.0 <= size <= 11.2: return True
    return False

def main():
    doc = fitz.open(PDF)
    n_pages = doc.page_count
    workdir = tempfile.mkdtemp(prefix='qtb_fxl_')
    bg_dir = os.path.join(workdir, 'bg'); os.makedirs(bg_dir)
    pages, all_chars = [], set()
    print(f'提取 {n_pages} 页 …')
    for i in range(n_pages):
        page = doc[i]
        # 全页渲染（含文字）用于颜色采样
        full = page.get_pixmap(matrix=fitz.Matrix(K, K))
        fsamples, fpw, fn = full.samples, full.width, full.n
        spans_out = []
        dd = page.get_text('dict')
        for b in dd['blocks']:
            if b['type'] != 0: continue
            for l in b['lines']:
                for s in l['spans']:
                    t = s['text']
                    if not t.strip(): continue
                    col = span_color(fsamples, fpw, fn, s['bbox'], K, K)
                    size = round(s['size'] * K, 1)
                    fam = 'kai' if kai_font(s['size'], t, i) else ('sans' if 'Helvetica' in s['font'] else 'song')
                    wt = 700 if is_bold(s['size'], col, t) else 400
                    x0, y0 = s['bbox'][0]*K, s['bbox'][1]*K
                    ox, oy = s['origin'][0]*K, s['origin'][1]*K
                    asc = s.get('ascender', 0.88)
                    top = oy - asc * s['size'] * K
                    spans_out.append(
                        f'<span class="t" style="left:{x0:.1f}px;top:{top:.1f}px;'
                        f'font-size:{size}px;font-weight:{wt};color:{col};'
                        f'font-family:var(--{fam})">{esc(t)}</span>')
                    all_chars.update(t)
        # 图形层：抹掉文字后渲染为背景
        rects = []
        for b in dd['blocks']:
            if b['type'] != 0: continue
            for l in b['lines']:
                for s in l['spans']:
                    rects.append(fitz.Rect(s['bbox']))
        for r in rects: page.add_redact_annot(r)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        pix = page.get_pixmap(matrix=fitz.Matrix(K, K))
        bg_name = f'bg{i:04d}.jpg'
        pix.pil_save(os.path.join(bg_dir, bg_name), format='JPEG', quality=82)
        pages.append((bg_name, spans_out))
        if (i+1) % 100 == 0: print(f'  {i+1}/{n_pages}')
    print('字体子集化 …')
    fonts = subset_fonts(all_chars, workdir)
    write_epub(pages, fonts, bg_dir, n_pages)
    print('DONE', OUT, round(os.path.getsize(OUT)/1048576, 1), 'MB')

def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def subset_fonts(chars, workdir):
    from fontTools import subset
    text = ''.join(sorted(chars))
    tf = os.path.join(workdir, 'chars.txt')
    open(tf, 'w', encoding='utf-8').write(text)
    out = {}
    jobs = [('song', 400, os.path.join(ROOT, 'fonts/NotoSerifCJKtc-Regular.otf'), 'nsr'),
            ('song', 700, os.path.join(ROOT, 'fonts/NotoSerifCJKtc-Bold.otf'), 'nsb'),
            ('kai', 400, os.path.join(ROOT, 'fonts/LXGWWenKai-Regular.ttf'), 'lwr'),
            ('kai', 700, os.path.join(ROOT, 'fonts/LXGWWenKai-Medium.ttf'), 'lwm')]
    for fam, wt, src, key in jobs:
        dst = os.path.join(workdir, f'f_{key}.woff2')
        args = [str(src), f'--text-file={tf}', f'--output-file={dst}',
                '--flavor=woff2', '--no-hinting', '--desubroutinize']
        subset.main(args)
        out[key] = (fam, wt, os.path.basename(dst), os.path.getsize(dst))
        print(f'  {key}: {out[key][3]//1024} KB')
    return out

NAV_MARKS = None  # 延迟构建

def write_epub(pages, fonts, bg_dir, n_pages):
    if os.path.exists(OUT): os.remove(OUT)
    z = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_STORED, compresslevel=0)
    z.writestr('mimetype', 'application/epub+zip', zipfile.ZIP_STORED)
    z.writestr('META-INF/container.xml',
'''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>''')
    CSS = '''@namespace epub "http://www.idpf.org/2007/ops";
html,body{ margin:0; padding:0; width:%dpx; height:%dpx; overflow:hidden; }
body{ position:relative; }
.pg{ position:relative; width:%dpx; height:%dpx; overflow:hidden;
     background:#FFF; }
.bg{ position:absolute; inset:0; width:%dpx; height:%dpx; }
.t{ position:absolute; line-height:1; white-space:pre; margin:0; }
@font-face{ font-family:'NSR'; src:url('../fonts/nsr.woff2') format('woff2'); font-weight:400; }
@font-face{ font-family:'NSB'; src:url('../fonts/nsb.woff2') format('woff2'); font-weight:700; }
@font-face{ font-family:'LWR'; src:url('../fonts/lwr.woff2') format('woff2'); font-weight:400; }
@font-face{ font-family:'LWM'; src:url('../fonts/lwm.woff2') format('woff2'); font-weight:700; }
:root{ --song:'NSR','NSB',serif; --kai:'LWR','LWM',serif; --sans:sans-serif; }
''' % (VW, VH, VW, VH, VW, VH)
    z.writestr('OEBPS/styles/fxl.css', CSS)
    for key, (fam, wt, fname, _) in fonts.items():
        z.write(os.path.join(bg_dir, '..', f'f_{key}.woff2'), f'OEBPS/fonts/{fname}')
    # 找导航锚点：卷隔页与各节章首页
    doc = fitz.open(PDF)
    anchors = []  # (spine_index, label)
    seen = set()
    for i in range(n_pages):
        t = re.sub(r'\s+', '', doc[i].get_text())
        m = re.match(r'^卷([一二三四五六七八九十]+)·論([甲乙丙丁戊己庚辛壬癸])$', t)
        if m and 'vol' not in seen:
            pass
        if t.startswith('卷') and '·論' in t[:8] and len(t) < 12:
            if i not in seen:
                anchors.append((i, t)); seen.add(i)
        m2 = re.match(r'^第(\d+)节', t)
        if m2 and i not in seen:
            anchors.append((i, t[:20])); seen.add(i)
        if i == 0 and i not in seen:
            anchors.insert(0, (0, '封面')); seen.add(0)
    # 每页 xhtml
    for i, (bg, spans) in enumerate(pages):
        label = [a[1] for a in anchors if a[0] == i]
        title = esc(label[0]) if label else f'第{i+1}页'
        body = (f'<img class="bg" src="../images/{bg}" alt=""/>' + ''.join(spans))
        x = (f'<?xml version="1.0" encoding="utf-8"?>\n'
             f'<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-Hans"><head>'
             f'<meta charset="utf-8"/><title>{title}</title>'
             f'<meta name="viewport" content="width={VW}, height={VH}"/>'
             f'<link rel="stylesheet" type="text/css" href="../styles/fxl.css"/></head>'
             f'<body><div class="pg">{body}</div></body></html>')
        z.writestr(f'OEBPS/text/pg{i:04d}.xhtml', x)
    # 背景图
    for i, (bg, _) in enumerate(pages):
        z.write(os.path.join(bg_dir, bg), f'OEBPS/images/{bg}')
    # nav
    nav_li = ''.join(f'<li><a href="text/pg{a[0]:04d}.xhtml">{esc(a[1])}</a></li>'
                     for a in anchors)
    z.writestr('OEBPS/nav.xhtml',
'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-Hans"><head><meta charset="utf-8"/><title>窮通寶鑑箋注</title></head>
<body><nav epub:type="toc" id="toc"><h1>目錄</h1><ol>''' + nav_li + '''</ol></nav></body></html>''')
    # opf
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="css" href="styles/fxl.css" media-type="text/css"/>']
    for key, (fam, wt, fname, _) in fonts.items():
        manifest.append(f'<item id="f_{key}" href="fonts/{fname}" media-type="font/woff2"/>')
    for i, (bg, _) in enumerate(pages):
        manifest.append(f'<item id="bg{i}" href="images/{bg}" media-type="image/jpeg"/>')
        manifest.append(f'<item id="pg{i}" href="text/pg{i:04d}.xhtml" media-type="application/xhtml+xml"/>')
    spine = ''.join(f'<itemref idref="pg{i}"/>' for i in range(n_pages))
    opf = (f'<?xml version="1.0" encoding="utf-8"?>\n'
           f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="zh-Hans">\n'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
           f'<dc:identifier id="uid">urn:uuid:qtb-fxl-2026</dc:identifier>\n'
           f'<dc:title>窮通寶鑑箋注（版式本）</dc:title>\n'
           f'<dc:creator>余春台 编次 · 徐樂吾 評注</dc:creator>\n'
           f'<dc:language>zh-Hans</dc:language>\n'
           f'<meta property="dcterms:modified">2026-09-12T00:00:00Z</meta>\n'
           f'<meta property="rendition:layout">pre-paginated</meta>\n'
           f'<meta property="rendition:orientation">portrait</meta>\n'
           f'<meta name="cover" content="bg0"/>\n'
           f'</metadata>\n<manifest>\n' + '\n'.join(manifest) + '\n</manifest>\n'
           f'<spine page-progression-direction="ltr">\n{spine}\n</spine>\n</package>')
    z.writestr('OEBPS/content.opf', opf)
    z.close()

if __name__ == '__main__':
    main()

# guji-ebook-skill · 古籍电子书制作 Skill（双品类）

把高清扫描古籍（PDF）制作成两种风格的电子书，共用同一份整理数据：

| 品类 | 风格 | 面向 | 输出 |
|---|---|---|---|
| **A 整理本** | 横排流式版式：多版本对读、简繁分工、章旨/白话/术语随文、书影配图 | 「读懂」 | 印刷级 PDF + 重排版 EPUB + FXL 版式本 EPUB |
| **B 复刻本** | 直排刻本风格：按原书行款逐字落格、双行夹注、朱圈句读、书口鱼尾、宣纸底（对齐 [vRain](https://github.com/shanleiguang/vRain) 视觉） | 「原貌沉浸」 | 复刻 PDF（文字可选中检索） |

实战验证：**《道德经三版本對照箋注》482 页**（81 章）·**《穷通宝鉴箋注》562 页**（113 节）·**《黃帝內經素問》828 页**（81 篇，含王冰注+新校正三层）·素問**复刻本**（齊伋体直排对页）。

```
                    ┌─ 品类 A 整理本：build_*_full.py ──▶ PDF + EPUB（重排版/FXL 版式本）
扫描 PDF ─▶ 录文 ─▶ book_data.json ─┤
（书影/行款实测）  （经/注/校正+阐释层）└─ 品类 B 复刻本：build_*_fuke.py ──▶ 直排复刻 PDF
```

## 仓库结构

```
SKILL.md                      ← Skill 本体：全流程方法 + 踩坑规范（字体/配图/版式/管线/QA/双品类）
01-调研清单-图书与电子书制作规范.md   ← 开本/版心/字号/图文/注解/分页 全参数清单
02-范例-版式规格书与样章.md         ← 版式规格书范例
scripts/
├── fetch_fonts.sh            ← 下载开源字体（思源宋体 CJK TC 全字库 + 霞鹜文楷）
├── render_audit.sh           ← 通用 HTML→PDF 渲染器（字体审计+自动重渲）
└── stamp_folios.py           ← 通用页码盖印（PyMuPDF）
examples/
├── daodejing/                ← 道德经：整理本 + 复刻本 双线参考实现
│   ├── book.html / build_book_full.py / content_81.py   （品类 A）
│   └── build_ddj_fxl.py                                 （FXL 版式本）
├── qiongtongbaojian/         ← 穷通宝鉴：整理本 + FXL
├── huangdineijing/           ← 黄帝内经素问：无文本层扫描的完整示范
│   ├── parse_suwen.py        ← 录文获取与装配（维基文库四部丛刊本+殆知阁双源）
│   ├── build_neijing_full.py / content_nj.py            （品类 A，828 页）
│   ├── build_neijing_fuke.py                            （品类 B 复刻引擎 ★）
│   └── build_nj_fxl.py                                  （FXL 版式本）
└── */assets/                 ← 书影/卷端叶/宣纸底图（公有领域图版）
```

## 环境依赖

```bash
# Python3 + 三个 pip 包；渲染用 Microsoft Edge 或 Chrome（无头打印）
pip3 install pymupdf opencc-python-reimplemented pillow fonttools brotli
bash scripts/fetch_fonts.sh        # 思源宋体全字库 OTF×2 + 霞鹜文楷×2（品类 A 用）

# 品类 B 复刻本另需齊伋體（与 vRain 同款主字体，fonts/ 目录不入库）：
curl -L -o examples/huangdineijing/fonts/qiji-combo.ttf \
  https://github.com/LingDong-/qiji-font/releases/download/0.0.4/qiji-combo.ttf
```

## 品类 A · 整理本调用（以道德经为例）

```bash
cd examples/daodejing
python3 build_book_full.py                        # 数据 → 全书 HTML + 重排版 EPUB
../../scripts/render_audit.sh book_full.html 道德经三版本对照笺注-全书.pdf   # 渲染+字体审计自动重渲
python3 ../../scripts/stamp_folios.py 道德经三版本对照笺注-全书.pdf          # 地脚盖页码
python3 build_ddj_fxl.py 道德经三版本对照笺注-全书.pdf 道德经三版本对照笺注-全书-版式本.epub   # FXL 版式本（可选）
epubcheck 道德经三版本对照笺注-全书.epub           # 重排版校验（可选）
```

黄帝内经（无文本层扫描 → 录文）多一步装配：

```bash
cd examples/huangdineijing
python3 parse_suwen.py             # 维基文库四部丛刊本(含王冰注)+殆知阁双源 → book_data.json
python3 build_neijing_full.py      # → neijing_full.html + 重排版 EPUB（81 篇）
# 渲染/盖码/FXL 同上，脚本为 build_nj_fxl.py
```

**换一本书**：复制 `examples/daodejing/`（或 `huangdineijing/`）为新目录，替换 `book_data.json` 与 `content_*.py`（章旨/白话/术语撰写层），按 SKILL.md §8 扩章流程生成。

## 品类 B · 复刻本调用（以素问·上古天真论为例）

```bash
cd examples/huangdineijing
# 0) 前置：qiji-combo.ttf 已放入 fonts/（见上），assets/paper_vr.jpg 宣纸底图已就位

# 1) 整篇复刻（默认篇 1；可传篇次 1..81）
python3 build_neijing_fuke.py          # → 复刻-上古天真論篇第一.pdf（直排对页）

# 2) 单页样本
python3 - <<'PY'
import fitz
src = fitz.open('复刻-上古天真論篇第一.pdf')
one = fitz.open(); one.insert_pdf(src, from_page=0, to_page=0)
one.save('复刻样本-对页一.pdf')
PY

# 3) 行款/风格参数在 build_neijing_fuke.py 头部参数区，一书一组：
#    CV_W/CV_H 画布、LEAF_COL×ROWS 行款、BIG/SMALL 字号、鱼尾五边形、
#    版心书名、NOTE_RED_BOOKS 红底白字出处签词典、MORDANTS 墨钉还原表
```

复刻本与整理本**共享同一份 `book_data.json`**：经文(p)/王冰注(zhu)/新校正(xiao)三层直排落格；朱圈句读由殆知阁标点录文 difflib 对齐自动生成；墨钉等版刻特征按叶面实察入 `MORDANTS` 表。

## QA 体系（实战沉淀）

| 关卡 | 工具 | 说明 |
|---|---|---|
| 字体零回退 | 出片审计 + 自动重渲 | PDF 出现 STSongti/PingFang 等 = 失败；详见 SKILL.md §1 |
| 版面验收 | judge 逐页抽样 | 110dpi 误判字形细节时用 220dpi 高清复核 |
| 数据洁净 | 生成器内置 | OpenCC 转繁、实体解码、句对污染过滤、增补区异体字归一 |
| 复刻本越界检查 | cells 遍历断言 | row<ROWS、col<COLS；密排参数下防溢框 |
| EPUB | epubcheck / XML 解析 | 重排版零错误；FXL 版式本逐文件校验 |

## 授权

代码 MIT；古籍文字与书影为公有领域；字体 SIL OFL（齊伋體见 [LingDong-/qiji-font](https://github.com/LingDong-/qiji-font)，正名「令東齊伋體」）。详见 `LICENSE`。

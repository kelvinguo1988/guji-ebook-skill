# guji-ebook-skill · 古籍整理电子书制作 Skill

把高清扫描古籍（PDF）通过 AI 整理成**多版本对读、图文混排、简繁规范的精美电子书**，一次性输出**印刷级 PDF** 与 **EPUB 3**。

本仓库是一个可直接挂载的 Agent Skill（`SKILL.md`）+ 一套经过 421 页全书实战验证的参考实现（`examples/daodejing/`《道德经三版本對照箋注》）。

```
扫描古籍 PDF 群 ──定位/裁切/核验──▶ 书影 assets/
整理数据(释文/古注) ─────────────▶ book_data.json
                   │
   book.html（版式设计系统 + 全部内容，唯一手工源）
                   ├──▶ build_pdf.sh ──▶ 印刷级 PDF（字体审计自动重渲）
                   └──▶ build_epub*.py ─▶ EPUB 3（epubcheck 零错误）
```

## 成品效果

- 《道德经三版本對照箋注》全书 **421 页**（16 开 185×260mm，81 章全）：每章含**章首页**（章号+章题+章旨）→ **四版本对读**两页（王弼本/河上公本/帛书甲本/帛书乙本竖排面板，朱丝栏、签条凸出）→ **古注**（王弼注+河上公章句，繁体）→ **今译+校勘记**（简体阐释+程序比对异文表+规则校按）。
- 第一章为全具样章：另含 石涛楷书书影、南宋建本书影、字词笺释。
- 字体审计零系统回退；EPUB 通过 epubcheck 零错误。

## 仓库结构

```
SKILL.md                      ← Skill 本体：全流程方法 + 踩坑规范（字体/配图/版式/管线/QA）
01-调研清单-图书与电子书制作规范.md   ← 开本/版心/字号/图文/注解/分页 全参数清单
02-范例-版式规格书与样章.md         ← 版式规格书范例
scripts/
├── fetch_fonts.sh            ← 下载开源字体（思源宋体 CJK TC 全字库 + 霞鹜文楷，断点续传+校验）
├── render_audit.sh           ← 通用 HTML→PDF 渲染器（字体审计+自动重渲）
└── stamp_folios.py           ← 通用页码盖印（PyMuPDF）
examples/daodejing/           ← 参考实现（可整目录复制的模板）
├── book.html                 ← 唯一内容与设计源（改书只改这一处）
├── build_book_full.py        ← 数据 → 全书 HTML + EPUB 生成器
├── content_81.py             ← 各章章旨/今译（人工撰写层）
├── build_pdf.sh              ← 本例渲染入口（含审计重渲）
├── build_epub_sample.py      ← 第一章样章 EPUB
└── assets/                   ← 书影（公有领域古籍图版裁切）
```

## 快速开始

```bash
# 0) 依赖：Python3 + PyMuPDF + OpenCC(pip)、Microsoft Edge 或 Chrome（无头打印）、java + epubcheck(可选)
pip3 install pymupdf opencc-python-reimplemented pillow

# 1) 下载字体（思源宋体全字库 OTF×2 + 霞鹜文楷×2，约 100MB，断点续传）
bash scripts/fetch_fonts.sh

# 2) 生成全书 HTML 并渲染 PDF（自动做字体审计，发现系统字体回退即重渲）
cd examples/daodejing
python3 build_book_full.py          # → book_full.html + 全书.epub
../scripts/render_audit.sh book_full.html 道德经三版本对照笺注-全书.pdf
python3 ../scripts/stamp_folios.py 道德经三版本对照笺注-全书.pdf

# 3) 校验 EPUB
epubcheck 道德经三版本对照笺注-全书.epub
```

换一本古籍：复制 `examples/daodejing/` 为新目录，替换 `book_data.json`（四版本经文+古注数据）与 `content_*.py`（章旨/今译撰写层），按 `SKILL.md` §8 扩章流程生成。

## QA 体系（本项目实战沉淀）

| 关卡 | 工具 | 说明 |
|---|---|---|
| 字体零回退 | 出片审计 + 自动重渲 | PDF 嵌入字体出现 STSongti/PingFang 等 = 失败；确定性失败=字族覆盖缺陷（详见 SKILL.md §1） |
| 无回退判别 | monospace 终极测试 | 待检字符末级回退设为等宽体，缺字无所遁形 |
| 版面验收 | judge 逐页抽样 | 110dpi 误判字形细节时用 220dpi 高清裁切复核 |
| 数据洁净 | 生成器内置 | OpenCC 注文转繁、实体解码、句对污染过滤（勘误条目/卷末题记剔除） |
| EPUB | epubcheck | 零错误零警告 |

## 授权

代码 MIT；古籍文字与书影为公有领域；字体 SIL OFL（详见 `LICENSE`）。

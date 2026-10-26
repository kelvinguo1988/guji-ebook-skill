# 清静经 AB 版战役（2026-10-05 开局）

## 底本（用户指认）
- 识典古籍 DZ0756《太上老君说常清静经注》一卷，元佚名撰
- 体例：**经文分句作注**，每条先阐释、后列感应事迹；注含内丹/外丹/佛教空幻说
- 经文约 401 字（DZ0757 白文本著录）→ 全书叶数极少（预计 8–15 叶），**B 版战役体量小，一个会话可完成读锚**

## 文本源探测结果
- 殆知阁 daizhige：道藏/ 目录仅 9 文件、无清靜經 ✗
- luckclub：类目无道经 ✗
- weread：搜索可用（匿名），正文需登录 cookie；但 weread 非刻本，不合 B 版底本要求
- **结论：注文与扫描页均需识典 cookie 通道**（argus 风控已实测：匿名 API=JS 挑战页、headless=Data exception）

## 待用户提供（解锁全部工序）
识典古籍登录后复制 cookie：F12 → Network → 任一请求 → Cookie 头全文，
存为 examples/qingjingjing/work/sdj_cookie.txt 后告知。
→ 即可：① API 拉全书经注文（A 版数据装配）；② 取扫描页图（B 版左原叶）

## 管线
A：book_data.json（经/注对）→ build_book_full.py 复用链 → PDF（零回退审计）→ FXL EPUB
B：复制素问引擎（六处必改清单）→ 行款实测（道藏本行款待扫描件确认）→ 逐叶锚定（量小，
   一次读齐）→ 左原叶右复刻对页 PDF → FXL EPUB（与 PDF 一致）

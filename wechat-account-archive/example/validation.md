# 2026-10-21 有界真实验证

## 输入与范围

用户给定名称“随机森林之外”（也可能输入“随机深林之外”）以及可选单篇链接：
https://mp.weixin.qq.com/s/-2IEzUVYNJP8YFYSHDDmnA

仅验证公开单篇身份、正文、图片与本地归档，不从该样本推断全账号目录。该名称、署名和链接不是通用脚本默认参数，未来使用必须重新核验。

## 实测

运行源仓库 `scripts/archive.py read-url <上述链接> --with-media`，独立数据目录为 `C:\Users\admin\Documents\CodexData\wechat-account-archive`。

- 标题：当 AI 开始自主挖因子：量化交易的 Harness 时代来了。
- 页面账号昵称：随机森林之外；页面作者署名：真剑圣。
- 页面 biz：MzkwMzE5ODMxMQ==。这是本次页面观察，不等于已完成 fakeid/alias 搜索绑定。
- 解析文本 8897 字符，包含生成的图片位置标记，不能当纯正文文字数。
- 识别 18 个图片位置（17 个唯一图片 URL，其中一处重复）；所有位置均已有本地图片，正文成功 1，图片缺失 0。
- 生成 original.html、article.md、metadata.json、media、catalog.csv、catalog.jsonl、missing.json、report.json/report.md、SQLite。
- 本地报告目录：`C:\Users\admin\Documents\CodexData\wechat-account-archive\single\a416543f39f6a18edf1c9ec1`。
- 报告明确 directory=partial、目录完整=false、all_complete=false。这个单篇样本没有目录终点证据。

本机初始没有登录态、wechat-reader 或候选后端监听端口（检查 8000/8001/8080/3000/5000，非全端口扫描）。已经在独立数据目录创建 venv，安装 Playwright 1.56.0，Edge 155.0.4283.62 无界面启动检查成功；未部署常驻服务、未更改全局配置。

## 行为验收

34 项离线行为测试通过，覆盖多篇推送、文章数与推送数差异、总数 unknown、瞬时/持续空页、重复页、损坏 publish_info、中断后重开数据库、媒体中断、同时间文章增量、采集中新增导致偏移、重复链接、缓存/版本、资产损坏、图片型文章、正文与媒体分账、付费试读、身份冲突、重名及浏览器 JSON/innerHTML 适配。

## 仍待验证

没有公众平台管理员扫码会话，未执行真实账号 searchbiz、fakeid/alias 绑定、全历史 appmsgpublish 分页与总数单位验收；不能声称账号全历史已拉全。登录后需要真实检查多篇推送的 begin/count 语义和总数单位，再复核首尾日期、批数/文章数、重叠响应和目录稳定性。任何隐藏/已删除且无索引文章仍是不可核验范围。

wechat-reader 未安装；其 CLI 和 models/parser 源码已核验，innerHTML 适配通过合成测试，未跑真实浏览器兜底。不要把合成测试写成外部工具实测。

来源：用户提供的链接与本机脚本实际输出；协议参考见 ../references/backend.md。原核验日期为 2026-10-21。

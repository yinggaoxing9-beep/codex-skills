# 输出与完整性

每个账号按 `backend:fakeid` 的哈希划分独立目录，不跨后端混用标识。账号名称和错字映射保存在独立数据根目录的 identities.json，并附 nickname/alias/biz/原文核验依据；每次联网调用重新验证。

## 文件

- `archive.sqlite`：articles 为可恢复正文任务；kv 保存身份和本轮游标；evidence 保存每个原始目录响应的脱敏副本、轮数、begin、用途、采集时间；assets 为按图片 URL 复用的缓存。
- `catalog.jsonl` / `catalog.csv`：每篇稳定 ID、原链接、规范链接、署名/原创标志、时间、状态、版本与本地 Markdown 路径。原始 payload 保存 observed_urls；同一时间戳和多篇推送全部保留，不用时间作为排除条件。
- `articles/<id>/<内容哈希>/original.html` 或 `browser-snapshot.html`、`article.md`、`metadata.json`：内容变化保留多个版本；Markdown 使用本地资产相对路径，图片顺序与重复位置保留。图片单独下载失败不抹掉正文成功。
- `media/<内容哈希>.<类型>`：图片按内容去重，检查已有资产哈希。音视频/iframe 当前单独标注 unsupported，不宣称媒体齐全。
- `missing.json`：失败正文、图片、未支持媒体与各项错误；它是失败队列的可读导出，实际恢复从 SQLite 状态进行。
- `report.json` / `report.md`：本轮 cutoff、完成时间、发现数、正文成功/缺失数、图片缺失/未支持媒体、目录总数和计数单位、终点证据、检查点、错误与路径。

## 状态解释

目录 `partial` 表示未完成两次稳定全扫描或存在分页问题；`stable_observed` 表示两轮完整扫描的批次与元数据签名一致，且每轮末尾重复空页和后移探测为空。原始 `total_count` 始终独立报告；未核验单位时 `total_unit=unknown`、`complete=false`、`all_complete=false`。这保留了全量验收目标，没有把搜索结果或一个空页当终点证明。

`body_complete_for_discovered` 只说明已发现文章均有非空正文或图片及本地文件，不能补足目录证据。`media_complete_for_downloaded` 只针对已成功下载正文中识别的媒体；必须同时查看 body_missing。目录完整、正文完整、媒体完整均独立，最终报告不能只报一个“成功”。

正文至少区分 pending、ok、deleted、restricted、captcha_required、rate_limited、parse_failed、network_error、cache_missing；其他可重试或格式状态保留原码。每次调用补失败项，已知文章即使目录登录失效仍会自动重试已核验缓存账号的正文，或用 bodies-only 独立续做。HTTP 200 的空壳/验证页不能记 ok。未尝试文章的媒体数量未知，不记成“已确认零缺失”。

## 恢复与效率

每个目录页先保存证据，再把文章和下一游标原子提交。解析损坏整页停在原 begin，禁止 silently continue。重复页或不前进停止；重叠页发生偏移时保留已归档文章与证据，仅重启当前扫描轮。两次全扫描有差异则继续有界复核；达到轮数或请求预算显示 partial，重复命令续跑。

本轮记录开始 cutoff；采集中发现的新文章仍收录，目录中 after_cutoff 单独标注，并通过后续扫描收敛，不能因时间相同跳过文章。全目录扫描默认每次重新核对；正文缓存默认 30 天内复用，元数据变化立即重读；用 `--refresh-days 0` 强制复查内容以发现无元数据变化的正文更新。图片失败独立重试，不重复获取缓存正文。

会话只需要读取返回的简短报告和必要候选。不要打印 evidence 全表、整页 HTML、整库 Markdown 或下载日志；分析阶段按篇按需读取文件。目录、索引和失败状态在磁盘上，是跨上下文续做的依据。

## 公开链接范围

`public-links-v1` 使用已发现清单，目录固定 partial、scope=discovered_public_links、账号总数 null。清单中的成功、失败、未尝试文章均计入 discovered，不能只导入成功文章后宣称正文齐全。公开合集的终点与篇数只证明相应合集的观测范围，不等价于账号完整历史。

离线导出 `manifest.json` 分别记录正文数、图片位置数和按内容去重的图片文件数；三者不能混用。目录中的正文成功文件应可打开，图片相对路径指向实际存在且哈希正确的文件。ZIP 解压后从 index.html 阅读，原始采集证据保留在源归档。

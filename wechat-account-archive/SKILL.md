---
name: wechat-account-archive
description: 读取微信公众号文章链接（mp.weixin.qq.com），提取正文供总结、分析或与本地项目对照；也支持按公众号名称核验账号、归档全部可访问历史文章及图片、增量补采和缺失核查。用户给微信文章链接或公众号名并要求读取/采集时使用。
---

# 微信公众号读取与归档

先按用户输入和意图选择入口。单篇链接读取与账号全量归档都属于本 Skill；后续摘要、研究或代码对照使用读取结果继续完成。

## 文章链接：先直接读取

用户提供 `https://mp.weixin.qq.com/s/...` 或 `/s?__biz=...` 并说“看看文章”“总结”“分析”“对照项目”时，先执行：

`python -X utf8 -B <skill>/scripts/archive.py read-url "<文章URL>"`

- 直接走本地脚本 HTTP，不要求公众平台登录，不先运行账号搜索、doctor、login，也不因其他抓取器失败就跳过此入口。收到带文字的分享内容时提取其中的完整微信文章 URL，不改变大小写。
- 默认读取正文并保留图片引用，输出简短 JSON 和 `markdown_path`、`html_path`、`metadata_path`；随后按需读取 Markdown 完成用户任务。需要图表/图片分析或保存图片时加 `--with-media`，按位置读取本地资产；仅有图片引用不能声称读过图中内容。
- 30 天内有效正文缓存复用；用户要求重新抓取或检查更新时加 `--refresh-days 0`。媒体按需补采，不重复下载缓存正文。
- 只有脚本返回明确的验证码/渲染/访问状态且浏览器有实际帮助时，才按 [读取与登录协议](references/backend.md) 有界兜底；网络权限错误先按当前环境的执行权限处理，不能直接归因微信风控。不得保证任意文章都无需浏览器。
- 单篇成功不启动该账号全历史采集，也不证明目录完整。用户明确要“这个链接所属公众号的全部文章”时，再进入账号归档流程，链接可辅助身份核验。

## 公众号名称：全量与补采

1. 运行 `python -X utf8 -B <skill>/scripts/archive.py doctor`。数据默认位于 Windows 用户的 `Documents/CodexData/wechat-account-archive`（其他平台为用户数据目录），可用全局参数 `--data-root <独立目录>` 覆盖；数据不得放入 Skill 或 Git 仓库。
2. 先区分可用入口：用户没有公众号管理权限或只要求公开可见内容时，使用下方公开清单流程，不再要求扫码或创建登录依赖。公众平台全目录接口才需要有效登录态；按 [读取与登录协议](references/backend.md) 准备独立依赖并运行 `login`，由用户使用公众号管理员微信扫码。不读取其他应用凭据，不部署常驻服务或修改全局浏览器配置。
3. 运行 `python -X utf8 -B <skill>/scripts/archive.py run "<公众号名>"`。首次扫描全目录，后续重扫目录并补新文章、变化内容、过期缓存和失败资产。中断后重复同一命令继续；`--max-pages` 达到本次预算必须报告 partial。
4. 名称有错字时搜索原名和有界片段，比较候选。fakeid/alias 与独立文章页 nickname/biz 一致才缓存；署名仅辅助，不按作者过滤。真正歧义时询问后传 `--select-fakeid`，仍须核验。改名或标识变化重新核验。可选 `--sample-url` 用于身份核对。
5. 按返回的 `report.json` / `report.md` 和 [输出与验收](references/completeness.md) 报告证据及缺口。

目录登录失效后，已知文章仍可处理：`run "<公众号名>" --bodies-only --archive <账号数据目录>`。浏览器兜底与 HTML 导入见协议参考。

## 无管理权限：公开清单下载

通过公开搜索、文章内链和公开合集核验账号、发现链接；名称有歧义先核对账号。保存目录来源与分页证据。全历史总数不可验证时保持未知，不把合集篇数当全账号篇数。

- 下载必须保留来源中的完整 URL，尤其是 `chksm`；`canonical_url` 只用于去重。原始 `http://mp.weixin.qq.com` 链接自动升级 HTTPS。不要先规范化链接再交给读取器。
- 将已发现的全部文章写为 UTF-8 JSONL，每行包含 `url`、`title`，可含 `create_time` 与 `discovery_source`。先完整登记，再执行 [公开清单与离线导出](references/backend.md#公开清单与离线导出)；缺失项也必须进入同一份报告。
- 使用 `scripts/download_list.py` 续传，优先复用已核验缓存；先保存所有正文，再补图片。连续三个验证/访问/网络错误自动停止正文队列，保留待处理记录。不要改用无界浏览器逐篇循环。
- 使用 `scripts/export_archive.py` 导出可离线浏览的目录、HTML、Markdown、图片和 ZIP；实际交付文件路径以及正文/图片缺失数量。已有快照和单篇缓存需要合并时先备份并核对账号。

## 验收边界

- 目录、正文、媒体独立记账；`body_complete_for_discovered` 仅针对已发现清单。未知总数保持 unknown/null；HTTP 200、一次空页、队列处理完均不能证明全量。
- 按推送批次推进游标，展开全部文章；两轮扫描、重叠复核和脱敏分页证据检测位移。保留同时间戳文章，失败、重复页、解析错误和预算耗尽不得算完成。
- 原文、Markdown、媒体位置、元数据、版本和任务状态落盘；图片文章不是空文。受限内容不绕过权限，失败有限重试，下次再补。
- 当前 raw 协议的总数单位未通过真实登录验收，保持 `stable_observed`、`complete=false`。不得宣称平台全历史无遗漏。
- 分析按需读取本地文件，不把整页 HTML、整库正文灌入会话。不自动建立定时任务。

行为测试：`python -X utf8 -B -m unittest discover -s <skill>/tests -v`。
历史账号样本按需查看 [归档验证记录](example/validation.md)，单篇入口与边界按需查看 [链接读取验证](example/link-reading.md)；案例不是默认输入或新授权。

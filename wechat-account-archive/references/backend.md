# 后端与登录契约

## 主路径

`archive.py` 的归档核心只依赖 Python 3.11+ 标准库。名称搜索和目录枚举使用用户自己登录的微信公众平台会话，HTTPS 访问 `cgi-bin/searchbiz` 和 `cgi-bin/appmsgpublish`，不读取 RSS 或本地最近文章库冒充全历史。

按公众号名称枚举历史目录时，先运行 `doctor` 检查登录与工具；单篇链接直接用 `read-url`，不依赖目录登录。现成服务如果只能返回展开后的 articles/count，缺少原始 publish_list、解析错误和游标证据，则不能接入为完整枚举来源。当前实现选择直接读取原始协议，不要求部署服务器。

协议线索来自 [wechat-download-api routes/articles.py](https://github.com/tmwgsicp/wechat-download-api/blob/main/routes/articles.py)（AGPL-3.0-only）和 [routes/search.py](https://github.com/tmwgsicp/wechat-download-api/blob/main/routes/search.py)。本 Skill 独立实现协议客户端，没有复制、链接或修改该项目代码，也不分发其服务；不要将其 AGPL 源码粘入本仓库。原项目的展开接口会跳过损坏 publish_info，且 count 为展开文章数，故没有复用这个有损封装。

`begin` 的推进候选单位是返回的 publish_list 推送批次数。每个非首段用 `begin-1,count=2` 对照前段最后批与本段首批，验证游标单位和位移。原始 `total_count` 单位不作未经核验的假设；同时记录总数与观察批数供人工复核。缺少总数不会补零。

## 单篇链接入口

`archive.py read-url "<微信文章URL>"` 不初始化 Platform、不读取 session.json；默认 HTTP 获取并解析有效正文，保存原文、Markdown、元数据和 SQLite 缓存，返回绝对文件路径。默认不下载图片；Markdown 保留原始图片链接和位置，`--with-media` 才归档图片并返回独立媒体核查。正文默认缓存 30 天，`--refresh-days 0` 强制刷新；刷新失败返回真实失败状态，不以旧缓存冒充本次成功。

默认不调用浏览器。若专用 HTTP 读取确实遇到验证码或渲染失败，且已安装可用 reader，可显式传 `read-url "<URL>" --reader <可执行文件>`，仅进行一次有界兜底；也可使用当前已授权浏览器读取。仅运行命令遭沙箱/网络权限拦截并不证明微信反爬，应先处理执行环境权限。已删除或无权访问的内容不能靠重复兜底变成成功。

成功后读取返回的 `markdown_path` 完成总结或对照任务；完整 HTML 保留在磁盘，无需打印进会话。单篇记录只代表该 URL 的正文与已请求资产，不包含账号目录完整性声明。

## 首次登录

Windows 运行 `scripts/prepare_login.ps1 -DataRoot <独立数据目录> -Login`，在打开的 Edge 窗口用有公众号管理权限的微信扫码。脚本仅在该数据目录创建 venv 并安装固定版本 Playwright；使用现有 Edge，不安装常驻服务，不修改全局浏览器配置。需 Chromium 时显式传 `-Channel chromium` 才下载独立浏览器。无扫码账号时不能调用平台目录接口。

依赖准备和登录可以分开：去掉 `-Login` 只准备依赖；随后用 `<数据目录>/.venv/Scripts/python.exe -X utf8 -B <skill>/scripts/archive.py --data-root <数据目录> login`。非 Windows 可自行创建独立 venv，安装同版本 Playwright，再执行 `login --channel chrome` 或安装独立 Chromium。

登录态只写 `<数据目录>/session.json`（token/cookie/captured_at）。Windows 准备脚本收紧专用数据目录 ACL，不能对已有无关目录执行；POSIX 文件使用 0600。不要输出文件内容、写入 Skill/Git、截图上传凭据或让用户把 Cookie 发进聊天。调用方可显式指定已授权导出的同 schema 会话文件，不能从其他软件配置或浏览器隐式提取。登录失效运行同一登录入口更新会话。

身份搜索每次重验：原始 query 与有界片段检索候选，只有 fakeid/alias 和独立文章页 nickname/biz 一致才自动绑定。名称近似只能排名，不能作为唯一证据。若映射过时，先复核改名、注销或新 fakeid；不要自动把新 ID 并入旧账号归档。`--select-fakeid` 只选择候选，不绕过后续核验。

## 正文兜底

主路径固定为公开文章 HTTP 获取，缓存优先。不将目录 Cookie 发送给文章图片或外部主机；媒体仅拉取微信图片域名，重定向不自动携带会话。每次请求有超时、限速和有限重试，验证码/付费/权限错误交由人工。

已安装 [wechat-reader](https://github.com/xiguawang/wechat-reader)（MIT）时，传 `run "<公众号名>" --reader <wechat-reader可执行文件>`，只对主路径的解析/验证失败调用一次 CLI。其 `read --strategy auto --timeout 30 --json` 返回结构化状态，成功 html 为 js_content 的 innerHTML；保存为 `browser-snapshot.html` 并保存 reader_result，不能声称是原始全页 HTML。该工具上游把账号名写进 author 的情况不能当成真实作者署名。它对图片型文章可能返回未渲染状态，不应把该状态当空文章成功。没有安装或会话时不会盲目切换多个工具。

也可在已有授权浏览器中打开已知失败 URL，手工通过验证码，保存页面 HTML 到独立数据目录，再执行 `import-html <账号归档目录> <目录中的文章id> <保存的HTML>`。导入仍检查非空正文/图片和身份；保存来源及版本。需要浏览器操作时使用当前可用浏览器工具，不另行搜索每篇文章。

## 真实分页验收

登录后选择至少有多篇推送的账号，检查 evidence 中相邻 `begin` 与重叠响应，确认每批全部 appmsgex、缺失/损坏批数和总数单位。对照平台可见目录首/末日期、批数与文章数；检查末页重复请求、下一偏移探测、两轮签名一致以及新发布导致的偏移。如果单位/终点无法验证，保持 `stable_observed`，不能更名为完整。全历史无遗漏仍须保留已删除/隐藏无索引范围未知这一边界。

## 公开清单与离线导出

无公众平台管理权限时，公开搜索与合集提供发现范围，不证明账号全历史完整。保留每篇的原始请求 URL（包含 `chksm` 等公开参数）；canonical URL 仅用于去重。原始 HTTP 文章链接升级到 HTTPS，非微信主机、用户信息或自定义端口拒绝。验证码跳转记录 `captcha_required`，不自动跟随或重试。

清单为 UTF-8 JSONL，每行对象包含 `url`、`title`，可含 `create_time`、`discovery_source`。来源和分页证据保存在独立数据目录。

```text
python -X utf8 -B <skill>/scripts/download_list.py --catalog <清单.jsonl> --archive <账号归档目录> --biz <已核验biz> --name <已核验公众号名> --with-media
python -X utf8 -B <skill>/scripts/export_archive.py --archive <账号归档目录> --output <新的离线导出目录>
```

清单一次性校验账号并登记全部条目；`--max-articles` 限制本次需要联网的正文篇数，有效缓存不占预算。`--interval` 默认 2 秒，`--refresh-days` 默认 30 天。失败正文不阻止其他条目；连续三个验证/访问/网络错误停止正文队列，仍可保存已成功正文的图片。重复相同命令续传，验证码不能靠无界重试解决。已保存结果不因清单再次导入而重置。

报告 backend 为 `public-links-v1`；目录 scope 为 `discovered_public_links`，账号总数 null，始终 `all_complete=false`。正文成功不等于图片完整，图片缺失单独统计。

导出目录必须不存在。导出器生成 `index.html`、按日期标题命名的 HTML/Markdown、独立 `media/`、清单/缺失报告、manifest 和同名 ZIP。HTML 由已保存正文生成，不执行原页面脚本，保留图片顺序与重复位置；缺失图片显示原图链接。原始网页版本仍在源归档中，导出不改变源数据。

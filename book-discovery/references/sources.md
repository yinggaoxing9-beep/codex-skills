# 图书来源选择

书目核验和内容获取可以独立成功。用户指定来源优先；本表是默认路由依据，不是全部必查清单。

| 需求 | 优先来源 | 边界 |
| --- | --- | --- |
| 书名、作者、版本 | 出版社、作者、国家/大学图书馆；Open Library、Google Books 辅助 | 目录不证明可下载，聚合字段需核对 |
| 中文原版、译本、卷册 | 中文出版社、图书馆、用户可用的读书平台 | 英文书名相近不代表同一中文译本 |
| 开放学术专著 | DOAB、OAPEN、大学出版社/作者主页 | 核对具体许可；入库不证明某个主张 |
| 公版经典 | Project Gutenberg、Wikisource、开放数字馆藏 | 公版状态可能随司法辖区、译本、版本不同 |
| Z-Library / Anna's Archive | 当次核验的来源页面或已授权会话 | 候选文件和线索，独立核对版本与访问状态 |
| 原始实验/最新政策 | 书中引用的论文、数据、法规与官方更新 | 书适合体系与历史背景；最新结论需追溯原始材料 |

## Open Library

[Search API](https://openlibrary.org/dev/docs/api/search) 默认按作品返回，嵌套 editions 指向版本。[Books API](https://openlibrary.org/dev/docs/api/books) 解释 work/edition/ISBN 区别。核验用具体 edition 或 ISBN 接口，不拼接作品级 ISBN 数组和某一出版社/年份。

共享 bookctl 限制少量结果；遵守 [API 使用规则](https://openlibrary.org/developers/api)，同一来源串行低频。脚本不自动重试、不遍历全库，多次命令也由调用方控制间隔。经常使用可通过 BOOK_DISCOVERY_CONTACT 设置用户愿意公开的联系地址，不伪造联系方式。

## Google Books 与开放馆藏

[Google Books API](https://developers.google.com/books/docs/v1/using) 按官方要求配置 API key 或 OAuth；未配置时用网页或其他来源，不依赖无密钥偶尔成功的行为。密钥不进技能、日志或输出链接。预览和地域状态按当次结果记录。

[DOAB](https://www.doabooks.org/)、[OAPEN](https://www.oapen.org/)、[Project Gutenberg](https://www.gutenberg.org/) 按各自覆盖范围使用，仍核对版本和实际可读范围。

## Z-Library 与其他镜像来源

- 不内置“永久官方域名”。用户 URL 是待核验入口；搜索排名、HTTPS、品牌图标、镜像清单或 HTTP 200 不足以单独证明归属。
- 结合当前可核验项目公告、已知会话上下文和跨来源信息判断身份。仍含糊时不提交凭据或付款信息，继续搜公开书目并标记未验证。
- 优先沿用已授权浏览器会话；不导出 Cookie、不要求密码粘贴聊天、不扫描父目录找凭据。用户要求 API 适配时明确配置主机与凭据来源，凭据在技能/仓库外，不向未经核验的重定向主机转发。
- 第三方 eAPI 是候选执行契约；部署前核验端点、鉴权、错误和配额行为。不能把某实现写的限额作为平台保证。
- 只使用真实返回的书籍 ID/哈希，不推测下载链接。解析失败、登录缺失、访问受阻与零结果分别记录。
- 账号或镜像故障不阻断整个找书任务；交付已核验书目与其他可用入口，明确指定来源的缺口。

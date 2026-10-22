# Codex Skills 中文增强集

面向中文用户维护的个人 Codex Skills 仓库，重点增强：

- 多来源信息检索、证据分级与交叉核验
- 上市公司基本面、财报洞察与财务取证
- 研究材料摘要、比较与信息整合
- 技术讲解、管理决策、研究汇报、数据报告、融资与教学 PPT
- 中文 HTML 专题报告与交互自阅报告
- 品牌、设计系统、界面和视觉设计
- Codex 上下文治理与 Token 节省
- 长期记忆整理、冲突处理与过期管理

当前收录 **26 个个人 Skills**，包括 **8 个 PPT 技能**和 **1 个 HTML 报告技能**，同步日期为 2026-10-22。系统内置和插件附带的技能不包含在本仓库中。

技能调用名保持英文；中文增强入口和保留的上游英文入口并存，必要的英文关键词用于兼容中英文自动触发。

## 技能目录

| 技能 | 用途 | 示例调用 |
| --- | --- | --- |
| `academic-search` | 薄编排器：为模糊/跨学科问题选择专业 Skill | `使用 $academic-search 研究 AI 医疗的算法与临床证据` |
| `ai-computing-research` | AI/计算机前沿、版本、benchmark 与复现审计 | `使用 $ai-computing-research 找近半年 LLM 推理研究` |
| `biomedical-evidence` | 医学指南、综述、试验、绝对风险与安全边界 | `使用 $biomedical-evidence 评估改善睡眠的证据` |
| `research-toolkit` | 共享检索、规范化、去重和标识符核验工具层 | `使用 $research-toolkit 核验这些 DOI 和 PMID` |
| `evidence-research` | 当前、多来源、可审计的信息研究 | `使用 $evidence-research 调查……` |
| `stock-analysis` | 上市公司基本面、估值和财务取证 | `使用 $stock-analysis 分析腾讯最新财报` |
| `financial-analyst` | 财务比率、DCF、预算差异与预测 | `使用 $financial-analyst 建立 DCF` |
| `research-summarizer` | 已提供论文、报告和网页的结构化摘要 | `使用 $research-summarizer 比较这些报告` |
| `context-budget` | 审计上下文膨胀并减少 Token 消耗 | `使用 $context-budget 审计当前配置` |
| `memory-curator` | 管理 Codex 记忆、项目约定和任务交接 | `使用 $memory-curator 整理长期记忆` |
| `presentation-studio` | PPT 总入口：梳理需求并路由到专业演示技能 | `使用 $presentation-studio 制作一份演示文稿` |
| `technical-explainer-deck` | 技术讲解、架构说明、技术选型与内部培训 | `使用 $technical-explainer-deck 讲解 AI Infra 架构` |
| `executive-decision-deck` | 管理层决策、项目立项、预算与方案比较 | `使用 $executive-decision-deck 制作项目立项汇报` |
| `research-presentation` | 论文汇报、研究进展、组会与答辩 | `使用 $research-presentation 汇报这篇论文` |
| `data-report-deck` | KPI、经营复盘、周月季报与数据故事 | `使用 $data-report-deck 制作季度经营复盘` |
| `pitch-deck` | 融资 BP、商业模式与投资人路演 | `使用 $pitch-deck 制作融资路演材料` |
| `teaching-deck` | 课程、工作坊、示例、练习与复习 | `使用 $teaching-deck 制作培训课件` |
| `deck-review` | PPT 审阅、评分、验收、压缩与修复 | `使用 $deck-review 检查这份 PPT` |
| `html-report` | 中文专题报告、研究解读、战略简报与交互自阅 | `使用 $html-report 制作一份独立 HTML 研究报告` |
| `banner-design` | 社交媒体、广告、网站与印刷横幅 | `使用 $banner-design 设计活动横幅` |
| `brand` | 品牌语气、视觉身份、品牌资产与一致性 | `使用 $brand 整理品牌规范` |
| `design` | 综合视觉设计、标志、品牌物料与图标 | `使用 $design 设计品牌视觉物料` |
| `design-system` | 设计 Token、组件规范与一致性设计 | `使用 $design-system 建立设计 Token` |
| `hallmark` | 页面设计、审计、重设计与参考提取 | `使用 $hallmark 改进这个页面的视觉设计` |
| `ui-styling` | shadcn/ui、Tailwind 与可访问界面实现 | `使用 $ui-styling 实现响应式界面` |
| `ui-ux-pro-max` | UI/UX 决策、风格、配色、字体与交互 | `使用 $ui-ux-pro-max 设计产品管理界面` |

PPT 任务类型明确时可以直接调用对应专业技能；类型不明确时从 `presentation-studio` 开始。`deck-review` 用于审阅已有演示，`html-report` 用于独立 HTML 报告。

上述目录保存本地安装版本及其配套脚本、参考资料和资产。部分上游设计技能仍引用外部工具或其他技能，具体依赖以各自入口为准。

## 论文研究混合架构

论文研究采用“专业 Skill + 统一工具层 + 薄编排器 + 评测体系”：

    academic-search（只路由与跨域合并）
    ├─ ai-computing-research
    ├─ biomedical-evidence
    └─ 后续领域 Skill

    research-toolkit（共享 API、规范化、去重、标识符核验）
    evals/research-stack（路由、引用、领域质量、安全与 Token 预算）

明确的 AI/计算机或医学问题会直接使用专业 Skill，避免加载跨学科入口的全部规则。当前先用差异最大的两个领域验证架构；历史、地理、天文、社会学和哲学暂由 academic-search 明示“通用回退”，评测达标后再逐个加入。

统一工具层只处理稳定的数据操作，专业 Skill 负责领域判断。这样可以独立替换数据源或上游项目，而不必复制 API、去重和核验逻辑。

运行离线校验：

    python -m unittest discover -s research-toolkit/tests -v
    python evals/research-stack/score_eval.py lint

完整设计与扩展门槛见 [docs/research-stack-architecture.md](docs/research-stack-architecture.md)。

## 安装

### PowerShell 一键安装

在仓库根目录运行：

```powershell
.\scripts\install.ps1
```

默认安装到 `$env:USERPROFILE\.codex\skills`。安装后重新打开 Codex，或开始一个新任务，让技能列表重新加载。

只安装指定技能：

```powershell
.\scripts\install.ps1 -Skills evidence-research,stock-analysis
```

只安装这次更新的 PPT 和 HTML 技能：

```powershell
.\scripts\install.ps1 -Skills presentation-studio,technical-explainer-deck,executive-decision-deck,research-presentation,data-report-deck,pitch-deck,teaching-deck,deck-review,html-report
```

预览操作而不复制文件：

```powershell
.\scripts\install.ps1 -WhatIf
```

### 手动安装

把所需技能的完整目录复制到：

```text
C:\Users\<你的用户名>\.codex\skills\<skill-name>
```

不要修改技能目录名或 `SKILL.md` 中的 `name`，否则 `$skill-name` 显式调用可能失效。

## 使用方式

可以显式指定技能：

```text
使用 $stock-analysis 分析这家公司近五年的利润质量和现金流风险。
```

也可以直接用自然语言描述任务；Codex 会依据 `description` 自动选择匹配技能。对重要任务建议显式写出 `$skill-name`，便于确认实际使用的工作流。

这些是本地 Codex Skills，普通 ChatGPT 网页对话不会自动读取本机的 `.codex\skills` 目录。

## 维护约定

- 活动入口是每个目录下的 `SKILL.md`。
- `references/SKILL.en.md` 保存英文入口备份，便于回滚及对照上游升级。
- 上游专业 references 和脚本尽量保持原貌，中文调整优先集中在入口和用户界面元数据。
- 新增或更新技能后，应运行官方 `quick_validate.py`，并对有关脚本做最小冒烟测试。
- 禁止提交 API Key、Token、Cookie、私钥、账号数据、公司机密或真实用户记忆。

## 来源与许可证

本仓库包含基于第三方项目改编或保留的内容，详细来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本仓库自有内容按 MIT License 发布；第三方内容保留其原始版权和许可条件，不因同步而自动适用本仓库的 MIT 声明。

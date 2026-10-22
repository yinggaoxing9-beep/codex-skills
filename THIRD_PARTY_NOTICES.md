# 第三方来源与许可说明

本仓库对若干开源技能进行了中文本地化、Codex 适配或工作流重构。上游内容的版权归原作者所有。

## ustc-ai4science/academic-search

- 项目：https://github.com/ustc-ai4science/academic-search
- 许可证：MIT
- 相关技能：`academic-search`、`ai-computing-research`、`biomedical-evidence`
- 上游版本：`1.2.0`，适配基线提交 `3ae68445`
- 改动：压缩 Codex 入口、替换 Claude/CDP 专属假设、强化撤稿与版本核验、跨学科证据评价，以及研究证据到生活判断的转化边界。

## google-deepmind/science-skills

- 项目：https://github.com/google-deepmind/science-skills
- 许可证：Apache-2.0
- 相关技能：`biomedical-evidence`、`research-toolkit`
- 参考模块：PubMed、ClinicalTrials.gov 与 Europe PMC 数据库技能
- 改动：未复制其脚本；借鉴 grounding、限流、字段裁剪、试验注册和开放全文边界，使用 Python 标准库重新实现统一接口。

## xwmxcz/papers-skill

- 项目：https://github.com/xwmxcz/papers-skill
- 许可证：MIT
- 相关技能：`ai-computing-research`、`research-toolkit`
- 改动：借鉴 Semantic Scholar/arXiv 的轻量 CLI 与先元数据后全文流程；未复制依赖型脚本，改为多数据源统一证据契约。

## affaan-m/ECC

- 项目：https://github.com/affaan-m/ECC
- 许可证：MIT
- 相关技能：`context-budget`、`evidence-research`
- 改动：面向 Codex 重构触发范围、检索流程、上下文预算和中文入口。

## alirezarezvani/claude-skills

- 项目：https://github.com/alirezarezvani/claude-skills
- 许可证：MIT
- 相关技能：`financial-analyst`、`memory-curator`、`research-summarizer`、`stock-analysis`
- 改动：中文入口与界面元数据、Codex 适配、技能边界调整，以及部分工作流强化。

上游 MIT License 可在对应项目中查看。仓库内 `references/SKILL.en.md` 是为回滚和升级对照保留的英文入口备份，并不表示上游仓库的完整镜像。

## PPT 技能栈

- 参考项目：[Akxan/ppt-agent-skill](https://github.com/Akxan/ppt-agent-skill)、[CacinieP/ppt-skills](https://github.com/CacinieP/ppt-skills)，均在上游来源记录中标为 MIT。
- 相关技能：`technical-explainer-deck`、`deck-review`；其余演示技能组成按场景路由的本地工作流。
- 参考认知负荷、叙事结构、视觉层级、中文字体、文本溢出、对比度、可编辑性和版式契约等思想；没有导入这些项目的完整生成链路或模板库。
- 本次同步的是 2026-10-22 本地升级版本，保留入口、参考资料和审计脚本。

## 设计技能本地快照

- 来源集合：[dingdong905/design-skills](https://github.com/dingdong905/design-skills)，父仓库：[Stramony/design-skills](https://github.com/Stramony/design-skills)。
- 相关技能：`banner-design`、`brand`、`design`、`design-system`、`hallmark`、`ui-styling`、`ui-ux-pro-max`。
- 本次按本地安装内容同步，保留原有作者元数据、引用、数据文件和许可文件；不将其描述为全部由本仓库作者原创。
- `banner-design`、`design`、`design-system` 的入口声明 MIT，并保留 claudekit 作者元数据。
- `ui-styling` 的入口声明 MIT，随附 `LICENSE.txt` 为 Apache-2.0；保留两者，不声称已确定唯一适用许可。
- `brand`、`hallmark`、`ui-ux-pro-max` 的本地入口未提供统一明确的许可证声明；本仓库 MIT 声明不替代其原始权利和许可条件。
- 字体、图标及其他引用资源仍适用各自原始条款。

# 研究交接外壳 v1

这是对现有产物的轻量引用层，不替代证据账本、原生因子注册表、统计评估或执行批准。需要跨阶段交接或可复现归档时使用，普通问答无需建文件。

字段定义见 [handoff.schema.json](handoff.schema.json)。固定 schema 的 Python 校验器只用标准库，支持该 schema 用到的关键字；不是通用 JSON Schema 实现。新增 schema 特性必须同时增加校验与测试。

## 身份、时点与范围

- id/version 标识一份不可变产物；修改内容增加版本，--prior 可检查同一 ID/版本是否改写。此命令不创建持久注册表。
- as_of 是决策/研究截点；available_at 是所用输入整体最早实际可得时刻，二者不等于生成时间。created_at 另存产物生成时间；历史重放必须标 retrospective，不能声称当时已有这个想法或产物。
- 引用携带 ID/version/hash/reference/available_at。来源的首次公开、版本、采集等细分时间留在原账本。
- valid_until 由任务的时效规则决定并在 payload 的 freshness_basis 说明，不能编造长期有效期。消费时显式传 --at，超过期限就拒绝。
- versions 记录 data/code/model；不适用可为 null，未知须列 gaps。scope 写证券/主题范围、目标、未来交易日期限、适配条件和用途。
- status 和 eligibility 是待核验声明；无法取证时写 unknown 和 gaps，不以空串、0 或默认通过代替。原始 idea 可没有周期/公式；正式 factor 才要求命名、周期、定义、回看窗口。
- upstream/evidence/counterevidence 保留版本与哈希。相同 ID 的多版本不能被无版本引用歧义选中。对供应商和内容的真实性仍须另核验。

## 运行

相对于本技能目录：

```text
python -X utf8 -B scripts/validate_handoff.py <artifact.json> --at <timezone-aware-time> --purpose research
python -X utf8 -B scripts/validate_handoff.py <artifact.json> --at <timezone-aware-time> --purpose production --entity <security> --horizon <N> --reference-root <artifacts-directory>
```

--reference-root 可选：逐项核对本地引用文件的原始字节 SHA-256；拒绝链接和越界，不下载 URL。提供该参数后任何引用缺失或变化都失败。不提供则 refs_verified=false；字段齐全不证明文件存在。--prior 检查不可变性。

输出 valid 仅表示声明与所选消费范围符合契约；eligible_by_contract 仍不是可执行授权。execution_authorized 始终为 false：实际执行必须再查原生注册表和独立批准、当期输入、payload 原生验证器及模型证据。验证失败返回非零、status=unknown。可完整表达 unknown 的产物允许结构通过，但没有可用数值。

## 因子与概率

候选 factor 可无 registry_ref；影子/生产消费必须有原生引用、匹配状态、批准证据、已核验适配与完整输入。想法生成器不能自批。已有旧名称保留在原生 payload，通过映射适配，不批量重命名。

有效概率须绑定 data/code/model、因子集合哈希、label_version、标签规则与阈值、校准范围/周期和相应模型/验证/校准/依赖审查引用。校准可为已拟合方法，也可为经过可靠性验证的 identity_validated；rank、none 和主观投票都不能仅凭名字放行。这里检查绑定一致性，报告语义和统计可靠性另审。

二分类、三分类回报标签有明确互斥完备定义，和为1。独立重叠事件逐项定义，不要求和为1；不能混写成单一涨跌概率。未知概率必须为 null；不能悄悄删掉失效因子重分权重，仍使用原校准。

## 复用与边界

投研：想法/事实 → 原生规格或账本 → 原生验证报告 → 获准调用 → 已验证组合结果。
论文研究：既有 researchctl 结果 → 来源核验/领域判断 → research_summary；原论文元数据 schema 不变。

合成跨任务样例见 [交接示例](../example/handoff-demo.md)。它证明接口运转，不证明来源真实性、模型遵规或投资效果。逐技能内容版本与验收状态由仓库 scripts/skill_release.py 记录；安装后重载是否生效单独核验。

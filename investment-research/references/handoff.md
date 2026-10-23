# 交接规则

复用 research-toolkit 的 `references/handoff.schema.json` 与 `scripts/validate_handoff.py`。该共享工具为原产物加可验证外层，不替代事实账本、估值 v2 或项目因子注册表。缺工具时可给可读交接草稿，但不能声称已通过机器门禁。

外层保存不可变 id/version、as_of、available_at、created_at、research_mode、valid_until、生产技能内容指纹、数据/代码/模型版本、用途/股票池/条件/目标期限、状态与资格、证据/反证/缺口和有版本及指纹的上游引用。原格式留 payload，先运行原产物的专用校验器再运行外层校验；外层通过不证明 payload 的领域真实性。

消费时提供明确的当前时间、用途、实体和期限。过期、PIT 不满足、条件或输入缺失、未知状态均不能变成可用数值。无上一版本无法证明历史不可变；传 `--prior` 可阻止同一 ID/version 被覆盖。

概率载荷须包含模型/校准/验证/依赖关系审阅引用、校准方法与同版本模型及目标、完整输入和适用条件的核验。定义见共享契约。上下游内容指纹应从实际文件计算，不手填假哈希；校验器验证引用结构；可用 --reference-root 核对本地原始文件哈希，不自动下载或认证来源。输出 eligible_by_contract 不等于执行授权；execution_authorized 始终为 false。独立审批及校准质量仍需实际原始证据审阅。

最低使用形式：

```text
python -X utf8 -B <research-toolkit>/scripts/validate_handoff.py <handoff.json> --at <consumption-time> --purpose research --entity <entity> --horizon <trading-days>
```

任何源技能、脚本、schema、评分用例或上游变化，重新核对对应内容版本的验收报告。结构、单测、模型行为、平台原生实测分别记状态。安装/发布方法由源仓库 `docs/skill-release-contract.md` 维护，不把工程测试通过写成投资有效。

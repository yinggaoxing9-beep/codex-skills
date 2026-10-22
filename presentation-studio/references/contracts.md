# PPT 栈统一契约

只保留影响决策的字段。未知值写 `unknown`，不要为填满表格而猜测。

## deck-brief

下面的时长与页数是示例值，不是默认限制；未知时用 `unknown`，按任务和模式提议后再确定。

```yaml
objective: 观众看完后应发生的变化
audience: 角色、知识水平、主要顾虑
decision_or_action: 需要理解、批准、选择或执行的事项
mode: live | read | hybrid
duration_minutes: 20
slide_count: 12
language: zh-CN
depth: L0 | L1 | L2 | L3 | L4
evidence_cutoff: YYYY-MM-DD
source_scope: 用户资料、允许检索的来源
template: 路径或 none
brand_constraints: 字体、颜色、Logo、保密要求
editability: text | tables | charts | diagrams | full
speaker_support: none | notes | timing | q-and-a
```

## storyboard

每页只保留：`id`、`narrative_role`、`title`、`one_message`、`evidence_ids`、`visual_form`、`detail_destination`、`risk`。`detail_destination` 只能是 `slide`、`notes` 或 `appendix`。

管理/研究性论证按需要加两个可选字段：`action`（决策、下一实验或核验动作）与 `conditions`（结论成立/失效的条件）。`one_message` 写对证据的解释，`evidence_ids` 指向原始依据；这样可追溯“证据 → 解释 → 行动 → 成立条件”，无需每页都画四格。描述性架构页可不填行动；研究证据不足时，行动应是验证假设而非直接推广。

`hybrid` 的主路径仍使用现有 `narrative_role`；补充材料经 `detail_destination: appendix` 导向带页码的附录。若一页有多个细节去向，在对应要点内注明，不另造模式字段。具体安排见 [使用模式](authoring-modes.md)。

## evidence-ledger

每条证据包含：`id`、`claim`、`source`、`as_of`、`unit`、`scope`、`confidence`、`limitations`。精确数值、产品规格、价格、供应和兼容性结论必须能回到该账本。

对管理/研究性主张窄幅扩展两个可选字段：

- `kind: fact | estimate | inference | recommendation`：原始事实/观测、估计、推断、建议。估计的假设与算法、推断的替代解释和建议的成立条件写入已有 `limitations`。
- `based_on: [证据 id]`：估计、推断和建议回链到依据；依据缺失时写待核验，不补造事实。原始事实可省略。

页内用“实测/资料披露”“估算/预测”“据此推断”“建议/待批准”等措辞区分类型；不能仅靠颜色。会改变选择的限制需出现在主页面，完整方法再进附录。参考作品的视觉设计不构成其内容真实性的证据。

若建议依赖多个指标同时满足门槛，要核验同一测试/观察窗口的联合记录；各指标分别取中位数等汇总值后过线，不能直接证明同次联合达标。缺少记录时只支持候选筛选，把联合复验列为放行条件。

## asset-manifest

每个外部视觉素材记录：`id`、`slide`、`source_or_generator`、`license_or_permission`、`crop_intent`、`attribution_location`。

## qa-report

```yaml
- severity: P0 | P1 | P2 | P3
  slide: 7
  category: content | evidence | narrative | visual | accessibility | editability
  finding: 具体问题
  repair: 最小修复
  status: open | fixed | accepted
```

P0 阻止交付；P1 原则上修复；P2 可在不破坏模板时修复；P3 只做润色。


# 数据结构与运行

脚本只处理已研究、已核验的数据，不自动把任意实时榜换成用户要求的历史周。原始请求与计算文件应和报告分开保存。

## 目录

```text
issues/YYYY-MM-DD_YYYY-MM-DD/
  brief.md
  period.json
  evidence/               原始响应、固定版本、采集日志、SHA-256
  research/               分板块候选、身份映射、计算过程、缺口
  report-data.json         渲染的唯一输入
  assets/                 5张PNG和SVG
  模型热度周报_起日_止日.md
  models-and-sources.json  精确ID与公开来源对应表
  portable/               可转交MD与相对路径配图
  validation.json
  feishu/                 仅需飞书时：预备HTML、备份和完成证据
```

默认可沿用用户当前研究项目；此用户旧项目曾在 `D:/demo/openrouter-research`，存在时可参考历史冻结证据。Skill本身不依赖这个绝对路径，也不以旧稿替代新研究。

## 日期脚本

```text
python <skill>/scripts/period.py --start 2026-10-23 --end 2026-10-29
python <skill>/scripts/period.py --as-of 2026-11-01T00:30:00+08:00
python <skill>/scripts/period.py --start 2026-10-23 --end 2026-10-29 --timezone Asia/Shanghai
```

第二个例子以UTC完整日为默认：北京时间11/1凌晨时，UTC的10/31尚未结束，所以最新完整UTC日是10/30。不能仅用本地日期减一天就认定UTC的10/31已完整。

脚本返回 `period` 所需字段（将整个对象置于下列JSON的period）：start_date、end_date、timezone、days、start_inclusive、end_exclusive、UTC/北京对应边界、comparison前期边界。它不证明来源已经提供该窗口；研究仍要对齐实际数据。

## report-data.json

顶层：

- `period`：period.py返回对象。普通周报必须7日；用户明确指定非周区间才可加 `allow_nonweekly:true`。
- `intro`：本期完整日期、时区及主统计窗口。
- `readme`：各来源实际周期和限制概述，不能泛称全部是精确周值。
- `cards`：严格按 `usage,releases,capability,huggingface,community` 的5项。
- `outro`：可选简短收尾，不写虚假研究人数或未完成承诺。

每个card字段：

| 字段 | 内容 |
|---|---|
| key | 五个固定key之一；title/tag/颜色/表头由layout-contract自动注入 |
| source_label | 图片副标题实际来源，短写，不能伪称没用过的工具 |
| subtitle | 正文周期与实际统计/观测时点 |
| summaries | 恰好3条非空Markdown简析，支持加粗 |
| chart_notes | 至少3段实际口径说明，含来源、窗口、比较期/未计算、方法和限制；每段可带来源链接 |
| global / china | 各最多10行，真实排序；不足留空数组位置由渲染器补横线 |
| sources | id、label、url、retrieved_at（带时区时间），可加原件路径/hash/字段说明 |
| observation | 结构化实际来源口径，见下文；内容必须与chart_notes一致 |
| notes / extraMarkdown | 可选正文补充；不要重复整段图下注释。规格/厂商基准/情报等表用三级标题，避免多出第六个二级章节 |

每行：`entity_id,name,rank,a,b,sort_value,evidence_ids`，可选 `url,display_name,raw_*`。

- `entity_id` 精确版本/变体或仓库ID。同一侧不能重复，两侧允许重复。
- `rank` 为各自榜序的1起连续整数。能力默认沿用usage的entity_id/rank顺序。若用户要求另一种能力排序，明确改口径再适配默认验证，不私自改变。
- `a,b` 是最终显示字符串：用量为7日量/环比；新品为上线日期/7日量；能力为智力/编码与Agent；HF为30日下载/本周新增；GitHub为累计Stars/本周新增。
- `sort_value` 是精确非负整数或十进制整数字符串，用作排序核验：用量tokens、上新合并tokens、能力沿用usage tokens、HF downloads、GitHub stargazers_count。大整数用字符串避免精度丢失。
- 新品无量时 `sort_value:null,rank:null`，置于有量项之后。其他空列的展示为“—”，不要凭空加数值0。
- `evidence_ids` 引用本节sources.id，原始计算值用raw_*保留。仅验证ID可解析并不等于验证事实。
- `url` 指向真实模型/仓库，不指向搜索结果。图片可用display_name，正文name必须完整。

observation示例（日期只是演示，不得直接复用）：

```json
{
  "kind": "exact_period",
  "timezone": "UTC",
  "start": "2026-10-23T00:00:00Z",
  "end": "2026-10-30T00:00:00Z",
  "exact_report_period": true,
  "calculation": "total_prompt_tokens + total_completion_tokens",
  "comparison": {
    "mode": "source_reported",
    "start": "2026-10-16T00:00:00Z",
    "end": "2026-10-23T00:00:00Z",
    "calculation": "source.change * 100; prior base not independently acquired"
  }
}
```

kind可取exact_period、rolling_window、snapshot、snapshot_delta、source_date_buckets。

- snapshot要给实际 `as_of`，exact_report_period=false；无可比环比用 `comparison:{mode:"not_computed"}`。
- snapshot_delta给完整start/end、`timestamp_role`（例如archive_commit，不能冒充observed_at）、`repository_observation_time_known`布尔值，以及间隔秒数和偏离主边界说明。默认false，不称精确周值。
- source_date_buckets给真实date_labels和来源时区（不明确可写source-defined/unknown），exact_report_period=false，不伪造带UTC时区的日边界。
- source_reported与recomputed必须记录实际来源的相邻等长比较期。来源窗口不匹配主期时exact_report_period=false，说明差异，不改标签让校验通过。
- 缺全部源数据时不要构造观察元数据来通过渲染；先出明确缺口稿或获取可核验证据。

## 渲染与飞书准备

调用 `load_workspace_dependencies` 获取Node/Python路径和node_modules。不要因Windows的python应用商店别名失败而中止，使用已定位的运行时。

```text
node <skill>/scripts/validate-data.cjs <issue>/report-data.json
node <skill>/scripts/render.cjs --data <issue>/report-data.json --out <issue> --module-dir <node_modules>
node <skill>/scripts/prepare-feishu.mjs --md <issue>/模型热度周报_起日_止日.md --out <issue> --module-dir <node_modules> --target <用户授权URL>
```

render依赖sharp；prepare-feishu依赖marked。`--svg-only`仅供无sharp时的中间验证，不要声称已经交付PNG。可用 `MODEL_HEAT_NODE_MODULES` 代替模块目录参数。

验证会拦截：8日误作一周、周期/基期重叠或长度不同、错误章节顺序、每图少于3条简析、来源ID缺失、榜序逆序、数字省略、能力行序偏离用量、快照假称精确周期。仍需人工查原始数值、源定义与图文语义，不能把PASS说成事实全部正确。

产物主MD用绝对图片路径方便当前环境打开；portable内用相对路径便于转交，并附models-and-sources.json保留模型精确ID和公开来源对应关系。只压缩portable目录，不混入账号信息、网页备份或整个历史研究目录。5张图都目视检查后交付。

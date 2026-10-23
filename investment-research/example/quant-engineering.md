# 量化工程接口适配核验

核验日期：2026-10-22。只读 checkout：`D:/project/quant-engineering/dingdong-dev/quant-engineering`，master，HEAD `8eb782a0de647490c6a6a276fce3d7405c2efc6f`；有既有未提交业务修改。目录与分支须重新确认，本文不是执行授权。

## 已有接口与边界

- `stock/research/factors/spec.py`：FactorSpec 有 factor_id/version/family/expression/inputs/lookback_trading_days/direction/supported_horizons/hypothesis/available_at 等；key 由原 factor_id 与 version 组成。ResearchProfile 将 horizon_trading_days、label_version、universe_version、preprocessing_version、execution_lag_trading_days、cost_model_version 固定在 profile 内。
- FactorSpec 的 factor_id 正则只接受小写 `^[a-z0-9][a-z0-9_.-]*$`，不能直接注册 `Alpha_<N>Day_...` 新规范名。available_at 的原生值如 next_open 是规则而非 ISO 时间戳，外层另存实际可得时刻。当前只能生成新规范候选和待适配说明；不自动改名旧 ID，不称已接通注册。
- `stock/research/factors/registry.py`：FactorRegistry.current_state(factor_key, profile_id) 读状态；transition 的 ACTIVE 门禁要求 promotion-ready model ablation 及 human 审批。write_active_manifest(profile_id, include_states=(ACTIVE,)) 会写文件，本轮没有执行。
- `stock/cli/factor_research.py`：真实参数含 --data、--registry-dir、--output、--horizon（仅 1/5/20）、--profile-id、--validation-periods、--signal-step、--start-date、--end-date、--codes、--register-only、--ablation-folds、--execution-rank-buffer、--execution-max-replacements、--execution-min-holding-days。10 日等新期限未接通该 CLI；不忽略或改填为 5 日。
- `stock/cli/high_alert_backtest.py`：--data、--output、--sample-size、--seed、--split-date、--parent-run、--revision-reason。复用既有回测，输出目录需新建；只有用户授权且资源范围明确才运行。既有技能 alpha-hypothesis-research 的项目案例提供更细事件研究边界。
- `stock/research/alpha_combiner.py`：AlphaCombiner.combine(factor_frame, *, as_of=None, prev_returns=None) 输出 alpha Series；equal_weight_rank、ir_weighted、lasso 是截面评分。combine 接受任意 frame，不替消费者核查 registry。调用层必须先核对因子/期限/用途/条件；分数不可改名概率。
- `stock/core/predictor.py` 的 _calibrate_probabilities：有 rank 到 0.05..0.95 的分位映射；none 分支只 clip。两者都不能凭名称或配置证明已做目标相关的校准。`stock/cli/forecast.py` 使用 probability_calibration="none"；本轮没有读取实际训练/校准产物，短中长期校准涨跌概率能力为 unknown。
- forecast CLI 包含 --history-dir、--update-dir、--spot-file、--as-of、--forecast-date、--universe-size、--train-years、--validation-days、--top-n、--output-dir。它会训练/写产物，不能当只读能力探针。参数从源码核对；没有运行业务入口。

## 可接和待接

已可接：只读 native ID/profile/生命周期与评估产物，引用已有 manifest/ledger/hash，把证据转成共享交接外层；研究输出区分候选与获准使用。

待接：新正式命名与注册表兼容、用途门禁的具体项目字段映射、任意期限 CLI、独立校准产物及完整标签/版本/覆盖验证。缺口未补齐时概率 null，不调用不适用或未获准因子。交接 schema 不自行创造原生批准。

`docs/alpha-researcher-design.md` 要求 enabled=false；本轮仅核验设计，未部署、启动调度、调用研究服务或激活生产。项目当前进度仍保留在项目，本文只作接口核验案例。

## 使用示例

“用 investment-research 把一个量价猜想写为候选，先不回测”：只定义可计算输入、待检验期限与缺口。
“读取指定 registry 与报告，解释某股 5/20 日因子的用途和反证”：先只读核对实际状态与有效性；校准证据缺失时分期限输出 unknown。
这些句子不授权回测、写 registry 或持续任务。

来源：上述源码及仓库 AGENTS.md、docs/alpha-researcher-design.md。本轮未改动项目实现、跑历史回测或证明盈利。

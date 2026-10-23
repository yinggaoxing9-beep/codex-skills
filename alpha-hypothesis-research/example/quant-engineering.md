# 量化工程：高位预警研究适配记录

本记录仅适用于对应代码库，核验日期为2026-10-15。它记录源码接口与测试，不提供盈利背书，也不继承运行授权。

源码checkout：`D:/project/quant-engineering/dingdong-dev/quant-engineering`。先核验Git根目录、当前分支、状态和仓库AGENTS；同名其他checkout不自动同步或覆盖。

## 当前组件

- `stock/research/high_alert_signals.py`：`compute_signals(panel, config=None, *, trading_calendar=None)`返回code/date、eligible和H01至H30(nullable boolean)；`get_signal_catalog(available_columns=None)`给完整目录及缺口。
- 目前日线实现H01至H11和H14，其余18条缺分钟/PIT适配。H14使用日线开收盘拆隔夜/日内；H12需要利好事件可得时间，不能替换为裸跳空；H09是OHLCV活动价代理，不能称真实成本。
- `stock/research/high_alert_backtest.py`：`forward_outcomes`、`select_events`、`summarize_signal`、`classify_results`；独立事件筛选，没有连续账户策略净值。
- `stock/cli/high_alert_backtest.py`：本地Parquet股票档案入口，输出目录必须新建，保存定义/配置/manifest/各周期事件/汇总/HTML与DRAFT注册表；另存`observed_calendar.csv`与`archive_codes.json`。运行前冻结7个依赖代码文件及所选输入文件的哈希，结束时再次核对，不接受运行中输入或代码变动。
- `stock/research/factors/spec.py`和`registry.py`：不可变因子定义、研究profile、trial family和追加生命周期事件；按源码既有执行验证与准入要求继续研究。

## 检查与调用

在上述仓库根目录先看当前CLI：

```text
python -X utf8 -B -m stock.cli.high_alert_backtest --help
python -X utf8 -B -m scripts.verify fast
python -X utf8 -B -m unittest tests.stock_tests.test_high_alert_signals tests.stock_tests.test_high_alert_backtest tests.stock_tests.test_high_alert_cli -v
```

下列为带占位参数的调用形状；只在任务已经授权回测并明确资源范围后填入真实路径，不能原样执行：

```text
python -X utf8 -B -m stock.cli.high_alert_backtest --data <partitioned-parquet-root> --output <new-output-directory> --sample-size <declared-size> --seed <declared-seed> --split-date <declared-date>
```

已有运行结果被看到后重新运行时，成对指定`--parent-run <prior-run>`与`--revision-reason <reason>`，保存父运行及修改原因的研究谱系；父运行目录须含`manifest.json`。初次运行不填这两个参数。

CLI当前要求分区档案。输出路径不能已有，以免覆盖先前试验。实际数据集、数据截至日、复权和历史股票池能力从文件与manifest核验；不从本记录推断。

## 本轮参数与边界

2026-10-15初轮预声明30条猜想、5/10/20交易日期限，共90项检验预算；12条可用不把预算缩减成赢家数量。这是当前实验预算示范，不是今后固定要求。高位筛选、冷却、命中阈值、样本量门槛和HAC/BH方法也均属于该版本，其他研究按目标重新声明。

本轮使用固定随机历史股票样本并将已知持仓单独展示；60%/40%时间切分仍是回顾性时间留出；模型现代知识、已知持仓和历史高点经历均可能参与猜想形成，故本轮仅属历史探索，后40%不能称全流程独立样本外。对照尚未匹配行业/市值/波动率。观察日期并集不是已独立核验的交易所日历；源停牌行清理及近似涨跌停标志限制成交推断。事件净避险指标条件于可评分和执行代理，不能称账户利润。

交付版单测核验：2026-10-15 `test_high_alert_signals`、`test_high_alert_backtest`、`test_high_alert_cli`三个文件共36项通过；`scripts.verify fast` 13项通过。它们只证明工程行为。当前完整研究结果须读本项目的产物与任务记录，不由本技能保存或刷新。

来源：本地上述源码、`docs/governance/contracts.md`、`docs/governance/validation.md`、`.tasks/stock/2026-10-15-high-alert-backtest.md`。未复制实现代码，不涉及未读取文章的归因。

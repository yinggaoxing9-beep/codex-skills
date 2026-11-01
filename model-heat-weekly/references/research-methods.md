# 来源和统计口径

## 身份与证据

建立映射：OpenRouter id/canonical/standard-free-batch、机构及归属证据、权重版本/仓库/开放日/许可、HF repo_id、GitHub数值repo_id、AA模型ID和推理配置。不能仅按名字模糊匹配；别名、许可和公开状态每期核对。

中国栏默认中国机构官方公开权重。基础模型血统不代替发布机构归属；第三方量化/微调不是官方原模型。公开权重不等于严格开源；API可用、开放承诺或目录open-weight简介不能单独证明权重已公开。期后当前状态不能倒填成期内状态。

每次采集保存URL、参数、UTC/北京时间、HTTP状态、原始文件与SHA-256、来源截至日/版本/提交、实际窗口。每个数值通过evidence_id追到原始文件/字段。原始证据只追加，修正另存；401、空响应、未上榜都不作0。

以下是已用入口，不保证永久稳定；每期核验官方方法、结构和可访问性。

## 1. OpenRouter用量

- 排名页 `https://openrouter.ai/rankings?view=week`；已用公开结果 `https://openrouter.ai/api/frontend/v1/rankings/models?view=week`；目录 `https://openrouter.ai/api/v1/models?output_modalities=all`；Data API方法 `https://openrouter.ai/docs/cookbook/administration/data-api`。不混淆不同接口覆盖，前端接口无长期稳定承诺。
- 收集返回集/分页中的精确版本与变体、输入/输出tokens、change、date、rank。此前官方周榜按最新完整UTC日桶截止的连续7天，比较此前连续7天；每期核对，不能从采集日猜截至日。
- 用量=prompt+completion。全球/中国各自降序取10，继续扫描全球第10之后补足中国候选，不能仅从全球前十筛右榜。默认不同变体分开，不合家族。
- 环比=(本期−基期)/基期×100%。两期同口径原数齐全才写“自行复算”；取change×100%写“平台返回值”，区别已知基期窗口与未独立取得基数。基期0/未知无可比百分比，“未见榜”不等于基期0。
- 按当期方法注明私密请求等排除规则。token量不是用户数、收入或能力。
- 中国占比写分子分母：“全球Top10内中国项tokens/全球Top10合计”不同于“中国榜Top10/全球榜Top10”，都不自动是全平台份额。
- 目标历史周≠当前周时查冻结历史或逐日数据。当前榜不能改日期冒充历史周，接口不可用时不猜测、不绕权限。

## 2. 本周上新

- 按Models API created和目标边界筛通用文本/图文生成模型。厂商发布、目录收录、权重开放分开记录；“上线”解释为目录日期，显示北京时间时注明筛选时区。
- 保存全模态候选和排除原因，明确纯图像/语音/转录/嵌入/decisions/别名处理。快照无已删模型时说明覆盖限制。
- 默认同canonical的standard/free/batch相加，再按本期7日量降序；明确与第一节按变体的差异。区分入口数、目录版本数、底层模型组数。
- 用量窗口与第一节一致，不是“上线后另累计7天”。入口不在当前目录而有用量时保留canonical映射证据。无可比量的候选在已知项后列出，排名/值为横线，不虚构数值顺序。
- 正文补价格（美元/百万tokens）、上下文、模态/功能和官方链接，分别列长上下文、缓存、batch等费率。
- 中国无合格新品可为空；开放承诺不算已经开放。旧目录模型本周开权重入情报，不补作目录新品。

## 3. 能力对照

- 采用第一节精确版本和行序；“最高”限定热门已匹配样本，不声称全行业最强。
- 一手入口 `https://artificialanalysis.ai/leaderboards/models`、精确模型页及 `https://artificialanalysis.ai/methodology/intelligence-benchmarking`；OpenRouter转载值单独标明。厂商模型卡/论文自报成绩另表。
- 智力=Artificial Analysis Intelligence Index。具体子测试、版本、权重、量表查当期方法，不在Skill写死版本，不跨版本做涨跌。分数非人的IQ/正确率，58和32不能解释为强81%。
- 记录effort、fallback、预算、联网/采样配置和评测日；未披露编码/Agent索引版本如实写，不与智力混加。第三方AA身份不因模板“官方基准”改变。
- 当前分数是快照，非周累计，不能回填期末历史值。

## 4. Hugging Face

- 用Hub API、官方组织和模型卡核验字段/发布者/权重/许可；计数说明 `https://huggingface.co/docs/hub/models-download-stats`。一仓一项，不合家族，排除第三方量化/微调/合并及范围外专用模型。
- 30日下载按同观测时点downloads排序，非本周下载。指定文件GET/HEAD计数非完整权重下载、独立用户或推理量。
- 本周新增优先精确周边界downloadsAllTime差或可信日数之和；**不能相减两次滚动30日downloads表示周新增**。
- 历史候选 `https://huggingface.co/datasets/cfahlgren1/hub-stats`。固定提交/字段/文件，声明第三方维护，非HF官方历史接口，不假设每个边界都有快照。
- 缺精确边界时可用接近7天的真实累计快照差参考。写两完整时点、实际间隔、端点偏移、逐仓采样时刻是否已知；表头保留“本周新增”，图下明确“快照差参考，非本期精确新增”。仅长度约7天不证明边界对齐，不按比例缩放或改标日期。
- 累计计数可追补/修订，负差不强制归零，先查验再保留修订/不可比状态；无基线非0，不承诺下期必可得。

## 5. GitHub与情报

- 累计Stars用仓库元数据API，候选是官方模型发布仓/家族专属参考推理仓，排除通用工具。保存repo_id防重命名误配，按累计Stars降序，各榜独立。Stars不可转移给新checkpoint，也非模型使用量。
- 本周新增首选同repo_id精确期末累计−期初累计，代表净增（新增减取消）。
- 无边界快照而用官方星标历史日桶时，先查当期日期映射、时区、取消处理。入口 `https://docs.github.com/en/rest/activity/starring`；工程说明 `https://github.blog/engineering/architecture-optimization/from-2500-requests-to-24-rebuilding-star-history-without-the-stargazers/`。
- 若历史计数仅保留查询时未取消Star，解释为“所选日期内新点Star且查询时未取消的记录之和”，非累计净增或所有点击次数。来源未承诺日桶时区则非精确UTC周；逐日存证，不能误算8桶或把Unix时间戳当UTC日边界保证。
- 表头仍“本周新增”，含义图下解释，不改为“加星留存”。期末累计/精确净增不可得保持缺失；可另列真实观察时刻的近似快照差，不混主列、不改日期。报告后一天取得的累计值不称期末收盘。
- 情报优先本期模型发布、权重/许可、重要能力/价格/API变化的官方公告。区分事件与文章发布日期，时区不明注明；无关营销案例不凑数。权重初始提交不单独证明当时公开；第三方搜索/社媒代理不替代官方内容证据。

# 本地工具

入口是本 Skill 的 scripts/find_media.py。下文 <skill>、<work>、<input> 由调用方替换为绝对路径；Windows 中文/空格路径整体加引号。使用独立任务目录，不向仓库存素材/缓存。输出 JSON，本地执行失败 exit 2、process_status=failed。trace 全部帧查询失败仍先写报告，再 exit 2；部分成功为 partial/exit 0，空匹配为成功查询。过程失败不代表候选错误。下列子命令均接在 python -B "<skill>/scripts/find_media.py" 后。输入文件不覆盖，输出报告与目录必须新建。

## 探测与局部依赖

python -B "<skill>/scripts/find_media.py" doctor

文字/游戏模式仅需 Codex 当前检索工具；subtitle/report 仅标准库。图片处理需 Pillow，视频需 FFmpeg。优先现有 ffmpeg/ffprobe，也可 --ffmpeg 或 FIND_MEDIA_FFMPEG；可发现 imageio-ffmpeg。本版由 FFmpeg demuxer 取时长，不强制 ffprobe。

按需 python -m venv "<skill>/.venv"，再用其 Python 执行 pip install -r "<skill>/requirements-media.txt"；已有 FFmpeg 可只装 Pillow。不会自动下载 OCR/ASR 模型。动漫向量需 Node >=24，在 Skill 根目录执行 npm.cmd ci --no-audit --no-fund（Linux 用 npm ci），按锁文件安装局部 sharp/trace.moe-id，不动全局 MCP。缺安装权限就降级文字/人工对照并说明缺口，不要求额外 LLM API Key。

TRACE_MOE_KEY 可选，仅读环境变量、发送请求头，不打印值。密钥不写命令、仓库、案例或日志。

## 视频与派生图

prepare "<input>" --out "<work>/frames" --start 0 --max-duration 120 --max-frames 24 --gap 5 --threshold 0.3 --timeout 90

FFmpeg scene score 检测切镜，无需 PySceneDetect。镜头是抽样单位，不等于语义段。先每镜头一帧，再第二帧与周期帧；无切镜仍抽帧。过滤近黑、低细节/严重模糊及同镜头完全重复，保留过滤记录。静态低细节动画可能误过滤，检查后调 --blur-threshold（默认 2 为启发式）；短镜头/渐变可能漏检，应人工查看时间轴、补指定范围，不能声称语义全覆盖。

manifest.json 含输入指纹、输入时钟、镜头、帧、过滤/失败、检测降级和预算。analyzed_input_range 仅为切镜分析范围；lookup_coverage 初始为空，代理必须关联 frame id 与 trace 结果，再分别记录采样、查询、核验覆盖。无可用帧的镜头 unprocessed，有代表帧也非全部画面已识别。预算不足标未处理，优先用户关心范围。

每个进程有超时，总工作量受时长/帧数限制。容器 seek 存在误差，精确定位前核验。脚本只处理本地文件，URL 由 Codex 连接器读线索，不负责通用视频下载。GIF 用 prepare；静态图片直接 trace。

transform "<image>" --out "<work>/mirror.png" --mirror
transform "<image>" --out "<work>/crop.png" --crop LEFT TOP RIGHT BOTTOM
transform "<image>" --out "<work>/trim.png" --black-border

副本与 .provenance.json 分开保存；crop 坐标基于 EXIF 方向修正后的图。black-border 仅保守裁近黑常量边界，人工确认视频区域；不默认多变换，每次查服务均计预算。

## 动漫查询

trace "<image1>" "<image2>" --out "<work>/trace.json" --cache "<work>/cache" --budget 6 --retries 1 --timeout 30

本地 sharp 修方向、缩至 320 内、RGB → 官方 ColorLayout.extract → JSON vector 发 trace.moe，无原图上传。候选保留原始分数、episode 原类型、at、from/to、预览、处理/库版本，始终 unverified，代理须视觉核验。

串行请求，同任务共用 cache 锁；不同目录也不要并行调用（免费共享 IP 通常并发 1）。动态 /me 与限流头记录额度；402 停止并记录 quota_or_concurrency，不当无匹配。429/503/504 最多 --retries 次（0–2），每次最多等 10 秒；重试也占搜索 budget。本地缓存读取不受服务额度或搜索 budget 限制。缓存成功结果最长 24h，预览通常 300 秒失效，缓存标过期风险。新预览才 --refresh，需耗额度。网络/鉴权/服务失败单列，不改变候选真假。预览用实际连接器/受控本地读取；被拒或过期明确未看过。

## 字幕与指定原片范围

subtitle "<subtitle.srt>" --query "<dialogue>" --out "<work>/dialogue.json" --version "<subtitle version>"

支持 SRT/VTT/ASS/SSA（ASS 读 Events Format）；UTF-8-BOM 默认，旧编码用 --encoding gb18030。去标签、Unicode NFKC、去标点空格的子串搜索，重复台词全留，无命中不等于作品无台词。字幕时间与视频时间不同，offset_to_video=null 代表未核偏移；缺版本不能确认原片时间。实际对白/匹配版本比对后才校正，不假定不同剪辑统一偏移。

compare "<query frame>" --source "<candidate episode>" --out "<work>/compare" --start 260 --end 290 --step 1 --max-frames 30

只在用户提供原片的指定范围抽样，Pillow 低分辨率 RGB 像素距离排序。低分也需看图；调色、水印、裁剪会降召回。这是朴素局部候选工具，无深度索引/整库搜索/变速区间推断，保留源指纹、采样时间和精度。多个锚点仍需真实连续原片核验。

report "<result.json>" --out "<work>/report.md"

代理结合证据按结果契约填 JSON，再校验/生成中文表格；不会自动将候选升级为结论。

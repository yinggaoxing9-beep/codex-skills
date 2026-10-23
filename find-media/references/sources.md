# 来源、许可、版本与数据流

核验日期 2026-10-21；服务条款和覆盖变化时重新核验。客户端开源不授予底层影视/游戏素材版权或完整片库。本 Skill 没复制第三方项目代码，薄适配器调用公开库接口。

实际采用：
- [trace.moe-id](https://github.com/soruly/trace.moe-id) 2.0.0，MIT，本地 ColorLayout，锁文件含完整性。
- [sharp](https://sharp.pixelplumbing.com/) 0.35.4，Apache-2.0；传递依赖 libvips 等许可保留于安装包。
- [Pillow](https://github.com/python-pillow/Pillow/blob/main/LICENSE) >=11.3,<13，HPND/Pillow 许可，本地图像派生与像素距离；实测版本在案例。
- [FFmpeg](https://ffmpeg.org/legal.html)，LGPL/GPL 依构建变化，抽帧/切镜；二进制版本进 manifest。
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) 0.6.0，包装层 BSD-2-Clause，所附 FFmpeg 另计许可；缺 ffmpeg 时可选。
- [trace.moe API 协议](https://github.com/soruly/trace.moe-api/blob/master/docs/docs.md)、[额度](https://github.com/soruly/trace.moe-api/blob/master/docs/limits.md)、[条款](https://github.com/soruly/trace.moe-api/blob/master/docs/terms.md)、[覆盖](https://trace.moe/about)。服务端代码 MIT 与在线服务、片库权限分开。免费可无密钥用，动态 /me 串行；在线条款禁止未经批准的商业使用（含转售），无 SLA，不能因客户端 MIT 推定服务许可。
- [官方 MCP](https://github.com/soruly/trace.moe-mcp) MIT、Node >=24。本版选官方库薄 CLI，无需全局配置。

数据流：本地输入 → 任务目录有限抽帧/派生 → 本地 sharp/trace.moe-id → HTTPS 仅发 33 维特征 → 接收候选/元数据/短期预览 URL，预览只作核验。/me 的网络标识不写公开报告；密钥仅请求头。文字检索只发送必要查询词；额外云搜图/OCR/ASR 遵循入口授权。缓存与派生图留用户任务目录，不入仓库。

按需来源/未采用方案：
- [TMDB](https://developer.themoviedb.org/docs/finding-data)、[watch providers](https://developer.themoviedb.org/reference/movie-watch-providers)：文本/外部 ID，不是识图；需凭据、按地区、JustWatch attribution，公开页可降级。
- [IGDB](https://api-docs.igdb.com/)：作品/别名/平台/截图；需 Twitch 凭据，无则公开查询。[Python 客户端](https://github.com/twitchtv/igdb-api-python) MIT，未依赖。
- [MobyGames J2ME](https://www.mobygames.com/platform/j2me/)：平台入口之一，资料/图片权限与 API 条款另计，不能据此假定手机系统或完整覆盖。
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) BSD-3-Clause，Content/AdaptiveDetector 可替换，未安装；本版 FFmpeg。
- [RapidOCR](https://github.com/RapidAI/RapidOCR) Apache-2.0 代码，模型须核 MODEL_LICENSES.md，未安装/下载。
- [PicImageSearch](https://github.com/kitUIN/PicImageSearch) MIT，未采用；各服务上传/密钥/条款各异，不广播。SauceNAO 条款/额度未核，不作必需入口。
- [Shotit](https://github.com/shotit/shotit) Apache-2.0，先导原片建索引/多服务，第一版未部署。
- [RomM](https://github.com/rommapp/romm) 是已有 ROM 库管理，不是模糊记忆检索，本版未引入。
- moviname-backend 未核到明确许可，不复制代码；视觉猜标题加元数据不证明原片匹配。

具体实测来源和失败登记于 [案例](../example/index.json)。测试生成画面无第三方素材；官方 API 文档演示图只在临时目录核验，不随技能发布。

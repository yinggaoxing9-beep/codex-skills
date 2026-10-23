# 结果契约

短任务可只交中文结论和来源；保存、多段或续做时用 JSON。scripts/contract.py 验证跨字段一致性，不能代替真实证据审核。所有时间秒；日期 ISO 格式。

顶层 schema_version=1，task_type=anime/live_action/game/plot；inputs 为来源、URL/本地路径、可取得的 SHA256、输入类型/读取状态，不可读 URL 不编指纹。clues 可选，保存明确/大概/不确定和修正。segments 每个输入段/候选独立。process 数组保留 provider/status/checked_at/原因/输入关联/尝试预算。coverage 记录总长、分析范围、镜头数、选帧/查询/核验数、未处理、停止原因；文字任务记录已查范围。unresolved/next_steps 为字符串数组。

segment 字段：
- id、input_range（视频 [start,end] 或 null）、work（name/aliases/ids/platform/year/version）、season、episode（原类型可 null/字符串/范围）。
- status：unresolved、title_only、episode_only、verified_anchor、verified_interval；episode_only 表示作品及集数确认而时间未确认。
- confirmation：title/episode/time 三个独立 unverified/confirmed/rejected。
- evidence 数组：唯一 id、source（URL/本地文件与指纹）、checked_at、observation；按需有 input_frame/subtitle_cue/processing/provider_raw/provider_similarity/preview/preview_read_status。
- confirmation_evidence：confirmed 层到 evidence id 数组的映射；搜索摘要不等于已看原片。
- anchors：input_time/source_time/evidence_id/reviewed=true，仅实际对应点经对照后填写。
- source_interval：仅 verified_interval 用源 [start,end]；continuity 必须含 reviewed_source_span=true 和 evidence_id，记录实际检查中间原片连续性的证据，不能靠两个点外推。
- time_basis：version（数据库文件名或用户原片指纹/版本）、clock（数据库/解码/字幕时钟）、precision（采样精度或未知）、error（已证误差或 null）；字幕偏移未证不标原片时间确认。
- clue_matches/clue_conflicts/clue_unknowns 为字符串数组；excluded=true 必须有 exclusion_reason，并延续至后续回合。
- watch_entries：url/kind（work_page/play_page/store_page/reference_page）/region（unknown 可用）/checked_at/availability（verified_available/unknown/unavailable），必要时 attribution；可访问网页不证明登录后可播。

process 状态如 ok/no_match/network_or_timeout/credentials_error/quota_or_concurrency/budget_exhausted/unreadable/link_only，均非候选真伪。原始响应按需在任务目录单独保存并用指纹引用，避免报告膨胀。不得平均分数或伪造概率；预览过期/被拒与来源不匹配分开。未处理段必须出现，不能只展示命中段。

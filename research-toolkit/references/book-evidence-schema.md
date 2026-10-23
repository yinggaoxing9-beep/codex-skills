# 图书书目与正文证据契约（v1）

bookctl 输出独立的 schema_version=book-discovery/1 envelope，不修改 researchctl 现有论文契约。

## 检索输出

顶层：schema_version、operation、query、provider、fetched_at、status、records、warnings。

status：ok（成功，允许空结果）、not_found（该来源未找到指定版本）、inconsistent（标识符冲突）、error（请求/协议失败）。空结果不表示全网不存在，error 不包装为正常空结果。

每条 record：
- record_type：book_work 或 book_edition。
- title、authors、author_keys、by_statement：来源提供的题名/作者；缺名字时保留 author_keys，不补造。作品级作者列表可能聚合不同版本的参与者，不能直接当作指定版本作者名单。
- identifiers：openlibrary_work/openlibrary_edition、isbn_10/isbn_13；ISBN 仅在具体版本填写。
- first_publish_year：作品首版年；publish_date、publishers、edition_name、physical_format、number_of_pages、languages、contributors：具体版本信息，不相互填补。physical_format 仍是目录声明，不证明下载文件类型。
- edition_candidates：每项保留自己的 title、edition key、language、provider_access，lookup 后再引用版本。
- source_url、provenance：记录/请求 URL，不含凭据。
- access：provider_access 为目录声明；observed=metadata_only，full_text_verified=false。借阅、预览、public 标记不自动升级为正文可用。
- verification：candidate、record_retrieved、identifier_match、identifier_unconfirmed、identifier_mismatch；只指目录/标识符，不验证正文或结论。

ISBN-10 与 978 ISBN-13 可规范化比较；979 不能转 ISBN-10。校验位有效不证明已分配或匹配。

## 内容阶段追加

由实际获取/阅读流程填写，不由元数据脚本生成：
- content_scope：metadata_only / preview / excerpt / full_text，表示可访问范围。
- inspected_ranges：实际核验章节与位置；可访问 full_text 不意味全书读过。
- locator：chapter、printed_page、pdf_page_index（1 起算）或 EPUB 节标题/段落。
- acquisition：获取 URL、时间、格式；保存后填 path、sha256。
- rights_status：明确许可/公版依据/受限/未知；镜像存在不证明许可。
- claims：原文支持的主张、短引文或转述、局限与反证；metadata_only 时为空。
- source_identity：跨镜像去重的作品/版本身份；不同译本版次保留关联，不强行合并。

跨阶段外壳使用同技能的 handoff-contract.md 引用原产物，不把图书 envelope 伪装成论文 records。专业质量评估由上层技能完成。

# 目录命中不等于目标版本

类型：observed。核验日期：2026-10-22。使用公开 Open Library API，只读查询，无账户或正文下载。

## 观察

1. 按 Designing Data-Intensive Applications 和 Martin Kleppmann 搜索，返回作品 OL19293745W，版本候选 OL59752345M。
2. 查询该版本，出版者为 Upfront Books / Audible，日期 Feb 05, 2021，ISBN 数组为空。出版方包含 Audible 提示可能为音频，但 physical_format 尚未核实；检索排序没有替调用方确认电子书载体。
3. 明确查询 ISBN 9781449373320 后返回版本 OL26780701M，出版者 O'Reilly Media，日期 Apr 02, 2017，ISBN-10 为 1449373321，状态 identifier_match。
4. 按“三体”与“刘慈欣”、语言 chi 搜索，返回作品 OL17267881W 和中文版本 OL26951073M。作品 author_name 含四名参与者，不能全部当作该中文版本的原著作者。
5. 输出始终保留 metadata_only 与 full_text_verified=false；borrowable 等目录声明不升级为已取得正文。

## 结果与边界

确认公共 API 的题名/作者搜索、中文语言筛选、版本查询、ISBN 核验路径当时可用。未测试全文获取、Z-Library、中文整体覆盖或模型盲评。

人工在线探针曾直接取候选的第一个 ISBN，因载体待核验版本无 ISBN 而失败；生产 CLI 的缺失标识符路径有离线测试，返回 identifier_unconfirmed。后续流程应保留未知，不把工作级 ISBN 拼给候选版本。

## 来源

- [技术书作品](https://openlibrary.org/works/OL19293745W)
- [载体待核验版本记录](https://openlibrary.org/books/OL59752345M)
- [明确 ISBN 对应版本](https://openlibrary.org/isbn/9781449373320)
- [中文书作品](https://openlibrary.org/works/OL17267881W)
- [中文版本候选](https://openlibrary.org/books/OL26951073M)

历史目录会变化；重用时重新核验，不继承下载授权或断言当前可访问。

后续一次版本查询出现网络失败，未能进一步核实载体字段；先前成功查询不证明接口持续稳定。

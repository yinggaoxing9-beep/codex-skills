# 同一交接契约的跨任务演示

这是合成工程样例，不是真实论文或投资结论。金融侧读取已有 evidence-driven-valuation 的 v2 合成载荷，先运行 fundamental-signal-intake 原账本校验；论文侧使用空 records 和明确 warning 的研究 envelope。两侧保持 native 载荷原样，添加同一交接外层，检查本地引用哈希、时间与 unknown 状态。

在源仓库根执行，输出目录必须新建且位于源码之外：

```text
python -X utf8 -B research-toolkit/example/handoff-demo.py --source-root . --output <new-output-directory>
python -X utf8 -B research-toolkit/scripts/validate_handoff.py <new-output-directory>/research-handoff.json --at <receipt-at> --reference-root <new-output-directory>
```

生成器使用实际完整 research-toolkit 目录指纹和文件原始字节指纹，不手填哈希。available_at 为合成原输入时点，created_at 是实际生成时点，research_mode=retrospective；演示有效期仅为生成后30分钟，不能作为业务时效默认。复跑生成新目录；过期后校验失败是预期。

输出 financial-handoff.json、research-handoff.json、原始 v2/paper 文件与 receipt。原始 payload 验证、外层验证和模型语义是独立层次；本演示只证明接口可复用。修改被引用文件后再次校验必须失败。模型版本 null、结果 unknown 和原因会保留，不填0。

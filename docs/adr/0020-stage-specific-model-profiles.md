# 管理员配置阶段模型 Profile

V2 通过统一 `ModelGateway` 提供严格结构化生成、文本流式输出和用量记录能力，Graph 和领域模块不得写死 Provider 或模型名称。管理员按意图解析、阶段 Author、专项 Reviewer 和测试设计等职责配置模型 Profile，首发可以让多个 Profile 指向同一模型但保留独立参数；普通项目用户不能选择模型。

模型调用审计不建立独立历史表，而是随本次助手消息保存在管理员可见的 `diagnostics` JSONB：按节点记录实际 Provider、模型、模型 Profile、参数摘要、Prompt Hash、Schema Hash、Token、耗时、重试、成本和结果。完整 Prompt、项目上下文和模型原始输出不重复写入诊断记录；普通用户只查看消息中的过程时间线，管理员才可查看诊断数据。

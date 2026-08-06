# Git 历史与当前产物投影

项目批准产物使用稳定文件路径，历史版本由 Git Commit 管理，不在文件名中携带版本号，也不在 PostgreSQL 重建完整产物版本库。PostgreSQL 的 `artifact` 只保存当前批准产物、内容 JSONB 查询缓存、内容哈希、稳定 Git 路径和当前 commit SHA；`artifact_draft` 保存当前候选内容。Run 被用户中断时不删除已经写入的草稿，所属阶段继续保持 `BUILDING`；下一 Run 由 AI PM 根据新消息和当前项目真相自动判断复用、修改或替换并记录在过程时间线，只有业务方向不明确时才请求人工校准，且候选必须重新完成适用校验、评审和审批，不能直接封存。每个产物绑定其项目和生产阶段，已删除产物的逻辑 ID 永不复用，历史内容按 Git Commit 查询。

`artifact` 和 `artifact_draft` 将稳定身份、标题、版本、生产基线、Git 定位及平台固定追踪关系保存为明确列；固定追踪列包括上游来源、需求、接口、读取表和写入表等逻辑引用，并使用 PostgreSQL 数组与 GIN 索引支持反向影响查询。只有不同产物类型的业务正文和 `domain_extensions` 保存在 `body` JSONB。Git YAML 由固定列与 `body` 确定性合成，Profile 只能扩展 `body.domain_extensions`，不能动态新增平台级追踪字段；需要新跨阶段关系时由平台数据库迁移增加明确字段。

技术架构决策使用 `ARCHITECTURE_DECISION` 产物类型和 `ADR` 逻辑编号前缀，作为架构阶段的普通产物进入同一草稿、校验、评审、批量 Git 发布和基线流程，不建立专用数据库表。其 `body` 记录决策问题、约束、选择方案、备选、理由、后果和风险，并通过固定引用字段关联需求、模块、接口或数据表。

数据库内部记录关联使用 UUID，例如 `artifact_draft.artifact_id` 指向当前 `artifact.id`；产物之间的业务追踪统一使用项目内稳定逻辑编号数组，例如 `requirement_refs = ['REQ-000001']`。Git YAML 和导出文件使用相同逻辑编号，不暴露数据库 UUID。由于数组不能提供逐元素外键，平台必须在候选发布、产物删除和阶段基线封存前执行项目内引用存在性与类型匹配校验。

产物逻辑 ID 使用项目内、按产物类型独立递增的编号，例如每个项目分别从 `REQ-000001`、`API-000001` 开始。各类型已发放的最大序号保存在 `project.artifact_counters` JSONB 中，并在既有项目级写锁内原子递增，不新增计数表；删除产物不得回退计数。`artifact` 以 UUID 作为内部主键，并通过 `(project_id, artifact_code)` 唯一约束保护逻辑编号。

新产物的 `artifact_draft` 只使用草稿 UUID 和 `canonical_key`，`artifact_code` 保持为空；生成失败、评审驳回或汇合时被判定为重复的草稿不得消耗正式编号。一个阶段内的草稿分别完成去重、校验、评审和必要审批后，平台才在阶段封存步骤中按产物类型连续预留正式编号、解析同批新产物之间的正式逻辑引用，并以一次 Git Commit 写入本阶段全部批准文件，在同一 Commit 创建基线 Tag。发布失败时草稿保留相同预留编号用于原号重试；Git 和数据库封存全部成功后才更新项目类型计数高水位、创建或更新当前 `artifact` 并删除本阶段草稿。因此正常新增保持连续，只有已经正式发布后又被删除的产物才留下编号空缺。

阶段尚未封存时，用户提出修改只将受影响产物及其依赖草稿从已审批状态退回 `REVISING`，其他未受影响草稿的审批继续有效；所有受影响内容重新通过后才可批量封存。阶段基线已经封存后不再直接修改当前产物，必须创建项目变更并进入重新基线化流程。

项目变更批准并开始重新基线化后，受影响的旧阶段基线立即退出 `SEALED` 可消费状态；其 Git Commit 和 Tag 仍可查看、下载和审计，但不得启动任何新的下游 Graph Run。受影响的当前下游基线标记为 `INVALIDATED`，只有新上游基线封存并完成必要重建后才重新开放下游工作。

变更影响分析精确到固定追踪字段中的产物逻辑引用，用于决定哪些产物需要生成或修改草稿；但只要一个当前产物受影响，其所属阶段基线就整体 `INVALIDATED`。未受影响产物不重新生成，继续作为新阶段快照的复用输入；受影响产物完成后，平台对阶段全部产物重新执行引用、覆盖和语义一致性检查，再以一个完整 Git Commit 和 Tag 封存新基线。

这里的阶段基线整体失效只表示旧阶段快照暂停作为新下游 Run 的输入，不表示阶段内全部产物重新生成。平台从变更产物开始沿当前逻辑引用递归计算受影响产物，逐阶段只为命中的产物创建草稿；未命中产物在新 Git 快照中保持原内容。某阶段缺少必要引用、无法证明影响边界时，保守地将该阶段及其下游产物全部纳入重建范围，不得假设无影响。

产物被批准移除时，平台先校验并处理全部当前引用，再以 Git Commit 删除稳定路径文件；Git 成功后删除 PostgreSQL 中对应的当前 `artifact` 记录，不保留墓碑或历史产物行，删除过程只在 `artifact_draft` 中暂存 `DELETING` 状态。旧内容和旧成员关系完全通过历史基线 Tag 与 Git Commit 查询，项目类型计数器保持原高水位以防逻辑 ID 复用。

`project_stage` 以 `(project_id, stage)` 唯一，每个项目预置一组交付阶段行，同时记录该阶段进度和当前批准基线指针。它保存阶段状态、当前基线版本、Git commit SHA、确定性 Git Tag 及阶段发布错误，不保存 Manifest 或产物引用清单；该 Commit 的阶段目录树就是基线的完整产物集合，历史基线通过 `baseline/<stage>/<version>` Tag 查询。`project` 只保存项目整体状态，不再保存单值 `current_stage`；多个 `project_stage` 可以同时处于 `BUILDING`，Graph 更细执行位置由助手消息过程时间线展示，内部恢复状态由 PostgreSQL Checkpoint 记录。

`project_stage.status` 表达 `NOT_STARTED`、`BUILDING`、`WAITING_FOR_HUMAN`、`SEALING`、`SEALED`、`SEAL_FAILED` 和 `INVALIDATED` 等阶段生命周期，Graph 只能消费 `SEALED` 阶段基线。`publish_key` 只用于发布幂等，`git_commit_sha` 和 `git_tag` 只记录 Git 结果；二者有值不能替代业务状态。状态进入 `SEALED` 时必须同时存在 commit SHA 和 Tag，Git 已成功但数据库尚未完成封存时由 Worker 幂等补全。

当前工作区列表、候选编辑和关系查询读取 PostgreSQL 当前投影；下游 Graph 消费已封存上游基线、历史查看和下载导出必须按 `project_stage.git_commit_sha` 或 Git Tag 从 GitLab 读取，不得用可能包含未封存后续修改的 `artifact` 当前行代替。Graph Run 启动时加载并固定所需 Git 基线作为本次运行输入，运行期间只使用该快照，可在 Run 范围内缓存但不得随默认分支变化。

中断后保留的 `artifact_draft` 仍属于当前工作区投影，当前 Run 正在处理的各阶段草稿统一退回已有 `REVISING` 状态，OWNER、MEMBER 和 VIEWER 均可读取；不增加草稿来源字段、中断专用状态或持久化标识。批准产物下载包和下游输入只读取 Git 基线，不得包含这些草稿，也不提供将其伪装成批准产物的导出路径。

每个 Delivery Run 在 `input_baselines` JSONB 中记录实际消费的上游阶段、基线版本、Git commit SHA 和 Tag；该运行输入在 Run 启动后不可修改。不同节点依赖的上游基线数量不固定，因此该字段保存运行快照而不拆关联表，也不用于替代当前基线查询。

首版不建立独立 `git_publish_outbox` 表，也不为单个 `artifact_draft` 维护 Git 发布状态。阶段级批量发布的状态、幂等键、尝试次数和最近错误全部保存在 `project_stage`；Worker 使用项目级写锁和行锁领取处于 `SEALING` 的阶段，发布内容由该阶段已批准草稿确定性生成。Git Commit 消息携带基线发布幂等键，确定性基线 Tag 同时作为封存幂等标识；进程在 Git 成功、数据库更新前崩溃时，重试先按幂等键或 Tag 查找已有结果，再补全 `artifact`、项目计数器和阶段状态。成功后删除本阶段全部草稿；失败草稿保留到问题解决或用户放弃，生成和评审过程由 Delivery Run 证据承担。系统不保留无限增长的独立任务流水，审计历史由 Delivery Run、Git Commit 和基线 Tag 承担。

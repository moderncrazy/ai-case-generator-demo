# AI 软件交付平台 V2 测试用例设计

| 属性 | 内容 |
| --- | --- |
| 文档状态 | `APPROVED` |
| 文档版本 | 1.0 |
| 日期 | 2026-08-06 |
| 上游基线 | PRD 1.0、总体架构 1.0、Graph/模块设计 1.0、数据库设计 1.1、API 设计 1.0 |
| 首发终点 | TEST 基线设计完成，不执行自动开发或自动测试 |

## 1. 测试目标

本设计验证平台能够从项目创建开始，经三个人工校准点，可靠地产出需求、PRD、架构、系统模块、API、数据库和测试用例批准基线。测试不仅验证接口返回值，还验证 PostgreSQL 当前投影、Redis 临时状态、LangGraph Checkpoint、GitLab 历史和对象存储之间的业务一致性。

首发不测试自动编码、测试执行、缺陷回流和生产发布。

## 2. 用例格式

| 字段 | 说明 |
| --- | --- |
| 用例 ID | `TC-领域-序号`，在本文内稳定 |
| 优先级 | P0 阻断上线；P1 核心异常与恢复；P2 辅助和边界 |
| 类型 | UNIT、DB、API、GRAPH、INTEGRATION、E2E、SECURITY、RESILIENCE |
| Given | 前置状态和测试数据 |
| When | 操作或故障注入 |
| Then | 可断言结果，不使用“正常”“合理”等模糊描述 |
| 追踪 | PRD 功能要求、架构章节或 API 路径 |

## 3. 测试环境与替身

| 依赖 | 单元/组件测试 | 集成/E2E |
| --- | --- | --- |
| PostgreSQL | 独立临时 Schema，执行真实 DDL | 与生产同主版本的独立实例 |
| Redis | 真实 Redis 测试实例 | 独立实例，可执行故障注入 |
| LangGraph | 真实 PostgreSQL Checkpointer | 与 Worker 共同运行 |
| 模型 | Deterministic Fake Model，按场景返回固定结构 | 受控模型 Profile；关键验收仍使用 Fake 保证确定性 |
| Git | In-memory Git Adapter | 内部测试 GitLab Project |
| MinIO/S3 | In-memory Object Adapter | 独立 Bucket |
| 时间 | Fake Clock | 可控 NTP 时间源和短 TTL 配置 |

每个测试独立创建项目、用户、Git 仓库和 Redis Key。禁止复用生产数据或真实密钥。

## 4. 发布门禁

- P0 必须 100% 通过。
- P1 不允许存在未接受的失败；已接受风险必须有 OWNER、范围和截止日期。
- API OpenAPI Schema 与文档中的 63 个公开接口一致。
- 数据库约束、并发和 Git 部分失败必须使用真实 PostgreSQL/GitLab 验证。
- E2E 至少覆盖一个通用 Profile 项目和一个专业 Profile 项目。
- 测试报告必须记录代码 Commit、数据库迁移版本、Profile Hash 和模型替身版本。

## 5. 认证与用户

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-AUTH-001 | P0 | API | ACTIVE 用户提交正确用户名密码 | 返回 200、Session Cookie、CSRF Token；Redis 两个 Key TTL 为 2 小时 | API `POST /session` |
| TC-AUTH-002 | P0 | SECURITY | 提交不存在用户名或错误密码 | 均返回相同 `AUTHENTICATION_FAILED`，不泄露账户是否存在 | FR-AUTH、API 错误码 |
| TC-AUTH-003 | P0 | API | DISABLED 用户登录 | 返回 `ACCOUNT_DISABLED`，不创建 Session | FR-AUTH |
| TC-AUTH-004 | P0 | INTEGRATION | 已登录用户发起有效请求 | `session:<hash>` 与 `user:<id>` TTL 均滑动恢复为 2 小时 | ADR 0017 |
| TC-AUTH-005 | P1 | INTEGRATION | SSE 连接仅接收心跳超过一次 TTL 刷新周期 | 心跳不刷新 Session 或用户缓存 TTL | API SSE |
| TC-AUTH-006 | P0 | SECURITY | 写请求缺失或伪造 CSRF、Origin、Fetch Metadata | 返回 `CSRF_VALIDATION_FAILED`，业务数据不变化 | 架构 15 |
| TC-AUTH-007 | P0 | API | 同一用户在两个设备登录 | 两个 Session 同时有效且互不覆盖 | FR 多端登录 |
| TC-AUTH-008 | P0 | INTEGRATION | 管理员禁用已有多端 Session 用户 | DB 与 Redis 用户状态变为 DISABLED；Session 不删除；后续请求均 403 | ADR 0017 |
| TC-AUTH-009 | P0 | INTEGRATION | 重新启用尚未过期 Session 用户 | 原 Session 无需登录即可继续请求 | 确认决策 |
| TC-AUTH-010 | P0 | API | 用户修改密码 | Hash/Salt 更新；所有现有 Session 保持有效；旧密码不能新登录 | API `PUT /me/password` |
| TC-AUTH-011 | P1 | DB | 连续创建大小写不同的相同 username | 唯一索引拒绝第二条，API 返回稳定冲突错误 | DB 6.1 |
| TC-AUTH-012 | P1 | SECURITY | VIEWER/USER 调用 ADMIN API | 返回 `PERMISSION_DENIED`，响应不含敏感字段 | 权限矩阵 |

## 6. 项目、成员与工作台

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-PROJ-001 | P0 | INTEGRATION | 使用新 Idempotency-Key 创建项目 | 创建 Project、OWNER、九个 Stage、首次消息、当前 Run 和 GitLab 创建任务 | API `POST /projects` |
| TC-PROJ-002 | P0 | API | 相同用户以相同 Key 和相同请求重试创建 | 返回原 Project 和 Run，不重复创建仓库或阶段 | 幂等设计 |
| TC-PROJ-003 | P0 | API | 相同 Key 提交不同项目内容 | 返回 `IDEMPOTENCY_KEY_REUSED`，原项目不变 | API 错误码 |
| TC-PROJ-004 | P1 | RESILIENCE | GitLab 项目创建失败 | 项目变为 BLOCKED；PG 数据保留；重试不会创建重复仓库 | 架构 Git seam |
| TC-PROJ-005 | P0 | API | OWNER 查询工作台 | 返回项目、九阶段、Run、Gate、Queue、占用和 allowed_actions 的一致快照 | API workspace |
| TC-PROJ-006 | P0 | SECURITY | VIEWER 查询工作台 | 可读取时间线、候选摘要和批准产物；不包含写动作 | ADR 0019 |
| TC-PROJ-007 | P0 | API | OWNER PUT 新成员及修改角色 | 成员关系幂等更新，重复 PUT 结果相同 | API members |
| TC-PROJ-008 | P0 | DB | 删除或降级最后一名 OWNER | 事务拒绝并返回 `LAST_OWNER_REQUIRED` | DB 成员约束 |
| TC-PROJ-009 | P1 | SECURITY | 非 OWNER 管理项目成员 | 返回 `PERMISSION_DENIED`，关系不变化 | 权限矩阵 |
| TC-PROJ-010 | P1 | API | 项目存在 API、DATABASE、TEST 同时 BUILDING | 工作台返回三行真实状态，不生成单值 current_stage | FR-DESIGN、DB 9.1 |

## 7. 消息幂等、对话占用和 Queue

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-MSG-001 | P0 | API | 空闲项目提交 DIRECT | 原子取得占用，创建用户/助手消息和 QUEUED Run，返回 202 | FR-MSG-003/005 |
| TC-MSG-002 | P0 | API | 相同项目、用户、Key 和请求重试消息 | 返回原 MessageReceipt，不创建第二个 Message 或 Run | DB 14.2 |
| TC-MSG-003 | P0 | API | 相同 Key 改变 content 或 delivery_mode | 返回 `IDEMPOTENCY_KEY_REUSED` | API 5 |
| TC-MSG-004 | P0 | DB | 两用户同时向空闲项目提交 DIRECT | 仅一个原子取得占用并成功；另一个返回 `CONVERSATION_OCCUPIED` | ADR 0013/0024 |
| TC-MSG-005 | P0 | INTEGRATION | 当前用户每次成功提交消息 | 占用 TTL 刷新为 300 秒 | FR-MSG-003 |
| TC-MSG-006 | P0 | INTEGRATION | Run 正在执行或 Queue 非空 | Worker 持续续期占用，其他用户不能在 5 分钟后抢占 | FR-MSG-004 |
| TC-MSG-007 | P0 | INTEGRATION | Run 进入 WAITING_FOR_HUMAN | Worker 停止续期；自然过期后其他合格用户可取得占用 | FR-GATE-006 |
| TC-MSG-008 | P0 | API | 活跃 Run 中当前用户提交 STEER 和正确 expected_run_id | Message 绑定当前 Run，在下一安全 Checkpoint 被消费 | FR-MSG-005 |
| TC-MSG-009 | P0 | GRAPH | 封存原子区收到 STEER | 请求返回 202，实际模式为 QUEUE，原因明确，消息不丢失 | FR-MSG-006 |
| TC-MSG-010 | P0 | API | 活跃 Run 中提交 QUEUE | 消息状态 QUEUED，不覆盖当前 delivery_run | DB 14.3 |
| TC-MSG-011 | P0 | DB | 多条 Queue 时间相同 | 以 `(created_at,id)` 稳定顺序逐条启动 | ADR 0024 |
| TC-MSG-012 | P0 | API | Queue 提交者取消尚未执行消息 | 原 Message 保留，状态 CANCELLED，记录操作者和时间 | FR-MSG-008 |
| TC-MSG-013 | P0 | SECURITY | MEMBER 取消他人 Queue | 返回 `POLICY_REJECTED`，Queue 保持不变 | FR-MSG-008 |
| TC-MSG-014 | P0 | API | OWNER 取消任意待执行 Queue | 取消成功并保留审计字段 | FR-MSG-008 |
| TC-MSG-015 | P0 | API | Queue 已被启动后请求取消 | 返回 `MESSAGE_NOT_CANCELLABLE`，不得影响当前 Run | API 错误码 |
| TC-MSG-016 | P0 | API | 无 Run、无 Queue且占用者主动释放 | Redis 占用删除，其他用户可立即发言 | FR-MSG-007 |
| TC-MSG-017 | P0 | API | 活动 Run 或 Queue 存在时释放 | 返回 `CONVERSATION_RELEASE_NOT_ALLOWED` | FR-MSG-007 |
| TC-MSG-018 | P1 | INTEGRATION | Redis 占用 Key 丢失但 PG 有活动 Run | 服务端数据库单写兜底拒绝并发新 Run，Scheduler/Worker 恢复续期 | 架构 10.2 |

## 8. Graph、人工 Gate 与意图路由

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-GRAPH-001 | P0 | GRAPH | 新项目首次消息 | PM 输出结构化项目理解、假设、排除项和项目章程候选 | Graph 入口 |
| TC-GRAPH-002 | P0 | E2E | 项目章程 Gate 未批准 | 不生成正式需求大纲下游基线 | FR-GATE-001 |
| TC-GRAPH-003 | P0 | E2E | 需求大纲和模块分别完成，只有部分模块确认 | PRD 不启动，直到全部需求模块批准 | 已确认门禁规则 |
| TC-GRAPH-004 | P0 | E2E | PRD Gate 未批准 | 架构及所有技术阶段不启动 | FR-GATE-003 |
| TC-GRAPH-005 | P0 | GRAPH | OWNER 批准当前 Gate | 决议进入共享时间线，Checkpoint 恢复且 Gate 不可重复处理 | API Human Gate |
| TC-GRAPH-006 | P0 | GRAPH | 两个 OWNER 对同一 Gate 并发提交不同决议 | 仅一个成功；另一个收到 `HUMAN_GATE_ALREADY_RESOLVED` | 并发决议 |
| TC-GRAPH-007 | P0 | GRAPH | Gate 决议携带旧 run_id 或 gate_id | 返回 `HUMAN_GATE_MISMATCH`，当前 Gate 不变化 | API 并发控制 |
| TC-GRAPH-008 | P0 | GRAPH | MEMBER 占用期间进入 OWNER-only Gate | MEMBER 占用自动释放；OWNER 决议可取得发言权 | ADR 0024 |
| TC-GRAPH-009 | P0 | GRAPH | 技术阶段发现新的业务范围决策 | 转为临时 Human Gate，不由 PM 自行决定 | FR-GATE-004 |
| TC-GRAPH-010 | P0 | GRAPH | Author 输出候选 | 独立 Validator 和 Reviewer 执行；Author 不审批自己结果 | FR-AGENT-002 |
| TC-GRAPH-011 | P0 | GRAPH | Reviewer 发现业务规则缺失 | 返回 Finding/决策升级，不直接补写未知业务规则 | Graph Reviewer |
| TC-GRAPH-012 | P1 | GRAPH | 用户只询问项目状态 | 意图路由为 Query，不启动生成或修改基线 | PM Intent |
| TC-GRAPH-013 | P1 | GRAPH | 用户对未封存候选提出调整 | 只修改允许范围候选并重新校验，不创建 Change | Graph Intent |
| TC-GRAPH-014 | P0 | GRAPH | 用户要求修改已批准产物 | 创建 project_change，先影响分析和决议，不直接覆盖基线 | FR-CHG |
| TC-GRAPH-015 | P1 | GRAPH | 模型输出不符合结构 Schema | Gateway 有限重试；仍失败则 Run FAILED，非法数据不落业务表 | Model Gateway |

## 9. API、数据库并行设计与测试汇合

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-DESIGN-001 | P0 | GRAPH | SYSTEM_MODULE 已封存 | API 和 DATABASE 在同一顶层 Run 中并行 BUILDING，共享固定输入基线 | FR-DESIGN-001 |
| TC-DESIGN-002 | P0 | GRAPH | API 分支尝试读取或修改 DB 草稿 | 直接依赖被拒绝，只能在 Convergence 节点汇合 | 架构 8.3 |
| TC-DESIGN-003 | P0 | GRAPH | 一侧 READY、另一侧仍 BUILDING | 两侧均不得封存 | FR-DESIGN-004 |
| TC-DESIGN-004 | P0 | GRAPH | API 字段类型与数据库列不一致 | Convergence 产生定向 Finding 并退回责任分支 | Graph 10.2 |
| TC-DESIGN-005 | P0 | GRAPH | API 操作缺少事务或幂等设计 | Convergence 不通过并返回 API/DB 责任阶段 | FR-DESIGN-004 |
| TC-DESIGN-006 | P0 | GRAPH | API/DB 汇合全部通过 | 两个阶段基线才允许封存并解锁契约/数据测试层 | FR-DESIGN-005 |
| TC-DESIGN-007 | P0 | GRAPH | 上游需求/架构封存后 | 对应业务验收、架构和接口测试草稿分层生成 | FR-TEST-001/003 |
| TC-DESIGN-008 | P0 | GRAPH | 某层测试草稿仍有未解决覆盖缺口 | 唯一 TEST 基线不得封存 | FR-TEST-004 |
| TC-DESIGN-009 | P0 | GRAPH | 所有测试层通过统一汇合 | AI PM 自动封存唯一 TEST 基线，无固定人工审批 | FR-TEST-005 |
| TC-DESIGN-010 | P0 | GRAPH | 追踪引用缺少 REQ/API/TABLE 目标 | 确定性校验失败并阻止封存 | FR-ART 追踪 |

## 10. 产物、编号与 Git 基线

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-ART-001 | P0 | DB | 新候选保存 | artifact_draft 有 UUID/canonical_key，但 artifact_code 为空 | ADR 0023 |
| TC-ART-002 | P0 | DB | 同项目同类型多个新候选封存 | 在项目锁内连续分配编号，不受其他项目/阶段影响 | 编号决策 |
| TC-ART-003 | P0 | DB | 删除老产物后创建新产物 | 已使用编号不回收，新编号从最大值继续 | 编号决策 |
| TC-ART-004 | P0 | INTEGRATION | 阶段封存成功 | YAML/Markdown 确定性生成，Git Commit/Tag、artifact 投影、stage 基线一致，草稿删除 | DB 14.6 |
| TC-ART-005 | P0 | RESILIENCE | 编号预留后 Git 写入失败 | Stage 为 SEAL_FAILED/SEALING，草稿和预留编号保留，重试使用原编号 | ADR 0023 |
| TC-ART-006 | P0 | RESILIENCE | Git 成功后、PG 事务 B 前进程崩溃 | Scheduler 按 publish_key/Tag 找到已有 Commit 并补全 PG，不产生第二 Commit | 无 Outbox 恢复 |
| TC-ART-007 | P0 | INTEGRATION | 同一 publish_key 重复封存 | 返回同一 Git 基线和当前投影，不重复 Tag | Git 幂等 |
| TC-ART-008 | P0 | API | 查询当前 Artifact | 列表来自 PG，正文按当前 Stage Commit/Tag 从 Git 读取 | FR-ART-007 |
| TC-ART-009 | P0 | API | 查询历史基线/Diff | 完全按 Git 历史返回，不依赖 artifact 历史表或 Manifest | ADR 0023 |
| TC-ART-010 | P0 | SECURITY | VIEWER 下载批准基线 | 可下载且只含批准 YAML/Markdown；不含草稿、诊断、附件原件 | FR-ART-006 |
| TC-ART-011 | P0 | API | 请求下载未批准草稿 | 返回 `APPROVED_CONTENT_ONLY` | API 错误码 |
| TC-ART-012 | P1 | INTEGRATION | 完整包生成期间某阶段产生新基线 | 下载仍使用开始时固定的 Commit 集合，不混入新版本 | API download |

## 11. Profile 生命周期与迁移

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-PROF-001 | P0 | DB | 两管理员以相同 lock_version 保存草稿 | 仅首个成功，第二个返回 `PROFILE_DRAFT_VERSION_CONFLICT` | DB 11.2 |
| TC-PROF-002 | P0 | API | 草稿缺少必需 Schema/迁移内容后校验 | valid=false，问题有 code/path/message，不可发布 | API Profile |
| TC-PROF-003 | P0 | DB | 发布 Profile 新版本 | 版本严格加 1，Version 行不可更新/删除，current_version 前进 | ADR 0021 |
| TC-PROF-004 | P0 | DB | 发布 2+ 版本但缺少相邻迁移 | 发布失败，不产生不连续版本 | Profile 发布 |
| TC-PROF-005 | P0 | API | 修改已存在迁移规则且 Hash 过期 | 返回 `PROFILE_RULE_HASH_CONFLICT` | API migration |
| TC-PROF-006 | P0 | GRAPH | 项目落后多个版本后提交新对话 | 自动按相邻规则逐步迁移到最新，再处理原消息 | FR-PROFILE-007 |
| TC-PROF-007 | P0 | RESILIENCE | 第二个迁移步骤技术失败 | 保留第一个成功版本，项目写入阻塞，读和下载继续 | DB 14.5 |
| TC-PROF-008 | P0 | GRAPH | 迁移失败后用户再次对话 | 每次仍自动重试迁移，不因历史失败跳过 | 确认决策 |
| TC-PROF-009 | P0 | API | 管理员手动重试失败迁移 | 返回 202；成功后原项目可继续；不新增迁移 Run 历史表 | API admin retry |
| TC-PROF-010 | P0 | SECURITY | 普通用户查询项目/工作台 | 不返回 Profile ID、名称、版本选择或匹配过程 | Profile 隐藏决策 |
| TC-PROF-011 | P1 | DB | 管理员尝试停用内置通用 Profile | 返回 `BUILTIN_PROFILE_REQUIRED`，状态保持 ACTIVE | DB 11.1 |
| TC-PROF-012 | P1 | GRAPH | 新项目匹配不到专业 Profile | PM 自动绑定通用 Profile，用户无额外选择步骤 | Profile 自动匹配 |

## 12. 中断、失败与恢复

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-REC-001 | P0 | GRAPH | 当前占用者中断 RUNNING Run | Run 先 STOPPING，在安全点后助手消息/Run 为 INTERRUPTED | FR-RUN-004 |
| TC-REC-002 | P0 | GRAPH | OWNER 强制中断 MEMBER Run | 允许绕过占用；安全停止后占用原子转交 OWNER | FR-RUN-006 |
| TC-REC-003 | P0 | GRAPH | 中断时存在多条 Queue | 全部 Queue 标记 CANCELLED，记录同一停止操作者/时间 | ADR 0024 |
| TC-REC-004 | P0 | GRAPH | 中断时当前 Run 有多个阶段草稿 | 全部保留并回到 REVISING，不增加中断专用草稿状态 | FR-RUN-005 |
| TC-REC-005 | P0 | RESILIENCE | 中断发生在 Git/封存原子区 | 原子区成功或失败后再停止；已成功基线不回滚 | FR-RUN-007 |
| TC-REC-006 | P0 | INTEGRATION | Run 最终 INTERRUPTED | Checkpoint Thread 清理，旧 Run 不可恢复 | FR-RUN-005 |
| TC-REC-007 | P0 | RESILIENCE | Worker 在可重试节点崩溃且租约过期 | 另一 Worker 从 Checkpoint 领取；幂等节点不重复副作用 | 架构 Worker |
| TC-REC-008 | P0 | RESILIENCE | Run FAILED | Checkpoint 保留，重试继续；放弃后清理并允许下一 Run | DB 8.3 |
| TC-REC-009 | P1 | API | 对非 FAILED Run 调用 retry/abandon | 返回 `RUN_NOT_FAILED`，当前 Run 不变化 | API Run |
| TC-REC-010 | P0 | DB | 新 Run 覆盖每项目唯一 delivery_run | 仍仅一行；旧过程可从 project_message 查看 | Run 当前投影 |

## 13. SSE 与前端恢复

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-SSE-001 | P0 | INTEGRATION | 助手追加过程事件 | 同事务更新 process[] 和 process_version，SSE 发送对应版本 | FR-OBS-001 |
| TC-SSE-002 | P0 | API | 客户端携带旧 Message Version 重连 | API 从 PG 补发缺失 ProcessEvent，再订阅 Redis | 架构 14.2 |
| TC-SSE-003 | P0 | RESILIENCE | Redis Pub/Sub 丢失一条通知 | 重连 project.sync/resync.required 使 UI 收敛到 PG 状态 | ADR 0016 |
| TC-SSE-004 | P1 | INTEGRATION | 慢客户端积压重复资源更新 | 可合并 stage/project 通知，但不能跳过 process_version | SSE 契约 |
| TC-SSE-005 | P1 | SECURITY | 无项目读取权限订阅 SSE | 返回 403/404，不泄露项目事件 |
| TC-SSE-006 | P1 | INTEGRATION | 仅接收 SSE 心跳 | 不写数据库、不刷新 Session、不续期对话占用 | API 18 |

## 14. 数据库约束与并发

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-DB-001 | P0 | DB | 同项目插入重复 stage | UNIQUE(project_id,stage) 拒绝 |
| TC-DB-002 | P0 | DB | 同项目创建第二条当前 Run | delivery_run.project_id PK 拒绝 |
| TC-DB-003 | P0 | DB | SEALED Stage 缺少 version/commit/tag | CHECK 拒绝提交 |
| TC-DB-004 | P0 | DB | 用户 Message 缺少 idempotency_key/request_hash | CHECK 拒绝；助手消息携带这些字段也被拒绝 |
| TC-DB-005 | P0 | DB | 同用户、项目重复幂等 Key | 唯一约束拒绝第二条不同消息 |
| TC-DB-006 | P0 | DB | 不同用户或不同项目使用相同 Key | 均可创建，作用域互不影响 |
| TC-DB-007 | P0 | DB | 两封存事务并发分配编号 | 项目锁串行化，无重复或跳过非失败预留 |
| TC-DB-008 | P1 | DB | Profile 版本重复、跳号或迁移非相邻 | 唯一/CHECK/发布事务拒绝 |
| TC-DB-009 | P1 | DB | 终态 Change 缺少决议人与 Git 指针 | 领域事务拒绝进入终态 |
| TC-DB-010 | P1 | DB | 查询高频路径执行计划 | 使用设计索引，不对 truth/body/process 做全表 GIN |

## 15. 文件、对象存储与安全

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-FILE-001 | P0 | API | 上传支持类型且大小合法附件 | 安全检查、Hash、对象写入和 project_file 绑定成功 | File Module |
| TC-FILE-002 | P0 | API | 同项目上传同名附件 | 返回 `FILE_NAME_CONFLICT`，不覆盖旧对象 |
| TC-FILE-003 | P0 | SECURITY | 上传超限、伪造 MIME 或危险内容 | 分别返回稳定文件错误，不进入模型上下文 | API 错误码 |
| TC-FILE-004 | P1 | RESILIENCE | 对象写成功但数据库事务失败 | 补偿删除孤儿对象或由清理器回收，不出现可见 project_file |
| TC-FILE-005 | P0 | SECURITY | 普通用户请求内部对象 Key/GitLab URL/Secret | 所有响应均不包含内部凭据或可写地址 | 安全架构 |
| TC-SEC-001 | P0 | SECURITY | 修改 path 中 project_id 越权读取或写入 | 返回 404/403，目标项目无变化 |
| TC-SEC-002 | P0 | SECURITY | 注入 SQL、脚本、Prompt 指令到名称/消息/附件 | ORM 参数化；UI 转义；Prompt 注入不能绕过策略代码 |
| TC-SEC-003 | P1 | SECURITY | 普通用户查询 diagnostics | 返回 `PERMISSION_DENIED` |
| TC-SEC-004 | P1 | SECURITY | 日志采样登录、消息、模型和 Git 错误 | 不出现密码、Token、Salt、完整 Prompt、附件正文或 Secret |

## 16. 首发端到端验收

| ID | P | 类型 | Given / When | Then | 追踪 |
| --- | --- | --- | --- | --- | --- |
| TC-E2E-001 | P0 | E2E | OWNER 创建通用项目并逐个完成三个 Gate | 最终九阶段状态/基线符合流程，TEST 唯一基线封存 | PRD 主流程 |
| TC-E2E-002 | P0 | E2E | 多模块需求逐个审批 | 未全部批准前不生成 PRD；全部批准后仅生成一份一致 PRD | 已确认规则 |
| TC-E2E-003 | P0 | E2E | API/DB 先产生冲突后定向返工 | 汇合前不封存；修复后同时形成一致基线 | FR-DESIGN |
| TC-E2E-004 | P0 | E2E | 运行期间 STEER、QUEUE、页面刷新和 SSE 重连 | 指令不丢失、顺序稳定、UI 与 PG 最终一致 | FR-MSG/RUN |
| TC-E2E-005 | P0 | E2E | 已批准 API 发起变更并批准 | 受影响 API/TEST 基线失效并重建；未受影响产物复用；旧版本仍可下载 | FR-CHG |
| TC-E2E-006 | P0 | E2E | 最新 Profile 发布后历史项目首次对话 | 自动迁移完成后继续原消息，用户不需要选择 Profile | FR-PROFILE |
| TC-E2E-007 | P0 | E2E | 完成项目下载完整批准包 | 包内文件、引用、Commit 集合与 UI 当前基线完全一致 | FR-ART |
| TC-E2E-008 | P0 | E2E | 在关键生成阶段中断后重新发起新消息 | 旧 Checkpoint 不恢复，保留草稿可供新 Run 重新规划 | FR-RUN |

## 17. 需求追踪与覆盖检查

自动生成 TEST 基线前必须执行以下确定性检查：

1. 每条 P0/P1 PRD 要求至少有一个正向用例；权限、并发或错误相关要求至少有一个反向用例。
2. 每个公开 API 至少覆盖成功、认证、授权、校验和领域冲突中适用的类别。
3. 每个数据库 CHECK、UNIQUE、关键 FK 和部分唯一索引至少有一个约束测试。
4. 每个 Run/Message/Stage/Change/Profile 状态迁移至少覆盖合法边和关键非法边。
5. Git、Redis、Checkpoint、模型和对象存储每个外部 seam 至少有一次故障注入。
6. 所有测试引用必须能解析到需求、模块、API、表或阶段代码；孤立引用阻止封存。

## 18. 实现阶段自动化建议

| 测试层 | 建议工具 | 执行时机 |
| --- | --- | --- |
| Python 单元/领域状态机 | pytest | 每次提交 |
| FastAPI 契约 | pytest + httpx + OpenAPI snapshot | 每次提交 |
| PostgreSQL/Redis/GitLab 集成 | Testcontainers 或 CI 服务容器 | PR |
| React 组件与 API Client | Vitest + Testing Library | 每次提交 |
| 浏览器 E2E | Playwright | PR 和候选发布 |
| 故障注入/恢复 | pytest 场景 + 可控 Adapter | PR 和每日构建 |
| 安全扫描 | SAST、依赖扫描、DAST | PR/每日/发布 |

本文不固定具体测试框架版本；实现计划必须根据当时依赖版本锁定，并生成可重复的测试数据工厂和清理机制。

## 19. 验收清单

- [ ] 首发范围内所有功能要求均有测试追踪。
- [ ] 三个人工 Gate、API/DB 汇合和唯一 TEST 基线均有 P0 E2E。
- [ ] Message 幂等、对话占用、Queue、STEER 和中断有并发/恢复测试。
- [ ] Profile 自动迁移失败不会放行业务写入，但读取和下载保持可用。
- [ ] Git 部分成功可幂等补全且不需要 Outbox。
- [ ] 63 个 API 的成功与适用错误路径进入契约覆盖生成规则。
- [ ] VIEWER、MEMBER、OWNER、ADMIN 权限矩阵包含正反向测试。
- [ ] 测试数据、日志和报告不包含生产密钥或敏感正文。

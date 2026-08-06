# AI 软件交付平台 V2 API 设计说明（契约重写前留档）

> 本文件仅保留接口设计推导，不是实现契约。实现与评审必须使用 `docs/api/platform-v2-api-design.md`。

| 属性 | 内容 |
| --- | --- |
| 文档状态 | `DRAFT_FOR_REVIEW` |
| 文档版本 | 0.2 |
| 日期 | 2026-08-06 |
| 上游基线 | V2 PRD 1.0、总体架构 1.0、Graph/模块设计 1.0、数据库设计 1.1 |
| 服务端 | FastAPI |
| 客户端 | React + OpenAPI 生成 Client |

## 1. 文档目的

本文定义 V2 首发版公开 HTTP API 的资源、Command、Query、鉴权、幂等、并发、SSE、错误、权限和下载契约。接口服务于 React SPA 和管理员页面，不作为 Graph 节点、数据库表或 GitLab 的远程控制面。

首发 API 只支撑从项目创建到需求、PRD、架构、系统模块、API、数据库和测试用例基线完成。自动开发、自动测试执行和发布接口不在本文范围。

## 2. 设计结论

采用“资源查询 + 显式业务动作”的混合风格：

- Query 使用 `GET`，读取稳定资源或面向页面的投影，不启动模型或隐式改变业务状态。
- 创建资源使用 `POST`，幂等替换使用 `PUT`，有限字段修改才使用 `PATCH`。
- 中断、重试、人工决议、取消和发布等状态迁移使用命名明确的动作子资源。
- 长时 AI 处理在 Worker 执行，HTTP 命令只负责验证、落库和调度，通常返回 `202 Accepted`。
- SSE 只通知持久状态增量，PostgreSQL 和 Git 才是断线恢复来源。
- OpenAPI 是前后端契约源；前端不得复制 Graph 状态机。

明确不采用：

- 每张数据库表一套 CRUD。
- 统一万能 `/commands` 入口。
- 客户端直接修改 Run、Stage、Artifact 或 Gate 状态。
- 客户端指定 `project_message.id`。
- 通用 ETag/Revision 框架。
- 独立 Command、Gate、SSE Event、Upload Session 或 Idempotency 表。

## 3. 通用 HTTP 约定

### 3.1 基础约定

```text
Base Path: /api/v2
JSON Field Style: snake_case
Time: RFC 3339 UTC
Character Set: UTF-8
```

请求和成功响应使用：

```http
Content-Type: application/json
```

错误响应使用：

```http
Content-Type: application/problem+json
```

SSE 使用 `text/event-stream`，文件下载使用实际 MIME 类型。

### 3.2 成功状态码

| 状态码 | 用途 |
| --- | --- |
| `200 OK` | 同步查询或同步 Command 成功 |
| `201 Created` | 资源已同步创建 |
| `202 Accepted` | Command 已持久化，后台继续处理 |
| `204 No Content` | 同步删除关系或退出登录成功 |
| `303 See Other` | 下载包已生成，跳转到短时签名地址 |

`202` 只表示命令已接受，不表示 Run、迁移、中断或生成已经完成。响应必须返回后续查询所需的业务资源引用。

### 3.3 列表与游标

持续增长的列表使用不透明游标，不使用页码：

```json
{
  "items": [],
  "next_cursor": null
}
```

- 消息游标内部对应 `(created_at, id)`。
- 变更、用户和项目列表使用各自稳定排序字段加 ID。
- `limit` 默认 50，最大 200。
- 客户端不得解析或拼装 Cursor。

### 3.4 请求关联

API 接受可选 `X-Request-ID`。缺失或格式不合格时由服务端生成。响应始终返回最终 `X-Request-ID`，并用于应用日志、问题响应和管理员诊断关联。

## 4. 认证、Session 与 CSRF

### 4.1 Session Cookie

登录成功后服务端设置随机不透明 Token：

```http
Set-Cookie: session=<token>; Path=/; HttpOnly; Secure; SameSite=Lax
```

Cookie 不设置浏览器持久化过期时间，是关闭浏览器后失效的 Session Cookie；Redis 中 `session:<token_hash>` 和 `user:<user_id>` 使用两小时滑动 TTL。每次通过认证的业务请求刷新两者 TTL，SSE 心跳不刷新。

### 4.2 CSRF

登录与 `GET /session` 返回 CSRF Token，React 只保存在内存。除安全只读请求外，客户端必须发送：

```http
X-CSRF-Token: <token>
```

服务端同时校验 Origin、CSRF Token 和 Fetch Metadata。Session Token、CSRF Token、密码、Salt 和 Hash 不进入普通响应或日志。

### 4.3 Session 接口

```text
POST   /session
GET    /session
DELETE /session
PUT    /me/password
```

登录请求：

```json
{
  "username": "admin",
  "password": "secret"
}
```

登录成功：

```json
{
  "user": {
    "id": "uuid",
    "username": "admin",
    "display_name": "管理员",
    "system_role": "ADMIN",
    "status": "ACTIVE",
    "must_change_password": false
  },
  "csrf_token": "random-token",
  "session_idle_expires_at": "2026-08-06T12:00:00Z"
}
```

修改密码请求：

```json
{
  "current_password": "old-secret",
  "new_password": "new-secret"
}
```

修改密码不撤销本端或其他端现有 Session。

## 5. 幂等设计

### 5.1 消息提交

每次新的消息提交由 React 生成 UUID，放在 Header：

```http
Idempotency-Key: 7aa4d156-987d-4f25-859d-6e954287c7a1
```

该值不是 Message ID。`project_message.id` 始终由服务端生成。Key 只在 `(project_id, user_id)` 范围内唯一，并随用户消息保存。

服务端对规范化请求计算 SHA-256 `request_hash`：

- 首次 Key：创建消息并返回回执。
- 相同 Key、相同 Hash：返回第一次回执，不重复创建助手消息或 Run。
- 相同 Key、不同 Hash：返回 `409 IDEMPOTENCY_KEY_REUSED`。
- 不同项目或不同用户使用相同 Key：互不冲突。

前端在用户发起一次操作时创建 Key；超时或连接中断重试必须复用原 Key；收到明确终态后，新操作生成新 Key。

### 5.2 其他 Command

- Gate 决议本身形成一条用户消息，因此同样使用 `Idempotency-Key`。
- 项目创建也使用 `Idempotency-Key`，保存在 `project.creation_idempotency_key`；真正 `project.id` 由服务端生成。
- Queue 取消、中断、重试、放弃和释放占用是目标状态幂等操作，重复请求返回当前结果。
- 成员 `PUT` 以目标表示幂等。
- Profile 发布使用当前版本、草稿 Hash 和迁移 Hash 的组合保证幂等。
- 阶段封存继续使用内部 `publish_key` 和确定性 Git Tag，不对浏览器暴露。

不建立通用幂等表，也不提供 `GET /commands/{id}`。后续状态通过 Message、Run、Stage、Gate 或 Profile 资源查询。

## 6. 并发控制

不引入全局 ETag 机制，按领域使用已有并发标识：

| 场景 | 并发标识 | 冲突结果 |
| --- | --- | --- |
| Profile 草稿编辑 | `expected_lock_version` | `409 PROFILE_DRAFT_VERSION_CONFLICT` |
| 当前 Run 操作 | `expected_run_id` | `409 RUN_ID_MISMATCH` |
| Gate 决议 | `expected_run_id + gate_id` | `409 HUMAN_GATE_MISMATCH` |
| Queue 取消 | Message 当前状态 | `409 MESSAGE_NOT_CANCELLABLE` |
| 项目内部真相提交 | `project.revision`，仅 PM/Worker 使用 | 内部重规划或失败 |
| 阶段内部提交 | `project_stage.revision`，仅 Worker 使用 | 内部重试或失效 |

前端查询到的 `allowed_actions` 只用于展示。每个 Command 仍在服务端重新校验账户、项目角色、占用、Run、Gate 和业务状态。

## 7. 错误模型

### 7.1 Problem Details

所有预期 HTTP 错误采用：

```json
{
  "type": "https://platform.example/problems/conversation-occupied",
  "title": "项目对话已被占用",
  "status": 423,
  "detail": "当前由其他项目成员操作",
  "code": "CONVERSATION_OCCUPIED",
  "instance": "/api/v2/projects/uuid/messages",
  "request_id": "uuid",
  "retryable": true,
  "context": {
    "owner_display_name": "张三",
    "expires_at": "2026-08-06T10:08:00Z"
  },
  "allowed_actions": ["WAIT"]
}
```

普通用户响应不得包含栈信息、数据库约束名、Prompt、Checkpoint、GitLab 内部地址、对象存储 Key 或模型供应商原始错误。

### 7.2 字段校验错误

```json
{
  "type": "https://platform.example/problems/validation-failed",
  "title": "请求字段校验失败",
  "status": 422,
  "code": "VALIDATION_FAILED",
  "detail": "请修正标记的字段",
  "request_id": "uuid",
  "retryable": false,
  "field_errors": [
    {
      "path": "content",
      "code": "REQUIRED",
      "message": "消息内容不能为空"
    }
  ]
}
```

### 7.3 状态码语义

| 状态码 | 语义 |
| --- | --- |
| `400` | HTTP 结构、JSON 或字段组合非法 |
| `401` | 未登录或 Redis Session 已过期 |
| `403` | 账户禁用或无操作权限 |
| `404` | 资源不存在或按权限隐藏存在性 |
| `409` | Run、Gate、Queue、版本或业务状态冲突 |
| `422` | 字段格式正确但业务输入无效 |
| `423` | 项目当前被其他用户占用 |
| `429` | 请求频率或容量限制 |
| `502` | 外部依赖返回无效结果 |
| `503` | GitLab、模型、Redis 或对象存储暂时不可用 |

稳定错误码至少包括：

```text
ACCOUNT_DISABLED
AUTHENTICATION_FAILED
CSRF_VALIDATION_FAILED
PROJECT_NOT_WRITABLE
CONVERSATION_OCCUPIED
CONVERSATION_RELEASE_NOT_ALLOWED
INVALID_DELIVERY_MODE
STEER_CONVERTED_TO_QUEUE
RUN_ID_MISMATCH
RUN_STATE_CONFLICT
RUN_STOPPING
RUN_FAILED_REQUIRES_RESOLUTION
MESSAGE_NOT_CANCELLABLE
IDEMPOTENCY_KEY_REUSED
HUMAN_GATE_NOT_ACTIVE
HUMAN_GATE_MISMATCH
HUMAN_GATE_ALREADY_RESOLVED
PROFILE_MIGRATION_FAILED
PROFILE_DRAFT_VERSION_CONFLICT
BASELINE_NOT_AVAILABLE
APPROVED_CONTENT_ONLY
EXTERNAL_SERVICE_UNAVAILABLE
```

## 8. 项目工作台投影

```text
GET /projects/{project_id}/workspace
```

这是 React 项目页的首屏 Query，不是新业务表。它从 PostgreSQL 当前投影和 Redis 占用组装：

```json
{
  "project": {
    "id": "uuid",
    "name": "订单履约平台",
    "description": "设计订单履约系统",
    "status": "ACTIVE",
    "revision": 12,
    "my_role": "OWNER"
  },
  "allowed_actions": [
    "SUBMIT_STEER",
    "SUBMIT_QUEUE",
    "INTERRUPT_RUN",
    "MANAGE_MEMBERS"
  ],
  "conversation": {
    "owner": {
      "user_id": "uuid",
      "display_name": "张三",
      "is_current_user": true
    },
    "expires_at": "2026-08-06T10:08:00Z",
    "allowed_delivery_modes": ["STEER", "QUEUE"],
    "can_release": false
  },
  "current_run": {
    "run_id": "uuid",
    "status": "RUNNING",
    "trigger_message_id": "uuid",
    "response_message_id": "uuid",
    "started_at": "2026-08-06T10:01:00Z",
    "updated_at": "2026-08-06T10:03:20Z"
  },
  "human_gate": null,
  "stages": [],
  "queue": {
    "count": 2
  },
  "artifact_summary": {
    "approved_count": 31,
    "draft_count": 12
  }
}
```

`workspace` 不返回完整消息、完整产物正文、Profile 身份或管理员诊断。详细内容由独立 Query 按需加载。

## 9. 项目与成员 API

### 9.1 项目

```text
GET  /projects
POST /projects
GET  /projects/{project_id}
GET  /projects/{project_id}/workspace
```

首发不提供宽泛的 `PATCH /projects/{id}`。项目事实、范围和业务要求通过消息、Gate 和变更流程修改，前端不得直接更新 `project.truth`、Profile、阶段、Run 或基线。

创建项目：

```http
Idempotency-Key: <client-generated-uuid>
```

```json
{
  "name": "订单履约平台",
  "description": "为直营业务设计订单履约系统",
  "initial_message": "需要覆盖创建订单、支付、履约和取消"
}
```

创建项目后服务端自动：创建项目与 OWNER 关系、匹配或使用通用 Profile、创建 GitLab 项目、创建各阶段初始行，并将首次消息路由给 PM。普通响应不暴露 Profile 选择过程或 GitLab 写凭据。

### 9.2 成员

```text
GET    /projects/{project_id}/members
PUT    /projects/{project_id}/members/{user_id}
DELETE /projects/{project_id}/members/{user_id}
```

成员表示：

```json
{
  "user_id": "uuid",
  "display_name": "李四",
  "role": "MEMBER"
}
```

`PUT` 用于新增或修改 `OWNER/MEMBER/VIEWER`。服务端保证项目至少存在一个 OWNER，并在 Run、Gate 和对话占用规则下判断是否允许变更。

## 10. 消息、Queue 与对话占用

### 10.1 消息 Query

```text
GET /projects/{project_id}/messages?cursor=&limit=
GET /projects/{project_id}/messages/{message_id}
```

普通消息响应不包含 `diagnostics`。助手消息可包含完整当前 `process` 和 `process_version`，用于刷新恢复。

### 10.2 提交消息

```text
POST /projects/{project_id}/messages
```

Header：

```http
Idempotency-Key: <uuid>
X-CSRF-Token: <token>
```

JSON 请求：

```json
{
  "content": "批量取消订单也需要记录操作原因",
  "delivery_mode": "STEER",
  "expected_run_id": "uuid"
}
```

规则：

- 空闲项目只允许 `DIRECT`。
- 活跃 Run 只允许当前对话用户提交 `STEER` 或 `QUEUE`。
- `STEER` 必须携带 `expected_run_id`。
- 错过安全边界或处于封存原子区的 `STEER` 由服务端转为 `QUEUE`，不能丢弃。
- `QUEUE` 不绑定当前 Run，按 `(created_at, id)` 执行。
- `STOPPING` 时拒绝新业务消息。
- 每次业务消息前自动尝试 Profile 迁移；迁移失败阻止写入，但不阻止读和下载。

返回 `202 Accepted`：

```json
{
  "message": {
    "id": "server-generated-uuid",
    "status": "QUEUED",
    "delivery_mode": "QUEUE",
    "target_run_id": null,
    "created_at": "2026-08-06T10:04:00Z"
  },
  "routing": {
    "requested_mode": "STEER",
    "effective_mode": "QUEUE",
    "conversion_reason": "ATOMIC_SECTION"
  },
  "current_run": {
    "run_id": "uuid",
    "status": "RUNNING"
  },
  "conversation": {
    "owner_user_id": "uuid",
    "expires_at": "2026-08-06T10:09:00Z"
  }
}
```

### 10.3 附件消息

带附件时使用同一路径的 `multipart/form-data` 变体：

- `metadata`：与 JSON 请求相同的结构。
- `files[]`：附件流。
- `Idempotency-Key`：仍为必填。

服务端负责消息 ID、文件安全校验、Hash、对象存储和 `project_file` 绑定。客户端不能传对象存储 Key。重试时同一 Key 必须携带相同 metadata 和附件集合，否则返回幂等冲突。

### 10.4 取消 Queue

```text
POST /projects/{project_id}/messages/{message_id}/cancellations
```

提交者可以取消自己的待执行 Queue，OWNER 可以取消任何待执行 Queue。已经被 Worker 启动的消息不能取消，只能按权限中断当前 Run。成功后原 Message 保留并变为 `CANCELLED`。

### 10.5 释放对话占用

```text
POST /projects/{project_id}/conversation-releases
```

仅当前对话用户、当前无活动 Run 且 Queue 为空时成功。页面关闭、断网和退出登录均不调用此接口，也不自动释放占用。

## 11. 当前 Run 与人工 Gate

### 11.1 Current Run

```text
GET /projects/{project_id}/run
```

每项目只返回一个当前 Run，不提供 Run 历史列表。历史过程从项目消息查看。

### 11.2 中断

```text
POST /projects/{project_id}/run/interruptions
```

```json
{
  "expected_run_id": "uuid"
}
```

返回 `202`：

```json
{
  "run_id": "uuid",
  "status": "STOPPING",
  "stop_mode": "AT_NEXT_SAFE_CHECKPOINT"
}
```

该响应只表示中断请求已登记。最终 `INTERRUPTED` 通过 Message、Run 和 SSE 获知。中断必须完成当前封存原子区、取消待执行 Queue、保留并退回当前 Run 草稿、清理 Checkpoint；客户端不能逐步调用这些动作。

当前对话用户可以中断自己的 Run。OWNER 可强制中断 MEMBER 的 Run；安全停止后对话占用原子转交该 OWNER。

### 11.3 失败恢复

```text
POST /projects/{project_id}/run/retries
POST /projects/{project_id}/run/abandonments
```

两个请求都必须携带 `expected_run_id`。只有 `FAILED` Run 可重试或放弃；`INTERRUPTED` 不能恢复。

### 11.4 Human Gate

```text
GET  /projects/{project_id}/human-gate
POST /projects/{project_id}/human-gate/decisions
```

Gate 是当前 Run/Checkpoint 的只读投影，不新增 Gate 表。决议请求：

```json
{
  "expected_run_id": "uuid",
  "gate_id": "opaque-gate-id",
  "decision": "APPROVE",
  "selected_option": null,
  "comment": "范围确认无误"
}
```

Header 必须携带 `Idempotency-Key`，该决议同时生成共享时间线中的用户消息。三个固定校准点和临时决策升级共用此接口，但 `allowed_decisions` 由当前 Gate 返回，客户端不能提交集合外值。

项目 MEMBER 的对话占用在 OWNER-only Gate 自动释放。OWNER 决议可绕过 MEMBER 占用，但仍必须校验 Run 和 Gate 身份。

## 12. 阶段、候选与质量结果

```text
GET /projects/{project_id}/stages
GET /projects/{project_id}/stages/{stage}
GET /projects/{project_id}/stages/{stage}/drafts
GET /projects/{project_id}/stages/{stage}/quality-findings
```

阶段响应直接返回全部阶段行，不能压缩成一个 `current_stage`。API、DATABASE 和 TEST 等可同时 `BUILDING`。

候选工作区只读展示当前 `artifact_draft`。普通用户不能直接 PATCH 草稿、设置校验结果或封存阶段；意见通过消息进入 PM/Graph。质量发现来自当前候选的 `validation/review` 投影，不建立独立 Finding 历史表。

禁止公开：

```text
POST  /runs
PATCH /runs/{id}/status
POST  /stages/{stage}/seal
PATCH /stages/{stage}/status
POST  /artifacts
PATCH /artifacts/{id}/approval-status
POST  /git/commits
POST  /graph/nodes/{node}/execute
```

## 13. 批准产物、基线与下载

### 13.1 当前批准产物

```text
GET /projects/{project_id}/artifacts?stage=&artifact_type=&cursor=&limit=
GET /projects/{project_id}/artifacts/{artifact_code}
GET /projects/{project_id}/artifacts/{artifact_code}/content?format=yaml|markdown
```

当前批准列表可以从 PostgreSQL `artifact` 投影读取。正文必须按当前阶段基线 Commit/Tag 读取 Git，不能读取可能变化的草稿。

### 13.2 基线历史与差异

```text
GET /projects/{project_id}/baselines?stage=
GET /projects/{project_id}/baselines/{stage}/{version}
GET /projects/{project_id}/baselines/{stage}/{version}/artifacts/{artifact_code}
GET /projects/{project_id}/baseline-diffs?stage=&from_version=&to_version=
```

历史基线列表、文件树、内容和 Diff 从内部 GitLab Commit/Tag 读取，不要求 PostgreSQL 保存历史 Artifact 或 Manifest。

### 13.3 下载

```text
GET /projects/{project_id}/baselines/{stage}/{version}/download
GET /projects/{project_id}/approved-package
```

- 只允许下载批准基线，VIEWER 也可下载。
- 下载包不包含草稿、附件原件、Prompt、诊断或 Checkpoint。
- 完整包开始生成前固定所有目标 Stage 的 Commit/Tag，避免跨版本混读。
- 小包可直接流式返回 ZIP；大包可返回短期签名地址。
- 短期票据放 Redis 或对象存储，不新增永久导出任务表。
- 用户不直接接触 GitLab URL、凭据或写能力。

## 14. 项目变更

```text
GET  /projects/{project_id}/changes?cursor=&limit=
GET  /projects/{project_id}/changes/{change_id}
POST /projects/{project_id}/changes/{change_id}/decisions
POST /projects/{project_id}/changes/{change_id}/retries
```

变更请求由 PM 从项目消息识别并创建，不同时维护另一套普通用户变更表单入口。决议请求必须携带当前 `expected_status`，允许值由 Change Query 返回。批准、拒绝或撤回的永久决议写入 Git；PostgreSQL只保留当前处理投影和 Git 指针。

## 15. 管理员用户 API

```text
GET   /admin/users?cursor=&limit=&status=
POST  /admin/users
GET   /admin/users/{user_id}
PATCH /admin/users/{user_id}
PUT   /admin/users/{user_id}/password
```

`PATCH` 只允许修改 `display_name`、`system_role` 和 `status`，不能提交密码 Hash、Salt 或 Session。禁用更新数据库与 Redis 用户状态但不删除 Session；重新启用后未过期 Session 无需重新登录。

管理员设置密码不建立密码重置表。用户自己的密码修改仍使用 `PUT /me/password`。

## 16. 管理员 Domain Profile API

```text
GET    /admin/domain-profiles
POST   /admin/domain-profiles
GET    /admin/domain-profiles/{profile_id}
PATCH  /admin/domain-profiles/{profile_id}

GET    /admin/domain-profiles/{profile_id}/draft
PUT    /admin/domain-profiles/{profile_id}/draft
POST   /admin/domain-profiles/{profile_id}/draft-validations
POST   /admin/domain-profiles/{profile_id}/publications

GET    /admin/domain-profiles/{profile_id}/versions
GET    /admin/domain-profiles/{profile_id}/versions/{version}
GET    /admin/domain-profiles/{profile_id}/migrations
PUT    /admin/domain-profiles/{profile_id}/migrations/{from_version}

POST   /admin/projects/{project_id}/profile-migration-retries
```

普通项目 API 不返回 Profile 名称、候选列表、版本或匹配过程。PM 在项目内部自动选择 Profile。

### 16.1 草稿乐观锁

```json
{
  "expected_lock_version": 8,
  "content": {}
}
```

成功响应返回 `lock_version: 9` 和新的 `content_hash`。版本不匹配返回 `409 PROFILE_DRAFT_VERSION_CONFLICT`。不再为 Profile 引入 ETag 或另一套 Revision。

### 16.2 发布与迁移

发布请求：

```json
{
  "expected_current_version": 4,
  "expected_draft_hash": "sha256",
  "migration": {
    "from_version": 4,
    "rule": {},
    "expected_rule_hash": "sha256"
  }
}
```

只能发布连续整数版本。迁移规则可以直接修正，项目每次新对话仍自动尝试迁移；管理员重试不替代自动迁移。

## 17. 管理员模型与诊断 API

```text
GET   /admin/model-profiles
POST  /admin/model-profiles
GET   /admin/model-profiles/{model_profile_id}
PATCH /admin/model-profiles/{model_profile_id}

GET /admin/projects/{project_id}/messages/{message_id}/diagnostics
```

模型配置只接收和返回 Secret 引用，不返回真实 API Key。诊断接口只供 ADMIN，返回脱敏后的模型 Profile、Provider、参数摘要、Prompt Hash、Schema Hash、Token、成本、耗时和重试；不返回完整 Prompt 或供应商密钥。

## 18. SSE 契约

### 18.1 连接

```text
GET /projects/{project_id}/events
Accept: text/event-stream
Last-Event-ID: <opaque-cursor>
```

连接使用 Session Cookie 鉴权。SSE 心跳不刷新登录 Session、用户缓存或项目对话占用。

### 18.2 事件类型

```text
project.sync
message.created
message.status.changed
message.process.appended
run.status.changed
human_gate.changed
stage.changed
artifact.changed
queue.changed
conversation.changed
resync.required
```

过程增量示例：

```text
id: message-uuid:36
event: message.process.appended
data: {
  "project_id": "uuid",
  "message_id": "uuid",
  "process_version": 36,
  "process_event": {
    "event_id": "uuid",
    "type": "VALIDATION_COMPLETED",
    "stage": "API",
    "agent_role": "VALIDATOR",
    "summary": "发现 2 个字段语义不一致",
    "occurred_at": "2026-08-06T10:05:00Z"
  }
}
```

### 18.3 重连

1. API 从 PostgreSQL 读取权威消息、当前 Run、阶段和 Gate 投影。
2. 对活动助手消息比较客户端游标与 `process_version`。
3. 能证明连续时，从已持久化 `process[]` 补发缺口。
4. 不能证明连续或非过程资源可能遗漏时，发送 `resync.required`。
5. React 重新查询 `workspace`、消息页或具体资源。
6. 完成同步后订阅 Redis Pub/Sub 在线通知。

不建立 SSE 事件历史表，也不使用全局 Sequence。Redis 通知丢失不影响项目真相和最终一致性。

## 19. 权限摘要

| 能力 | OWNER | MEMBER | VIEWER | ADMIN 治理接口 |
| --- | --- | --- | --- | --- |
| 查看项目、时间线、阶段 | 是 | 是 | 是 | 按授权 |
| 下载批准基线 | 是 | 是 | 是 | 按授权 |
| 提交项目消息 | 是 | 是 | 否 | 否 |
| 取得普通对话占用 | 是 | 是 | 否 | 否 |
| 三个固定 Gate 决议 | 是 | 否 | 否 | 否 |
| 取消自己的 Queue | 是 | 是 | 否 | 否 |
| 取消任意 Queue | 是 | 否 | 否 | 否 |
| 中断自己的 Run | 是 | 是 | 否 | 否 |
| 强制中断并接管 | 是 | 否 | 否 | 否 |
| 管理项目成员 | 是 | 否 | 否 | 否 |
| 管理用户、Profile、模型 | 否 | 否 | 否 | 是 |

ADMIN 不自动拥有所有项目业务决策权。系统治理权限与项目角色分别校验。

## 20. OpenAPI 与前端约束

- FastAPI 生成的 OpenAPI 必须包含稳定 `operationId`，供 React Client 代码生成。
- 状态、角色、阶段、错误码和动作使用枚举 Schema，不使用无约束字符串。
- Problem Details 为所有非 2xx 响应的统一 Schema。
- `workspace.allowed_actions` 只控制按钮提示，不能代替服务端授权。
- React Query 缓存建议按 `workspace/messages/artifacts/changes` 分离。
- SSE 收到资源变化时精确更新过程或使对应 Query 失效，不在浏览器维护 Graph 副本。
- 前端不得自动重试非幂等写操作；消息只允许带原 `Idempotency-Key` 重试。

## 21. 完整接口参数契约

本节是 OpenAPI 实现输入。每个公开接口必须出现在下表中，并明确请求参数、请求体、成功响应和错误响应。表中的 Schema 字段在 21.16—21.20 定义；引用 Schema 不是省略字段，而是避免重复定义后产生漂移。

通用规则：

- 除登录外，所有接口都需要 Session Cookie；SSE 同样通过 Cookie 鉴权。所有非 `GET` 请求还需要 `X-CSRF-Token`。
- `POST /projects`、`POST /projects/{id}/messages`、Gate 决议和 Change 决议需要 UUID 格式的 `Idempotency-Key`。
- 所有 UUID Path 参数均为必填；不存在或不可见统一返回 `404`。
- 所有非 2xx 响应都是 `ProblemDetails`；字段错误额外返回 `field_errors[]`。
- 下表中的 `—` 表示该位置没有参数，不表示可以传任意字段；未声明字段由服务端拒绝。

### 21.1 Session 与本人账户

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `createSession` | `POST /session` | `X-CSRF-Token` 不需要 | — | `LoginRequest` | `200 SessionView` + `Set-Cookie` |
| `getSession` | `GET /session` | Session Cookie | — | — | `200 SessionView` |
| `deleteSession` | `DELETE /session` | Session Cookie、CSRF | — | — | `204` |
| `changeMyPassword` | `PUT /me/password` | Session Cookie、CSRF | — | `ChangePasswordRequest` | `200 ActionResult` |

`LoginRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `username` | string | 是 | 1—100 字符，服务端不区分大小写查找 |
| `password` | string | 是 | 原始密码，只在 TLS 请求体出现 |

`ChangePasswordRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `current_password` | string | 是 | 当前密码 |
| `new_password` | string | 是 | 满足当前密码策略，不能与当前密码相同 |

### 21.2 项目

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listProjects` | `GET /projects` | Session Cookie | Query：`cursor? string`、`limit? int=50`、`status? ProjectStatus` | — | `200 ProjectPage` |
| `createProject` | `POST /projects` | Session Cookie、CSRF、`Idempotency-Key` | — | `CreateProjectRequest` | `202 ProjectCreateReceipt` |
| `getProject` | `GET /projects/{project_id}` | Session Cookie | Path：`project_id uuid` | — | `200 ProjectView` |
| `getProjectWorkspace` | `GET /projects/{project_id}/workspace` | Session Cookie | Path：`project_id uuid` | — | `200 WorkspaceView` |

`CreateProjectRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `name` | string | 是 | 1—255 字符 |
| `description` | string/null | 否 | 创建背景，最大长度由配置限制 |
| `initial_message` | string | 是 | PM 首次接收的项目目标和上下文，不能为空 |

`ProjectCreateReceipt`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `project` | `ProjectView` | 是 | 已落库项目 |
| `initial_message` | `MessageView` | 是 | 服务端生成 ID 的首条用户消息 |
| `response_message_id` | uuid | 是 | 对应助手消息 |
| `run` | `RunView` | 是 | 已排队的当前 Run |
| `repository_status` | enum | 是 | `PENDING/READY/FAILED`；不暴露 GitLab 地址 |

### 21.3 项目成员

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listProjectMembers` | `GET /projects/{project_id}/members` | Session Cookie | Path：`project_id uuid` | — | `200 MemberView[]` |
| `putProjectMember` | `PUT /projects/{project_id}/members/{user_id}` | Session Cookie、CSRF | Path：`project_id uuid`、`user_id uuid` | `PutMemberRequest` | `200 MemberView` |
| `deleteProjectMember` | `DELETE /projects/{project_id}/members/{user_id}` | Session Cookie、CSRF | Path：`project_id uuid`、`user_id uuid` | — | `204` |

`PutMemberRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `role` | enum | 是 | `OWNER/MEMBER/VIEWER` |

### 21.4 消息、Queue 与占用

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listProjectMessages` | `GET /projects/{project_id}/messages` | Session Cookie | Path：`project_id uuid`；Query：`cursor? string`、`limit? int=50` | — | `200 MessagePage` |
| `getProjectMessage` | `GET /projects/{project_id}/messages/{message_id}` | Session Cookie | Path：`project_id uuid`、`message_id uuid` | — | `200 MessageView` |
| `submitProjectMessage` | `POST /projects/{project_id}/messages` | Session Cookie、CSRF、`Idempotency-Key` | Path：`project_id uuid` | `SubmitMessageRequest` 或 multipart | `202 MessageReceipt` |
| `cancelQueuedMessage` | `POST /projects/{project_id}/messages/{message_id}/cancellations` | Session Cookie、CSRF | Path：`project_id uuid`、`message_id uuid` | — | `200 MessageView` |
| `releaseConversation` | `POST /projects/{project_id}/conversation-releases` | Session Cookie、CSRF | Path：`project_id uuid` | — | `200 ConversationView` |

`SubmitMessageRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `content` | string | 是 | 用户输入，去除首尾空白后不能为空 |
| `delivery_mode` | enum | 是 | `DIRECT/STEER/QUEUE` |
| `expected_run_id` | uuid/null | 条件 | `STEER` 必填；`DIRECT/QUEUE` 为空 |

Multipart 请求：

| Part | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `metadata` | JSON `SubmitMessageRequest` | 是 | 与纯 JSON 请求一致 |
| `files[]` | binary | 是 | 至少一个；逐文件校验名称、大小、MIME 和 Hash |

`MessageReceipt`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `message` | `MessageView` | 是 | 已持久化用户消息 |
| `response_message_id` | uuid/null | 否 | DIRECT 启动 Run 时创建的助手消息；STEER/QUEUE 可为空 |
| `routing` | `RoutingView` | 是 | 请求模式、实际模式和转换原因 |
| `current_run` | `RunView/null` | 否 | 当前 Run 快照 |
| `conversation` | `ConversationView` | 是 | 当前占用投影 |

### 21.5 Current Run

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `getCurrentRun` | `GET /projects/{project_id}/run` | Session Cookie | Path：`project_id uuid` | — | `200 RunView`；无 Run 时 `404` |
| `interruptCurrentRun` | `POST /projects/{project_id}/run/interruptions` | Session Cookie、CSRF | Path：`project_id uuid` | `ExpectedRunRequest` | `202 RunActionReceipt` |
| `retryCurrentRun` | `POST /projects/{project_id}/run/retries` | Session Cookie、CSRF | Path：`project_id uuid` | `ExpectedRunRequest` | `202 RunActionReceipt` |
| `abandonCurrentRun` | `POST /projects/{project_id}/run/abandonments` | Session Cookie、CSRF | Path：`project_id uuid` | `ExpectedRunRequest` | `200 RunActionReceipt` |

`ExpectedRunRequest`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `expected_run_id` | uuid | 是 | 用户页面所见 Run；不匹配时拒绝操作新 Run |

`RunActionReceipt`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `run_id` | uuid | 是 | 被操作 Run |
| `status` | `RunStatus` | 是 | 接口提交后的当前状态 |
| `response_message_id` | uuid | 是 | 用户可查看过程和终态的助手消息 |
| `accepted_at` | datetime | 是 | 服务端接受时间 |
| `stop_mode` | enum/null | 否 | 中断时为 `AT_NEXT_SAFE_CHECKPOINT` |

### 21.6 Human Gate

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `getHumanGate` | `GET /projects/{project_id}/human-gate` | Session Cookie | Path：`project_id uuid` | — | `200 HumanGateView`；无 Gate 时 `404` |
| `decideHumanGate` | `POST /projects/{project_id}/human-gate/decisions` | Session Cookie、CSRF、`Idempotency-Key` | Path：`project_id uuid` | `HumanGateDecisionRequest` | `202 HumanGateDecisionReceipt` |

`HumanGateDecisionRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `expected_run_id` | uuid | 是 | 当前等待 Run |
| `gate_id` | string | 是 | GET Gate 返回的不透明标识 |
| `decision` | string | 是 | 必须属于 Gate 的 `allowed_decisions` |
| `selected_option` | string/null | 条件 | Gate 要求选择方案时必填 |
| `comment` | string/null | 否 | OWNER 补充说明 |

`HumanGateDecisionReceipt`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `decision_message` | `MessageView` | 是 | 写入共享时间线的决议消息 |
| `gate_id` | string | 是 | 被处理 Gate |
| `decision` | string | 是 | 实际接受的决议 |
| `run` | `RunView` | 是 | 恢复排队或运行后的 Run |

### 21.7 阶段、草稿与质量发现

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listProjectStages` | `GET /projects/{project_id}/stages` | Session Cookie | Path：`project_id uuid` | — | `200 StageView[]` |
| `getProjectStage` | `GET /projects/{project_id}/stages/{stage}` | Session Cookie | Path：`project_id uuid`、`stage StageCode` | — | `200 StageView` |
| `listStageDrafts` | `GET /projects/{project_id}/stages/{stage}/drafts` | Session Cookie | Path：`project_id uuid`、`stage StageCode`；Query：`artifact_type? string` | — | `200 ArtifactDraftView[]` |
| `listStageQualityFindings` | `GET /projects/{project_id}/stages/{stage}/quality-findings` | Session Cookie | Path：`project_id uuid`、`stage StageCode`；Query：`severity? enum`、`status? enum` | — | `200 QualityFindingView[]` |

### 21.8 当前批准产物

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listArtifacts` | `GET /projects/{project_id}/artifacts` | Session Cookie | Path：`project_id uuid`；Query：`stage? StageCode`、`artifact_type? string`、`cursor? string`、`limit? int=50` | — | `200 ArtifactPage` |
| `getArtifact` | `GET /projects/{project_id}/artifacts/{artifact_code}` | Session Cookie | Path：`project_id uuid`、`artifact_code string` | — | `200 ArtifactView` |
| `getArtifactContent` | `GET /projects/{project_id}/artifacts/{artifact_code}/content` | Session Cookie | Path：`project_id uuid`、`artifact_code string`；Query：`format yaml/markdown` | — | `200 text/yaml` 或 `text/markdown` |

### 21.9 基线、Diff 与下载

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listBaselines` | `GET /projects/{project_id}/baselines` | Session Cookie | Path：`project_id uuid`；Query：`stage? StageCode`、`cursor? string`、`limit? int=50` | — | `200 BaselinePage` |
| `getBaseline` | `GET /projects/{project_id}/baselines/{stage}/{version}` | Session Cookie | Path：`project_id uuid`、`stage StageCode`、`version int>=1` | — | `200 BaselineView` |
| `getBaselineArtifact` | `GET /projects/{project_id}/baselines/{stage}/{version}/artifacts/{artifact_code}` | Session Cookie | Path：项目、阶段、版本、产物代码；Query：`format yaml/markdown` | — | `200 text/yaml` 或 `text/markdown` |
| `getBaselineDiff` | `GET /projects/{project_id}/baseline-diffs` | Session Cookie | Path：`project_id uuid`；Query：`stage StageCode`、`from_version int`、`to_version int`、`format? summary/unified=summary` | — | `200 BaselineDiffView` |
| `downloadBaseline` | `GET /projects/{project_id}/baselines/{stage}/{version}/download` | Session Cookie | Path：项目、阶段、版本 | — | `200 application/zip` 或 `303` |
| `downloadApprovedPackage` | `GET /projects/{project_id}/approved-package` | Session Cookie | Path：`project_id uuid`；Query：`stages? StageCode[]`，缺省为全部已封存阶段 | — | `200 application/zip` 或 `303` |

二进制下载响应 Header：

| Header | 必填 | 含义 |
| --- | --- | --- |
| `Content-Type` | 是 | `application/zip` |
| `Content-Disposition` | 是 | 安全的 UTF-8 下载文件名 |
| `ETag` | 是 | 仅用于下载缓存校验，由固定 Git Commit 集合计算；不用于写并发 |
| `Digest` | 是 | 包文件内容摘要 |

### 21.10 项目变更

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listProjectChanges` | `GET /projects/{project_id}/changes` | Session Cookie | Path：`project_id uuid`；Query：`cursor?`、`limit?`、`status? ChangeStatus` | — | `200 ChangePage` |
| `getProjectChange` | `GET /projects/{project_id}/changes/{change_id}` | Session Cookie | Path：`project_id uuid`、`change_id uuid` | — | `200 ChangeView` |
| `decideProjectChange` | `POST /projects/{project_id}/changes/{change_id}/decisions` | Session Cookie、CSRF、`Idempotency-Key` | Path：项目、变更 ID | `ChangeDecisionRequest` | `202 ChangeActionReceipt` |
| `retryProjectChange` | `POST /projects/{project_id}/changes/{change_id}/retries` | Session Cookie、CSRF | Path：项目、变更 ID | `ExpectedChangeStatusRequest` | `202 ChangeActionReceipt` |

`ChangeDecisionRequest`：

| 字段 | 类型 | 必填 | 规则/含义 |
| --- | --- | --- | --- |
| `expected_status` | `ChangeStatus` | 是 | 防止处理已变化的变更 |
| `decision` | enum | 是 | `APPROVE/REJECT/WITHDRAW`，需属于允许集合 |
| `comment` | string/null | 否 | 决议说明 |

`ExpectedChangeStatusRequest`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `expected_status` | `ChangeStatus` | 是 | 只允许重试指定失败状态 |

### 21.11 管理员用户

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listUsers` | `GET /admin/users` | ADMIN Session | Query：`cursor?`、`limit?`、`status? UserStatus`、`q? string` | — | `200 UserPage` |
| `createUser` | `POST /admin/users` | ADMIN Session、CSRF | — | `CreateUserRequest` | `201 UserView` |
| `getUser` | `GET /admin/users/{user_id}` | ADMIN Session | Path：`user_id uuid` | — | `200 UserView` |
| `updateUser` | `PATCH /admin/users/{user_id}` | ADMIN Session、CSRF | Path：`user_id uuid` | `UpdateUserRequest` | `200 UserView` |
| `setUserPassword` | `PUT /admin/users/{user_id}/password` | ADMIN Session、CSRF | Path：`user_id uuid` | `SetUserPasswordRequest` | `200 ActionResult` |

| Schema 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `CreateUserRequest.username` | string | 是 | 唯一登录名 |
| `CreateUserRequest.display_name` | string | 是 | 显示名 |
| `CreateUserRequest.temporary_password` | string | 是 | 临时密码 |
| `CreateUserRequest.system_role` | enum | 是 | `ADMIN/USER` |
| `UpdateUserRequest.display_name` | string | 否 | 至少提交一个允许字段 |
| `UpdateUserRequest.system_role` | enum | 否 | `ADMIN/USER` |
| `UpdateUserRequest.status` | enum | 否 | `ACTIVE/DISABLED` |
| `SetUserPasswordRequest.new_password` | string | 是 | 新临时密码 |
| `SetUserPasswordRequest.must_change_password` | boolean | 是 | 是否要求下次交互前修改 |

### 21.12 管理员 Domain Profile

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listDomainProfiles` | `GET /admin/domain-profiles` | ADMIN Session | Query：`cursor?`、`limit?`、`status?`、`q?` | — | `200 DomainProfilePage` |
| `createDomainProfile` | `POST /admin/domain-profiles` | ADMIN Session、CSRF | — | `CreateDomainProfileRequest` | `201 DomainProfileView` |
| `getDomainProfile` | `GET /admin/domain-profiles/{profile_id}` | ADMIN Session | Path：`profile_id uuid` | — | `200 DomainProfileView` |
| `updateDomainProfile` | `PATCH /admin/domain-profiles/{profile_id}` | ADMIN Session、CSRF | Path：`profile_id uuid` | `UpdateDomainProfileRequest` | `200 DomainProfileView` |
| `getDomainProfileDraft` | `GET /admin/domain-profiles/{profile_id}/draft` | ADMIN Session | Path：`profile_id uuid` | — | `200 DomainProfileDraftView` |
| `putDomainProfileDraft` | `PUT /admin/domain-profiles/{profile_id}/draft` | ADMIN Session、CSRF | Path：`profile_id uuid` | `PutDomainProfileDraftRequest` | `200 DomainProfileDraftView` |
| `validateDomainProfileDraft` | `POST /admin/domain-profiles/{profile_id}/draft-validations` | ADMIN Session、CSRF | Path：`profile_id uuid` | `ProfileDraftValidationRequest` | `200 ProfileValidationReport` |
| `publishDomainProfile` | `POST /admin/domain-profiles/{profile_id}/publications` | ADMIN Session、CSRF | Path：`profile_id uuid` | `PublishDomainProfileRequest` | `201 DomainProfileVersionView` |
| `listDomainProfileVersions` | `GET /admin/domain-profiles/{profile_id}/versions` | ADMIN Session | Path：`profile_id uuid`；Query：`cursor?`、`limit?` | — | `200 DomainProfileVersionPage` |
| `getDomainProfileVersion` | `GET /admin/domain-profiles/{profile_id}/versions/{version}` | ADMIN Session | Path：`profile_id uuid`、`version int>=1` | — | `200 DomainProfileVersionView` |
| `listProfileMigrations` | `GET /admin/domain-profiles/{profile_id}/migrations` | ADMIN Session | Path：`profile_id uuid` | — | `200 ProfileMigrationView[]` |
| `putProfileMigration` | `PUT /admin/domain-profiles/{profile_id}/migrations/{from_version}` | ADMIN Session、CSRF | Path：`profile_id uuid`、`from_version int>=1` | `PutProfileMigrationRequest` | `200 ProfileMigrationView` |
| `retryProjectProfileMigration` | `POST /admin/projects/{project_id}/profile-migration-retries` | ADMIN Session、CSRF | Path：`project_id uuid` | — | `202 ProfileMigrationRetryReceipt` |

Profile 请求字段：

| Schema 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `CreateDomainProfileRequest.code` | string | 是 | 稳定唯一代码 |
| `CreateDomainProfileRequest.name` | string | 是 | 管理端名称 |
| `CreateDomainProfileRequest.description` | string/null | 否 | 管理说明 |
| `UpdateDomainProfileRequest.name` | string | 否 | 至少提交一个允许字段 |
| `UpdateDomainProfileRequest.description` | string/null | 否 | 管理说明 |
| `UpdateDomainProfileRequest.status` | enum | 否 | `ACTIVE/INACTIVE` |
| `PutDomainProfileDraftRequest.expected_lock_version` | integer | 是 | 当前草稿乐观锁版本 |
| `PutDomainProfileDraftRequest.content` | object | 是 | 完整 Profile 草稿 |
| `ProfileDraftValidationRequest.expected_lock_version` | integer | 是 | 要验证的草稿版本 |
| `PublishDomainProfileRequest.expected_current_version` | integer | 是 | 当前发布版本，首次发布为 0 |
| `PublishDomainProfileRequest.expected_draft_hash` | sha256 | 是 | 已验证草稿 Hash |
| `PublishDomainProfileRequest.migration` | `MigrationInput/null` | 条件 | 版本大于 1 时必填 |
| `PutProfileMigrationRequest.to_version` | integer | 是 | 必须等于 `from_version + 1` |
| `PutProfileMigrationRequest.rule` | object | 是 | 当前相邻升级规则 |
| `PutProfileMigrationRequest.expected_rule_hash` | sha256/null | 否 | 修改已有规则时的并发条件 |

`MigrationInput` 字段为 `from_version integer`、`to_version integer`、`rule object`、`expected_rule_hash sha256/null`。

### 21.13 管理员模型配置与诊断

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `listModelProfiles` | `GET /admin/model-profiles` | ADMIN Session | Query：`cursor?`、`limit?`、`purpose?`、`status?` | — | `200 ModelProfilePage` |
| `createModelProfile` | `POST /admin/model-profiles` | ADMIN Session、CSRF | — | `CreateModelProfileRequest` | `201 ModelProfileView` |
| `getModelProfile` | `GET /admin/model-profiles/{model_profile_id}` | ADMIN Session | Path：`model_profile_id uuid` | — | `200 ModelProfileView` |
| `updateModelProfile` | `PATCH /admin/model-profiles/{model_profile_id}` | ADMIN Session、CSRF | Path：`model_profile_id uuid` | `UpdateModelProfileRequest` | `200 ModelProfileView` |
| `getMessageDiagnostics` | `GET /admin/projects/{project_id}/messages/{message_id}/diagnostics` | ADMIN Session | Path：`project_id uuid`、`message_id uuid` | — | `200 DiagnosticEntry[]` |

模型配置请求字段：

| Schema 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `CreateModelProfileRequest.code` | string | 是 | 稳定唯一代码 |
| `CreateModelProfileRequest.name` | string | 是 | 管理端名称 |
| `CreateModelProfileRequest.purpose` | string | 是 | 阶段或用途代码 |
| `CreateModelProfileRequest.provider` | string | 是 | Provider Adapter 代码 |
| `CreateModelProfileRequest.model_name` | string | 是 | 供应商模型标识 |
| `CreateModelProfileRequest.parameters` | object | 是 | 温度、输出限制等白名单参数 |
| `CreateModelProfileRequest.secret_ref` | string | 是 | Secret 标识，不是密钥值 |
| `CreateModelProfileRequest.is_default` | boolean | 是 | 是否为该用途默认配置 |
| `UpdateModelProfileRequest.name` | string | 否 | 至少提交一个允许字段 |
| `UpdateModelProfileRequest.purpose` | string | 否 | 新用途代码；需重新校验默认项 |
| `UpdateModelProfileRequest.provider` | string | 否 | 新 Provider Adapter 代码 |
| `UpdateModelProfileRequest.model_name` | string | 否 | 新供应商模型标识 |
| `UpdateModelProfileRequest.parameters` | object | 否 | 完整替换参数集合 |
| `UpdateModelProfileRequest.secret_ref` | string | 否 | 新 Secret 标识 |
| `UpdateModelProfileRequest.is_default` | boolean | 否 | 默认切换需事务保证唯一 |
| `UpdateModelProfileRequest.status` | enum | 否 | `ACTIVE/INACTIVE` |

### 21.14 SSE

| operationId | 方法与路径 | Request Header | Path/Query | Request Body | 成功响应 |
| --- | --- | --- | --- | --- | --- |
| `subscribeProjectEvents` | `GET /projects/{project_id}/events` | Session Cookie、`Accept: text/event-stream`、`Last-Event-ID?` | Path：`project_id uuid` | — | `200 text/event-stream` |

SSE `data` 公共外壳：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 |
| `resource_type` | string | 是 | `message/run/stage/artifact/gate/conversation/project` |
| `resource_id` | string | 是 | 资源稳定 ID 或阶段代码 |
| `version` | integer/null | 否 | Message Process Version 或资源修订号 |
| `occurred_at` | datetime | 是 | 事件形成时间 |
| `data` | object | 是 | 事件类型对应的轻量增量 |

### 21.15 公共枚举

| Schema | 值 |
| --- | --- |
| `ProjectStatus` | `ACTIVE/REBASELINING/BLOCKED/COMPLETED/ARCHIVED` |
| `UserStatus` | `ACTIVE/DISABLED` |
| `RunStatus` | `QUEUED/PREPARING/MIGRATING/RUNNING/WAITING_FOR_HUMAN/STOPPING/COMPLETED/FAILED/CANCELLED/INTERRUPTED` |
| `MessageStatus` | `PENDING/QUEUED/RUNNING/WAITING_FOR_HUMAN/COMPLETED/FAILED/FAILED_BEFORE_PROCESSING/CANCELLED/INTERRUPTED` |
| `StageCode` | `PROJECT_CHARTER/REQUIREMENT_OUTLINE/REQUIREMENT_MODULE/PRD/ARCHITECTURE/SYSTEM_MODULE/API/DATABASE/TEST` |
| `StageStatus` | `NOT_STARTED/BUILDING/WAITING_FOR_HUMAN/SEALING/SEALED/SEAL_FAILED/INVALIDATED` |
| `ChangeStatus` | `PROPOSED/ANALYZING/WAITING_FOR_HUMAN/APPROVED/APPLYING/APPLIED/REJECTED/WITHDRAWN/FAILED` |

### 21.16 公共用户、项目与成员响应

`UserView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 用户 ID |
| `username` | string | 是 | 登录名 |
| `display_name` | string | 是 | 显示名 |
| `system_role` | enum | 是 | `ADMIN/USER` |
| `status` | `UserStatus` | 是 | 用户状态 |
| `must_change_password` | boolean | 是 | 是否必须修改密码 |
| `last_login_at` | datetime/null | 否 | 最近成功登录 |
| `created_at` | datetime | 是 | 创建时间 |

`SessionView` 由 `user UserView`、`csrf_token string`、`session_idle_expires_at datetime` 组成。

`ProjectView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 项目 ID |
| `name` | string | 是 | 项目名称 |
| `description` | string/null | 否 | 创建描述 |
| `status` | `ProjectStatus` | 是 | 项目状态 |
| `revision` | integer | 是 | 当前项目真相修订号，只读 |
| `my_role` | enum | 是 | 当前用户的 `OWNER/MEMBER/VIEWER` |
| `created_by_user_id` | uuid | 是 | 创建者 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 更新时间 |

`MemberView` 由 `user_id uuid`、`username string`、`display_name string`、`role enum`、`created_at datetime` 组成。

页面类型：

- `UserPage.items: UserView[]`。
- `ProjectPage.items: ProjectView[]`。
- 所有 Page 另含 `next_cursor: string/null`。

### 21.17 公共工作台、消息、Run 与 Gate 响应

`WorkspaceView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `project` | `ProjectView` | 是 | 项目摘要 |
| `allowed_actions` | string[] | 是 | 服务端计算的 UI 动作提示 |
| `conversation` | `ConversationView/null` | 否 | 当前占用；空闲时为空 |
| `current_run` | `RunView/null` | 否 | 当前 Run |
| `human_gate` | `HumanGateView/null` | 否 | 当前 Gate |
| `stages` | `StageView[]` | 是 | 全部阶段状态 |
| `queue` | object | 是 | `count integer`，可选最近 Queue 摘要 |
| `artifact_summary` | object | 是 | `approved_count/draft_count integer` |

`ConversationView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `owner_user_id` | uuid | 是 | 当前占用用户 |
| `owner_display_name` | string | 是 | 显示名 |
| `is_current_user` | boolean | 是 | 是否当前登录用户 |
| `expires_at` | datetime | 是 | 当前 TTL 预计截止时间 |
| `allowed_delivery_modes` | enum[] | 是 | 当前可显示模式 |
| `can_release` | boolean | 是 | 当前是否满足主动释放条件 |

`MessageView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 服务端生成 Message ID |
| `project_id` | uuid | 是 | 项目 |
| `user_id` | uuid/null | 否 | 用户消息提交者 |
| `role` | enum | 是 | `USER/ASSISTANT/SYSTEM` |
| `agent_role` | string/null | 否 | 助手专业角色 |
| `content` | string | 是 | 当前可见正文 |
| `delivery_mode` | enum/null | 否 | 用户消息的 DIRECT/STEER/QUEUE |
| `target_run_id` | uuid/null | 否 | 目标 Run |
| `status` | `MessageStatus` | 是 | 当前状态 |
| `process` | `ProcessEvent[]` | 是 | 用户可见过程；列表 Query 可按参数裁剪 |
| `process_version` | integer | 是 | SSE 恢复水位 |
| `stopped_by_user_id` | uuid/null | 否 | 取消/中断操作者 |
| `stopped_at` | datetime/null | 否 | 取消/中断完成时间 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 更新时间 |

`ProcessEvent` 由 `event_id uuid`、`type string`、`stage StageCode/null`、`agent_role string/null`、`summary string`、`occurred_at datetime` 和可选 `resource_refs object` 组成。

`RoutingView` 由 `requested_mode enum`、`effective_mode enum`、`conversion_reason string/null` 组成。

`RunView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `run_id` | uuid | 是 | 当前逻辑 Run |
| `status` | `RunStatus` | 是 | 状态 |
| `trigger_message_id` | uuid | 是 | 触发消息 |
| `response_message_id` | uuid | 是 | 助手消息 |
| `retry_count` | integer | 是 | 当前 Run 累计重试 |
| `started_at` | datetime | 是 | 启动时间 |
| `updated_at` | datetime | 是 | 更新时间 |
| `last_error` | `PublicError/null` | 否 | 脱敏可行动错误 |
| `allowed_actions` | string[] | 是 | 当前用户动作提示 |

`HumanGateView` 由 `gate_id string`、`run_id uuid`、`type string`、`title string`、`question string`、`context object`、`allowed_decisions string[]`、`options object[]`、`requested_at datetime` 组成。

`MessagePage.items` 为 `MessageView[]`，另含 `next_cursor`。

### 21.18 公共阶段、产物与基线响应

`StageView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `stage` | `StageCode` | 是 | 阶段 |
| `status` | `StageStatus` | 是 | 当前状态 |
| `revision` | integer | 是 | 阶段修订号，只读 |
| `baseline_version` | integer | 是 | 0 表示未封存 |
| `baseline` | `BaselineRef/null` | 否 | 当前 Git 基线引用 |
| `candidate_count` | integer | 是 | 当前草稿数量 |
| `quality_issue_count` | integer | 是 | 当前未解决问题数 |
| `last_error` | `PublicError/null` | 否 | 封存等公开错误 |
| `updated_at` | datetime | 是 | 更新时间 |

`ArtifactDraftView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 草稿 ID，不是正式 Artifact Code |
| `stage` | `StageCode` | 是 | 所属阶段 |
| `artifact_type` | string | 是 | 产物类型 |
| `canonical_key` | string | 是 | 稳定业务键 |
| `operation` | enum | 是 | `CREATE/UPDATE/DELETE` |
| `title` | string | 是 | 标题 |
| `body` | object | 是 | 结构化候选内容 |
| `status` | string | 是 | 当前候选状态 |
| `validation` | object | 是 | 确定性校验摘要 |
| `review` | object | 是 | 语义评审摘要 |
| `updated_at` | datetime | 是 | 更新时间 |

`QualityFindingView` 由 `finding_id string`、`draft_id uuid`、`source enum`、`code string`、`severity enum`、`status enum`、`message string`、`field_path string/null`、`requirement_refs string[]` 组成。它是草稿 JSONB 投影，不是独立表主键。

`ArtifactView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `artifact_code` | string | 是 | 正式逻辑编号 |
| `stage` | `StageCode` | 是 | 所属阶段 |
| `artifact_type` | string | 是 | 类型 |
| `canonical_key` | string | 是 | 稳定业务键 |
| `title` | string | 是 | 标题 |
| `content_hash` | sha256 | 是 | 结构化源 Hash |
| `requirement_refs` | string[] | 是 | 需求引用 |
| `module_refs` | string[] | 是 | 模块引用 |
| `api_refs` | string[] | 是 | API 引用 |
| `table_refs` | string[] | 是 | 数据表引用 |
| `test_refs` | string[] | 是 | 测试引用 |
| `baseline` | `BaselineRef` | 是 | 当前批准来源 |
| `updated_at` | datetime | 是 | 当前投影更新时间 |

`ArtifactPage.items` 为 `ArtifactView[]`，另含 `next_cursor`。

`BaselineRef` 由 `stage StageCode`、`version integer`、`git_commit_sha string`、`git_tag string` 组成。

`BaselineView` 在 `BaselineRef` 基础上增加 `profile_version integer`、`profile_hash sha256`、`sealed_at datetime`、`artifacts ArtifactView[]`。`BaselinePage.items` 为不含完整 `artifacts` 的 `BaselineView[]`。

`BaselineDiffView` 由 `stage`、`from BaselineRef`、`to BaselineRef`、`summary`、`added[]`、`modified[]`、`deleted[]` 和可选 `unified_diff` 组成。

### 21.19 公共变更、Profile、模型和诊断响应

`ChangeView`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 变更 ID |
| `status` | `ChangeStatus` | 是 | 当前状态 |
| `summary` | string | 是 | 变更摘要 |
| `source_message_id` | uuid | 是 | 发起消息 |
| `target_refs` | string[] | 是 | 目标逻辑引用 |
| `impact` | object/null | 否 | 影响阶段和产物 |
| `allowed_decisions` | string[] | 是 | 当前用户可提交决议 |
| `decision_git_commit_sha` | string/null | 否 | 终态 Git 决议指针 |
| `last_error` | `PublicError/null` | 否 | 可行动错误 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 更新时间 |

`ChangeActionReceipt` 由 `change ChangeView`、`run RunView/null`、`decision_message MessageView/null` 组成；`ChangePage.items` 为 `ChangeView[]`。

`DomainProfileView` 由 `id uuid`、`code string`、`name string`、`description string/null`、`status ACTIVE/INACTIVE`、`is_builtin_general boolean`、`current_version integer`、`current_hash sha256/null`、`updated_at datetime` 组成。匹配规则属于发布版 Profile 内容，不复制到稳定身份响应。

`DomainProfileDraftView` 由 `profile_id uuid`、`base_version integer`、`lock_version integer`、`content object`、`content_hash sha256`、`updated_by_user_id uuid`、`updated_at datetime` 组成。校验结果由验证接口即时返回，不在草稿表重复保存。

`DomainProfileVersionView` 由 `profile_id uuid`、`version integer`、`content object`、`content_hash sha256`、`published_by_user_id uuid`、`published_at datetime` 组成。

`ProfileMigrationView` 由 `profile_id uuid`、`from_version integer`、`to_version integer`、`rule object`、`rule_hash sha256`、`updated_at datetime` 组成。

`ProfileValidationReport` 由 `valid boolean`、`draft_hash sha256`、`errors[]`、`warnings[]` 组成；`ProfileMigrationRetryReceipt` 由 `project_id`、`status`、`from_version`、`target_version`、`accepted_at` 组成。

`ModelProfileView` 由 `id uuid`、`code string`、`name string`、`purpose string`、`provider string`、`model_name string`、`parameters object`、`secret_ref string`、`is_default boolean`、`status ACTIVE/INACTIVE`、`updated_at datetime` 组成。真实 Secret 永不返回。

`DiagnosticEntry` 由 `node string`、`stage StageCode/null`、`provider string`、`model_profile_code string`、`parameter_summary object`、`prompt_hash sha256`、`schema_hash sha256/null`、`input_tokens integer`、`output_tokens integer`、`latency_ms integer`、`retry_count integer`、`estimated_cost decimal/null`、`result string`、`occurred_at datetime` 组成。

页面映射：

- `DomainProfilePage.items: DomainProfileView[]`。
- `DomainProfileVersionPage.items: DomainProfileVersionView[]`。
- `ModelProfilePage.items: ModelProfileView[]`。
- 所有 Page Schema 统一包含 `items` 和 `next_cursor`。

### 21.20 公共简单响应与错误字段

`ActionResult`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `result` | enum | 是 | `APPLIED/ALREADY_APPLIED` |
| `occurred_at` | datetime | 是 | 完成时间 |

`PublicError`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `code` | string | 是 | 稳定错误码 |
| `message` | string | 是 | 用户可理解信息 |
| `retryable` | boolean | 是 | 是否可重试 |
| `request_id` | string/null | 否 | 管理员关联 ID |

`ProblemDetails`：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `type` | uri | 是 | 稳定问题类型 URI |
| `title` | string | 是 | 简短标题 |
| `status` | integer | 是 | HTTP 状态码 |
| `detail` | string | 是 | 本次具体说明 |
| `code` | string | 是 | 前端分支使用的稳定错误码 |
| `instance` | uri-reference | 是 | 本次请求路径 |
| `request_id` | string | 是 | 日志关联 ID |
| `retryable` | boolean | 是 | 是否可安全重试 |
| `context` | object | 否 | 脱敏的行动上下文 |
| `allowed_actions` | string[] | 否 | 建议动作 |
| `field_errors` | object[] | 否 | 字段错误，包含 `path/code/message` |

## 22. 被 API 隐藏的复杂度

公开 API 不暴露：

- Redis Session Key、用户缓存、对话占用 Lua 和续期。
- Profile 自动匹配、整数版本升级路径和运行时 Schema 合成。
- DIRECT/STEER/QUEUE 路由、Worker 唤醒、租约和 Checkpoint。
- LangGraph 节点、Agent、Barrier、返工路由和上下文投影。
- 草稿校验、语义评审、连续编号和候选去重。
- Git Commit/Tag、`publish_key`、封存补全和当前 Artifact 投影。
- 中断安全点、不可中断区、Queue 批量取消和 Checkpoint 清理。
- GitLab 服务账号、对象存储 Key 和模型供应商凭据。

## 23. 首发 API 验收检查

- [ ] 63 个公开接口均具有唯一 `operationId`，并列出 Header、Path、Query、Body、成功响应和公共错误响应。
- [ ] 所有请求/响应 Schema 均能生成 OpenAPI 类型；产物正文和 Profile 内容引用各自版本化 JSON Schema，不使用无约束透传字段。
- [ ] Message ID 只由服务端生成，客户端只提供有作用域的 `Idempotency-Key`。
- [ ] 同 Key 同请求不重复启动 Run，同 Key 不同请求返回幂等冲突。
- [ ] Profile 草稿直接使用现有 `lock_version`，没有额外 ETag/Revision。
- [ ] 普通 Query 不启动模型、迁移、重试或其他业务状态变化。
- [ ] 长时 Command 快速返回 `202`，请求连接不承载 Graph 执行。
- [ ] DIRECT/STEER/QUEUE、转换结果和 `expected_run_id` 契约明确。
- [ ] WAITING、FAILED、STOPPING 和 INTERRUPTED 均有可查询投影。
- [ ] OWNER Gate、强制中断和 MEMBER 占用规则由服务端重验。
- [ ] 多阶段状态直接返回，未引入单值 `current_stage`。
- [ ] 草稿只读，客户端不能绕过 Graph 封存或批准产物。
- [ ] 历史、Diff 和下载按 Git Commit/Tag 读取。
- [ ] SSE 可按 Message Process Version 恢复，Redis 不作为历史来源。
- [ ] 普通接口不泄露 Profile、Prompt、诊断、GitLab 或供应商细节。
- [ ] OpenAPI 可生成完整 React Client 类型，不依赖手写重复 DTO。

## 24. 后续测试设计输入

测试用例设计至少覆盖：

1. Session 滑动过期、禁用/启用、多端登录和密码修改。
2. Message 幂等重试、Key 复用冲突和附件重试。
3. Redis 占用竞争、五分钟到期、Queue 续期和释放条件。
4. DIRECT/STEER/QUEUE 路由、自动转 Queue 和稳定顺序。
5. Gate 重复决议、不同决议竞争和 OWNER 绕过。
6. Run 中断安全点、封存原子区、Queue 取消和草稿保留。
7. Profile `lock_version` 冲突、自动迁移失败与管理员重试。
8. Git 成功、数据库失败后的封存补全、历史读取和下载隔离。
9. SSE 断线补发、版本跳跃、Redis 丢通知和全量重同步。
10. OWNER/MEMBER/VIEWER/ADMIN 的正反向权限矩阵。

实现不得为方便 API 增加本文已明确禁止的通用 Command、Event、Gate、Run History 或 Idempotency 表。若未来需要超大文件分片上传、跨天事件回放或外部开放 API，应单独提交 ADR。

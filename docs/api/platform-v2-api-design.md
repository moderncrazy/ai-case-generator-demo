# AI 软件交付平台 V2 API 接口文档

## 概述

本文档描述 V2 首发版公开 HTTP API。接口按当前项目 `doc/api_design.md` 的格式逐个说明，每个接口独立列出请求参数、请求示例、响应参数和响应示例。

首发范围到需求、PRD、架构、系统模块、API、数据库和测试用例设计完成，不包含自动开发和自动测试执行。

---

## 基础信息

| 项目 | 说明 |
| --- | --- |
| 基础 URL | `/api/v2` |
| 请求/成功响应 | `application/json` |
| 错误响应 | `application/problem+json` |
| 认证方式 | HttpOnly Session Cookie |
| 字段命名 | `snake_case` |
| 时间格式 | RFC 3339 UTC |
| 字符编码 | UTF-8 |
| 文档状态 | `APPROVED` |
| 文档版本 | 1.0 |
| 日期 | 2026-08-06 |

除登录外的接口均需要 Session Cookie。所有写接口同时校验 `X-CSRF-Token`、Origin 和 Fetch Metadata。项目创建、消息提交、人工 Gate 决议和变更决议还必须携带 UUID 格式的 `Idempotency-Key`。

---

## 通用错误响应

所有非 2xx 响应使用以下结构：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 是 | 稳定问题类型 URI |
| `title` | string | 是 | 错误标题 |
| `status` | int | 是 | HTTP 状态码 |
| `detail` | string | 是 | 本次错误说明 |
| `code` | string | 是 | 前端判断使用的稳定错误码 |
| `instance` | string | 是 | 请求路径 |
| `request_id` | string | 是 | 日志关联 ID |
| `retryable` | bool | 是 | 是否可安全重试 |
| `context` | object | 否 | 脱敏的行动上下文 |
| `allowed_actions` | string[] | 否 | 建议动作 |
| `field_errors` | object[] | 否 | 字段错误，包含 `path/code/message` |

```json
{
  "type": "https://platform.example/problems/conversation-occupied",
  "title": "项目对话已被占用",
  "status": 423,
  "detail": "当前由其他项目成员操作",
  "code": "CONVERSATION_OCCUPIED",
  "instance": "/api/v2/projects/4f6f/messages",
  "request_id": "req_01",
  "retryable": true,
  "context": {
    "owner_display_name": "张三",
    "expires_at": "2026-08-06T10:08:00Z"
  },
  "allowed_actions": ["WAIT"]
}
```

---

## 统一错误码说明

错误码是稳定的前后端契约。前端按 `code` 决定交互，不能解析 `detail` 文案；服务端可以优化文案，但不得在同一 API 大版本中改变错误码含义。

### 通用、认证与权限错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `MALFORMED_REQUEST` | 400 | JSON、Multipart 或 Header 结构无法解析 | 否 | 提示请求异常并记录 `request_id` |
| `VALIDATION_FAILED` | 422 | 字段缺失、格式或组合不合法 | 否 | 根据 `field_errors` 标记字段 |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Content-Type 不受接口支持 | 否 | 阻止提交并提示支持格式 |
| `AUTHENTICATION_FAILED` | 401 | 用户名或密码错误 | 否 | 停留登录页，不区分用户名是否存在 |
| `SESSION_EXPIRED` | 401 | Redis Session 不存在或已过期 | 否 | 清理本地登录态并跳转登录页 |
| `ACCOUNT_DISABLED` | 403 | 当前账户已禁用 | 否 | 阻止操作并展示账户状态 |
| `CSRF_VALIDATION_FAILED` | 403 | CSRF、Origin 或 Fetch Metadata 校验失败 | 否 | 刷新 Session 后最多重试一次 |
| `PERMISSION_DENIED` | 403 | 系统角色或项目角色无权执行操作 | 否 | 隐藏操作入口并提示权限不足 |
| `POLICY_REJECTED` | 403 | 操作违反平台治理规则 | 否 | 展示 `detail` 和 `allowed_actions` |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在或对当前用户不可见 | 否 | 返回列表或显示资源不存在 |
| `IDEMPOTENCY_KEY_REUSED` | 409 | 同一幂等键被用于不同请求内容 | 否 | 停止自动重试；新操作生成新 Key |
| `RATE_LIMITED` | 429 | 超过用户或系统频率限制 | 是 | 按 `Retry-After` 延迟重试 |

### 项目与成员错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `PROJECT_NOT_WRITABLE` | 409 | 项目归档、阻塞、迁移失败或处于禁止写入状态 | 条件 | 刷新工作台，按上下文展示恢复动作 |
| `PROJECT_REPOSITORY_NOT_READY` | 409 | 内部 GitLab 仓库尚未创建完成 | 是 | 保持只读并稍后刷新 |
| `LAST_OWNER_REQUIRED` | 409 | 操作会导致项目没有 OWNER | 否 | 要求先设置另一名 OWNER |
| `MEMBER_NOT_FOUND` | 404 | 指定项目成员不存在 | 否 | 刷新成员列表 |

### 对话、消息与 Run 错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `CONVERSATION_OCCUPIED` | 423 | 项目对话正由另一名用户占用 | 是 | 展示占用者和剩余时间，等待或刷新 |
| `CONVERSATION_RELEASE_NOT_ALLOWED` | 409 | 当前有活动 Run、Queue，或调用者不是占用者 | 条件 | 刷新工作台并禁用释放按钮 |
| `INVALID_DELIVERY_MODE` | 409 | 当前状态不允许请求的 DIRECT/STEER/QUEUE | 条件 | 使用响应中的允许模式重新选择 |
| `MESSAGE_NOT_CANCELLABLE` | 409 | Queue 已取消、已开始执行或不是 Queue | 否 | 刷新消息状态 |
| `CURRENT_RUN_NOT_FOUND` | 404 | 项目当前没有 Run | 否 | 刷新工作台并隐藏 Run 操作 |
| `RUN_ID_MISMATCH` | 409 | `expected_run_id` 与当前 Run 不一致 | 条件 | 刷新后由用户重新确认操作 |
| `RUN_STATE_CONFLICT` | 409 | 当前 Run 状态不允许该操作 | 条件 | 刷新 Run 状态和允许动作 |
| `RUN_STOPPING` | 409 | Run 已进入安全停止过程，禁止新业务消息 | 是 | 等待最终 `INTERRUPTED` |
| `RUN_FAILED_REQUIRES_RESOLUTION` | 409 | 失败 Run 尚未重试或放弃，不能启动新 Run | 条件 | 展示重试和放弃入口 |
| `RUN_NOT_FAILED` | 409 | 对非 FAILED Run 发起重试或放弃 | 否 | 刷新 Run 状态 |

`STEER` 因错过安全边界转为 `QUEUE` 是成功路由，不是错误。接口仍返回 `202`，并在 `routing.conversion_reason` 返回 `ATOMIC_SECTION` 等原因。

### Human Gate 与项目变更错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `HUMAN_GATE_NOT_ACTIVE` | 404 | 当前没有待处理 Gate | 否 | 刷新工作台并关闭决策面板 |
| `HUMAN_GATE_MISMATCH` | 409 | Gate ID 或 Run ID 已变化 | 条件 | 重新获取当前 Gate |
| `HUMAN_GATE_ALREADY_RESOLVED` | 409 | Gate 已由其他 OWNER 或请求处理 | 否 | 展示最终决议并关闭输入 |
| `CHANGE_STATUS_CONFLICT` | 409 | `expected_status` 与当前 Change 状态不同 | 条件 | 重新获取 Change 详情 |
| `CHANGE_DECISION_NOT_ALLOWED` | 409 | 当前状态不允许提交该决议 | 否 | 使用 `allowed_decisions` 重新展示按钮 |
| `CHANGE_NOT_RETRYABLE` | 409 | Change 不处于允许重试的 FAILED 状态 | 否 | 刷新 Change 状态 |

### Profile、模型与管理员错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `PROFILE_DRAFT_VERSION_CONFLICT` | 409 | `expected_lock_version` 已过期 | 条件 | 重新加载草稿后再编辑 |
| `PROFILE_VALIDATION_FAILED` | 422 | Profile 草稿未通过发布校验 | 否 | 展示校验问题列表 |
| `PROFILE_VERSION_CONFLICT` | 409 | 预期发布版本不是当前连续版本 | 条件 | 刷新 Profile 详情和版本列表 |
| `PROFILE_RULE_HASH_CONFLICT` | 409 | 迁移规则已被其他管理员修改 | 条件 | 重新加载当前规则 |
| `PROFILE_MIGRATION_FAILED` | 409 | 项目自动升级 Profile 失败，业务写入被阻止 | 是 | 保持项目只读；用户新对话仍会自动重试，管理员可手动重试 |
| `BUILTIN_PROFILE_REQUIRED` | 409 | 试图停用系统通用兜底 Profile | 否 | 恢复原状态 |
| `MODEL_DEFAULT_CONFLICT` | 409 | 同一 purpose 出现多个启用默认模型 | 条件 | 刷新列表并重新选择默认项 |
| `SECRET_REF_INVALID` | 422 | Secret 引用不存在或当前服务无权使用 | 否 | 修正 Secret 配置 |

### 产物、基线、文件与外部依赖错误

| 错误码 | HTTP 状态 | 含义 | 可重试 | 前端处理 |
| --- | --- | --- | --- | --- |
| `ARTIFACT_NOT_FOUND` | 404 | 指定正式产物在目标基线不存在 | 否 | 刷新产物或基线列表 |
| `BASELINE_NOT_AVAILABLE` | 404 | 阶段尚未封存或指定历史版本不存在 | 否 | 选择已有基线 |
| `APPROVED_CONTENT_ONLY` | 409 | 尝试通过下载接口获取草稿或未批准内容 | 否 | 只允许选择批准基线 |
| `FILE_NAME_CONFLICT` | 409 | 项目中已存在同名附件 | 否 | 修改文件名后重新上传 |
| `FILE_TOO_LARGE` | 413 | 单文件或请求总大小超过限制 | 否 | 压缩或拆分文件 |
| `UNSUPPORTED_FILE_TYPE` | 415 | 文件类型不在允许列表 | 否 | 改用受支持格式 |
| `FILE_REJECTED` | 422 | 文件安全检查或内容检查未通过 | 否 | 移除问题文件 |
| `UPSTREAM_INVALID_RESPONSE` | 502 | GitLab、模型或对象存储返回无效响应 | 是 | 保留当前状态并稍后重试 |
| `EXTERNAL_SERVICE_UNAVAILABLE` | 503 | 外部依赖暂时不可用 | 是 | 按 `Retry-After` 重试；长时任务由 Worker 幂等恢复 |

### 内部执行错误分类

以下代码可出现在 ADMIN 诊断或过程记录中，但不能作为普通用户 HTTP 错误原样返回：

| 内部代码 | 含义 | 对外处理 |
| --- | --- | --- |
| `BUSINESS_DECISION_REQUIRED` | 需要业务、成本、合规或不可逆决策 | 转为 Human Gate，不返回失败 |
| `STALE_INPUT` | 上游基线或项目修订已变化 | 丢弃结果并重新规划 |
| `CONCURRENCY_CONFLICT` | Worker 租约或内部修订竞争 | 内部重新加载和安全重试 |
| `EXTERNAL_TRANSIENT` | 外部依赖暂时失败 | 映射 `EXTERNAL_SERVICE_UNAVAILABLE` 或内部重试 |
| `EXTERNAL_PERMANENT` | 外部权限或配置永久错误 | Run 进入 FAILED，对外返回脱敏后的稳定错误码 |

---

## Session 接口

### 用户登录

```http
POST /api/v2/session
```

**说明：** 校验本地账户并创建 Redis Session。成功后通过 HttpOnly Cookie 返回随机 Token。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 登录名，最长 100 字符 |
| `password` | string | 是 | 原始密码，仅通过 TLS 传输 |

**请求示例：**

```json
{
  "username": "admin",
  "password": "example-password"
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `user.id` | uuid | 是 | 用户 ID |
| `user.username` | string | 是 | 登录名 |
| `user.display_name` | string | 是 | 显示名 |
| `user.system_role` | string | 是 | `ADMIN` 或 `USER` |
| `user.status` | string | 是 | `ACTIVE` |
| `user.must_change_password` | bool | 是 | 是否必须修改临时密码 |
| `csrf_token` | string | 是 | React 内存保存的 CSRF Token |
| `session_idle_expires_at` | datetime | 是 | Redis 滑动过期预计时间 |

**响应示例：**

```json
{
  "user": {
    "id": "b133dd60-efbd-4a41-a339-13223795c256",
    "username": "admin",
    "display_name": "管理员",
    "system_role": "ADMIN",
    "status": "ACTIVE",
    "must_change_password": false
  },
  "csrf_token": "csrf-token",
  "session_idle_expires_at": "2026-08-06T12:00:00Z"
}
```

**主要错误码：** `AUTHENTICATION_FAILED`、`ACCOUNT_DISABLED`。

---

### 获取当前 Session

```http
GET /api/v2/session
```

**说明：** 页面刷新后恢复当前用户、CSRF Token 和 Session 预计过期时间。

**请求参数：** 无。

**响应参数：** 与“用户登录”响应参数相同。

**响应示例：**

```json
{
  "user": {
    "id": "b133dd60-efbd-4a41-a339-13223795c256",
    "username": "admin",
    "display_name": "管理员",
    "system_role": "ADMIN",
    "status": "ACTIVE",
    "must_change_password": false
  },
  "csrf_token": "new-csrf-token",
  "session_idle_expires_at": "2026-08-06T12:15:00Z"
}
```

**主要错误码：** `SESSION_EXPIRED`、`ACCOUNT_DISABLED`。

---

### 退出登录

```http
DELETE /api/v2/session
```

**说明：** 删除当前设备 Redis Session，不影响其他设备。

**请求参数：** 无。

**响应参数：** 无，成功返回 `204 No Content`。

**主要错误码：** `SESSION_EXPIRED`、`CSRF_VALIDATION_FAILED`。

---

### 修改本人密码

```http
PUT /api/v2/me/password
```

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `current_password` | string | 是 | 当前密码 |
| `new_password` | string | 是 | 符合密码策略且不能与当前密码相同 |

**请求示例：**

```json
{
  "current_password": "old-password",
  "new_password": "new-password"
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `result` | string | 是 | `APPLIED` 或 `ALREADY_APPLIED` |
| `occurred_at` | datetime | 是 | 完成时间 |

**响应示例：**

```json
{
  "result": "APPLIED",
  "occurred_at": "2026-08-06T10:00:00Z"
}
```

修改密码不撤销任何已登录 Session。

---

## 项目接口

### 查询项目列表

```http
GET /api/v2/projects
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `cursor` | string | 否 | 上一页返回的不透明游标 |
| `limit` | int | 否 | 默认 50，最大 200 |
| `status` | string | 否 | `ACTIVE/REBASELINING/BLOCKED/COMPLETED/ARCHIVED` |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | 项目 ID |
| `items[].name` | string | 是 | 项目名称 |
| `items[].description` | string/null | 否 | 项目描述 |
| `items[].status` | string | 是 | 项目状态 |
| `items[].revision` | int | 是 | 项目真相修订号 |
| `items[].my_role` | string | 是 | `OWNER/MEMBER/VIEWER` |
| `items[].created_at` | datetime | 是 | 创建时间 |
| `items[].updated_at` | datetime | 是 | 更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "6df9e9cb-3f0f-43cc-8071-bffb5b814dfa",
      "name": "订单履约平台",
      "description": "订单履约系统设计",
      "status": "ACTIVE",
      "revision": 12,
      "my_role": "OWNER",
      "created_at": "2026-08-06T09:00:00Z",
      "updated_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 创建项目

```http
POST /api/v2/projects
```

**请求头参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `Idempotency-Key` | uuid | 是 | 本次创建操作重试标识，不是项目 ID |

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 项目名称，1—255 字符 |
| `description` | string/null | 否 | 项目背景 |
| `initial_message` | string | 是 | PM 首次接收的目标和上下文 |

**请求示例：**

```json
{
  "name": "订单履约平台",
  "description": "为直营业务设计订单履约系统",
  "initial_message": "需要覆盖创建订单、支付、履约和取消"
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project.id` | uuid | 是 | 服务端生成的项目 ID |
| `project.name` | string | 是 | 项目名称 |
| `project.description` | string/null | 否 | 项目描述 |
| `project.status` | string | 是 | 初始为 `ACTIVE` 或仓库失败后的 `BLOCKED` |
| `project.revision` | int | 是 | 初始修订号 |
| `project.my_role` | string | 是 | 创建者为 `OWNER` |
| `initial_message.id` | uuid | 是 | 服务端生成的用户 Message ID |
| `initial_message.status` | string | 是 | 当前消息状态 |
| `response_message_id` | uuid | 是 | 助手消息 ID |
| `run.run_id` | uuid | 是 | 当前 Run ID |
| `run.status` | string | 是 | 通常为 `QUEUED` |
| `repository_status` | string | 是 | `PENDING/READY/FAILED` |

**响应示例：**

```json
{
  "project": {
    "id": "6df9e9cb-3f0f-43cc-8071-bffb5b814dfa",
    "name": "订单履约平台",
    "description": "为直营业务设计订单履约系统",
    "status": "ACTIVE",
    "revision": 0,
    "my_role": "OWNER"
  },
  "initial_message": {
    "id": "f444337e-bec5-48b2-be20-bb45db96f228",
    "status": "PENDING"
  },
  "response_message_id": "f73de800-074b-42b6-858e-66559857ec36",
  "run": {
    "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
    "status": "QUEUED"
  },
  "repository_status": "PENDING"
}
```

成功返回 `202 Accepted`。

---

### 获取项目详情

```http
GET /api/v2/projects/{project_id}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | uuid | 是 | 项目 ID |
| `name` | string | 是 | 项目名称 |
| `description` | string/null | 否 | 项目描述 |
| `status` | string | 是 | 项目状态 |
| `revision` | int | 是 | 项目真相修订号，只读 |
| `my_role` | string | 是 | 当前用户项目角色 |
| `created_by_user_id` | uuid | 是 | 创建者 |
| `created_at` | datetime | 是 | 创建时间 |
| `updated_at` | datetime | 是 | 更新时间 |

**响应示例：**

```json
{
  "id": "6df9e9cb-3f0f-43cc-8071-bffb5b814dfa",
  "name": "订单履约平台",
  "description": "订单履约系统设计",
  "status": "ACTIVE",
  "revision": 12,
  "my_role": "OWNER",
  "created_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "created_at": "2026-08-06T09:00:00Z",
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 获取项目工作台

```http
GET /api/v2/projects/{project_id}/workspace
```

**说明：** 一次返回 React 项目页需要的当前投影，不创建 `workspace` 表。

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project` | object | 是 | 项目详情对象 |
| `allowed_actions` | string[] | 是 | 当前用户可显示的操作 |
| `conversation` | object/null | 否 | 当前占用用户、到期时间和允许消息模式 |
| `current_run` | object/null | 否 | 当前 Run 摘要 |
| `human_gate` | object/null | 否 | 当前人工决策 Gate |
| `stages` | object[] | 是 | 九个阶段当前状态 |
| `queue.count` | int | 是 | 待执行 Queue 数量 |
| `artifact_summary.approved_count` | int | 是 | 当前批准产物数 |
| `artifact_summary.draft_count` | int | 是 | 当前草稿数 |

**响应示例：**

```json
{
  "project": {
    "id": "6df9e9cb-3f0f-43cc-8071-bffb5b814dfa",
    "name": "订单履约平台",
    "status": "ACTIVE",
    "revision": 12,
    "my_role": "OWNER"
  },
  "allowed_actions": ["SUBMIT_STEER", "SUBMIT_QUEUE", "INTERRUPT_RUN"],
  "conversation": {
    "owner_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
    "owner_display_name": "管理员",
    "is_current_user": true,
    "expires_at": "2026-08-06T10:08:00Z",
    "allowed_delivery_modes": ["STEER", "QUEUE"],
    "can_release": false
  },
  "current_run": {
    "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
    "status": "RUNNING"
  },
  "human_gate": null,
  "stages": [],
  "queue": {"count": 2},
  "artifact_summary": {"approved_count": 31, "draft_count": 12}
}
```

---

## 项目成员接口

### 查询项目成员

```http
GET /api/v2/projects/{project_id}/members
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].user_id` | uuid | 是 | 用户 ID |
| `[].username` | string | 是 | 登录名 |
| `[].display_name` | string | 是 | 显示名 |
| `[].role` | string | 是 | `OWNER/MEMBER/VIEWER` |
| `[].created_at` | datetime | 是 | 加入时间 |

**响应示例：**

```json
[
  {
    "user_id": "b133dd60-efbd-4a41-a339-13223795c256",
    "username": "admin",
    "display_name": "管理员",
    "role": "OWNER",
    "created_at": "2026-08-06T09:00:00Z"
  }
]
```

---

## 管理员 Domain Profile 接口

### 查询 Domain Profile 列表

```http
GET /api/v2/admin/domain-profiles
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `cursor` | string | 否 | 上一页游标 |
| `limit` | int | 否 | 默认 50，最大 200 |
| `status` | string | 否 | `ACTIVE/INACTIVE` |
| `q` | string | 否 | Code 或名称关键词 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | Profile ID |
| `items[].code` | string | 是 | 稳定机器代码 |
| `items[].name` | string | 是 | 管理端名称 |
| `items[].description` | string/null | 否 | 管理说明 |
| `items[].status` | string | 是 | `ACTIVE/INACTIVE` |
| `items[].is_builtin_general` | bool | 是 | 是否通用兜底 Profile |
| `items[].current_version` | int | 是 | 当前发布整数版本 |
| `items[].current_hash` | string/null | 否 | 当前发布内容 Hash |
| `items[].updated_at` | datetime | 是 | 更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "a08e3428-a3c0-4833-96b4-928144761ef6",
      "code": "general",
      "name": "通用软件项目",
      "description": "未匹配专业领域时使用",
      "status": "ACTIVE",
      "is_builtin_general": true,
      "current_version": 5,
      "current_hash": "93af...",
      "updated_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 创建 Domain Profile

```http
POST /api/v2/admin/domain-profiles
```

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `code` | string | 是 | 全局唯一稳定代码 |
| `name` | string | 是 | 管理端名称 |
| `description` | string/null | 否 | 管理说明 |

**请求示例：**

```json
{
  "code": "ecommerce",
  "name": "电商平台",
  "description": "订单、商品、库存和支付领域"
}
```

**响应参数：** 与“查询 Domain Profile 列表”的单个 `items[]` 对象相同；新建时 `current_version=0`、`current_hash=null`、`is_builtin_general=false`。

**响应示例：**

```json
{
  "id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "code": "ecommerce",
  "name": "电商平台",
  "description": "订单、商品、库存和支付领域",
  "status": "ACTIVE",
  "is_builtin_general": false,
  "current_version": 0,
  "current_hash": null,
  "updated_at": "2026-08-06T10:00:00Z"
}
```

成功返回 `201 Created`。

---

### 获取 Domain Profile 详情

```http
GET /api/v2/admin/domain-profiles/{profile_id}
```

**路径参数：** `profile_id`（uuid，必填，Profile ID）。

**响应参数：** 与“查询 Domain Profile 列表”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "code": "ecommerce",
  "name": "电商平台",
  "description": "订单、商品、库存和支付领域",
  "status": "ACTIVE",
  "is_builtin_general": false,
  "current_version": 5,
  "current_hash": "93af...",
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 修改 Domain Profile 元数据

```http
PATCH /api/v2/admin/domain-profiles/{profile_id}
```

**路径参数：** `profile_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 新名称 |
| `description` | string/null | 否 | 新说明 |
| `status` | string | 否 | `ACTIVE/INACTIVE` |

至少提交一个字段；内置通用 Profile 不能停用。

**请求示例：**

```json
{"description": "电商交易与履约领域"}
```

**响应参数：** 与“获取 Domain Profile 详情”相同。

**响应示例：**

```json
{
  "id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "code": "ecommerce",
  "name": "电商平台",
  "description": "电商交易与履约领域",
  "status": "ACTIVE",
  "is_builtin_general": false,
  "current_version": 5,
  "current_hash": "93af...",
  "updated_at": "2026-08-06T10:05:00Z"
}
```

---

### 获取 Domain Profile 草稿

```http
GET /api/v2/admin/domain-profiles/{profile_id}/draft
```

**路径参数：** `profile_id`（uuid，必填）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `profile_id` | uuid | 是 | Profile ID |
| `base_version` | int | 是 | 草稿起始发布版本 |
| `lock_version` | int | 是 | 乐观锁版本 |
| `content` | object | 是 | 完整 Profile 聚合，受版本化 Schema 约束 |
| `content_hash` | string | 是 | 草稿 SHA-256 |
| `updated_by_user_id` | uuid | 是 | 最近编辑管理员 |
| `updated_at` | datetime | 是 | 最近编辑时间 |

**响应示例：**

```json
{
  "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "base_version": 5,
  "lock_version": 8,
  "content": {
    "terminology": {},
    "matching": {},
    "artifact_extensions": {},
    "validation_rules": []
  },
  "content_hash": "b0d2...",
  "updated_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 保存 Domain Profile 草稿

```http
PUT /api/v2/admin/domain-profiles/{profile_id}/draft
```

**路径参数：** `profile_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expected_lock_version` | int | 是 | GET 草稿返回的 `lock_version` |
| `content` | object | 是 | 完整替换后的 Profile 聚合 |

**请求示例：**

```json
{
  "expected_lock_version": 8,
  "content": {
    "terminology": {},
    "matching": {},
    "artifact_extensions": {},
    "validation_rules": []
  }
}
```

**响应参数：** 与“获取 Domain Profile 草稿”相同，其中 `lock_version` 递增并返回新 `content_hash`。

**响应示例：**

```json
{
  "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "base_version": 5,
  "lock_version": 9,
  "content": {
    "terminology": {},
    "matching": {},
    "artifact_extensions": {},
    "validation_rules": []
  },
  "content_hash": "f260...",
  "updated_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "updated_at": "2026-08-06T10:05:00Z"
}
```

**主要错误码：** `PROFILE_DRAFT_VERSION_CONFLICT`。

---

### 校验 Domain Profile 草稿

```http
POST /api/v2/admin/domain-profiles/{profile_id}/draft-validations
```

**路径参数：** `profile_id`（uuid，必填）。

**请求体参数：** `expected_lock_version`（int，必填，要校验的草稿版本）。

**请求示例：**

```json
{"expected_lock_version": 9}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `valid` | bool | 是 | 是否通过静态检查 |
| `draft_hash` | string | 是 | 被校验草稿 Hash |
| `errors[]` | object[] | 是 | 阻止发布的问题，含 `code/path/message` |
| `warnings[]` | object[] | 是 | 不阻止发布的提示 |

**响应示例：**

```json
{
  "valid": true,
  "draft_hash": "f260...",
  "errors": [],
  "warnings": []
}
```

---

### 发布 Domain Profile

```http
POST /api/v2/admin/domain-profiles/{profile_id}/publications
```

**路径参数：** `profile_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expected_current_version` | int | 是 | 当前发布版本，首次发布为 0 |
| `expected_draft_hash` | string | 是 | 已校验草稿 Hash |
| `migration` | object/null | 条件 | 发布版本大于 1 时必填 |
| `migration.from_version` | int | 条件 | 当前版本 |
| `migration.to_version` | int | 条件 | 必须为当前版本加 1 |
| `migration.rule` | object | 条件 | 相邻升级规则 |
| `migration.expected_rule_hash` | string/null | 否 | 覆盖现有规则时的 Hash |

**请求示例：**

```json
{
  "expected_current_version": 5,
  "expected_draft_hash": "f260...",
  "migration": {
    "from_version": 5,
    "to_version": 6,
    "rule": {"operations": []},
    "expected_rule_hash": null
  }
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `profile_id` | uuid | 是 | Profile ID |
| `version` | int | 是 | 新发布整数版本 |
| `content` | object | 是 | 不可变发布内容 |
| `content_hash` | string | 是 | 发布内容 Hash |
| `validation_result` | object | 是 | 发布时校验结果 |
| `published_by_user_id` | uuid | 是 | 发布管理员 |
| `published_at` | datetime | 是 | 发布时间 |

**响应示例：**

```json
{
  "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "version": 6,
  "content": {"terminology": {}, "matching": {}},
  "content_hash": "f260...",
  "validation_result": {"valid": true},
  "published_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "published_at": "2026-08-06T10:10:00Z"
}
```

成功返回 `201 Created`。

---

### 查询 Domain Profile 版本

```http
GET /api/v2/admin/domain-profiles/{profile_id}/versions
```

**路径参数：** `profile_id`（uuid，必填）。

**查询参数：** `cursor`（string，否）、`limit`（int，否，默认 50）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].profile_id` | uuid | 是 | Profile ID |
| `items[].version` | int | 是 | 整数版本 |
| `items[].content_hash` | string | 是 | 内容 Hash |
| `items[].published_by_user_id` | uuid | 是 | 发布人 |
| `items[].published_at` | datetime | 是 | 发布时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
      "version": 6,
      "content_hash": "f260...",
      "published_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
      "published_at": "2026-08-06T10:10:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 获取 Domain Profile 指定版本

```http
GET /api/v2/admin/domain-profiles/{profile_id}/versions/{version}
```

**路径参数：** `profile_id`（uuid，必填）、`version`（int，必填，大于等于 1）。

**响应参数：** 与“发布 Domain Profile”的响应相同。

**响应示例：**

```json
{
  "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "version": 6,
  "content": {"terminology": {}, "matching": {}},
  "content_hash": "f260...",
  "validation_result": {"valid": true},
  "published_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "published_at": "2026-08-06T10:10:00Z"
}
```

---

### 查询 Profile 迁移规则

```http
GET /api/v2/admin/domain-profiles/{profile_id}/migrations
```

**路径参数：** `profile_id`（uuid，必填）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].profile_id` | uuid | 是 | Profile ID |
| `[].from_version` | int | 是 | 来源版本 |
| `[].to_version` | int | 是 | 相邻目标版本 |
| `[].rule` | object | 是 | 当前迁移规则 |
| `[].rule_hash` | string | 是 | 当前规则 Hash |
| `[].updated_at` | datetime | 是 | 最近修改时间 |

**响应示例：**

```json
[
  {
    "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
    "from_version": 5,
    "to_version": 6,
    "rule": {"operations": []},
    "rule_hash": "19fd...",
    "updated_at": "2026-08-06T10:10:00Z"
  }
]
```

---

### 保存 Profile 迁移规则

```http
PUT /api/v2/admin/domain-profiles/{profile_id}/migrations/{from_version}
```

**路径参数：** `profile_id`（uuid，必填）、`from_version`（int，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `to_version` | int | 是 | 必须等于 `from_version + 1` |
| `rule` | object | 是 | 完整迁移规则 |
| `expected_rule_hash` | string/null | 否 | 修改已有规则时使用 |

**请求示例：**

```json
{
  "to_version": 6,
  "rule": {"operations": []},
  "expected_rule_hash": "19fd..."
}
```

**响应参数：** 与“查询 Profile 迁移规则”的单个数组对象相同。

**响应示例：**

```json
{
  "profile_id": "28ba06c7-cbc2-4cef-8aa3-a6a7549df05c",
  "from_version": 5,
  "to_version": 6,
  "rule": {"operations": []},
  "rule_hash": "2aaa...",
  "updated_at": "2026-08-06T10:15:00Z"
}
```

---

### 管理员重试项目 Profile 迁移

```http
POST /api/v2/admin/projects/{project_id}/profile-migration-retries
```

**路径参数：** `project_id`（uuid，必填）。

**请求体参数：** 无。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `status` | string | 是 | `MIGRATING/CURRENT/FAILED` |
| `from_version` | int | 是 | 重试起始版本 |
| `target_version` | int | 是 | 当前最新版本 |
| `accepted_at` | datetime | 是 | 接受时间 |

**响应示例：**

```json
{
  "project_id": "6df9e9cb-3f0f-43cc-8071-bffb5b814dfa",
  "status": "MIGRATING",
  "from_version": 4,
  "target_version": 6,
  "accepted_at": "2026-08-06T10:20:00Z"
}
```

成功返回 `202 Accepted`。用户每次对话仍会自动执行迁移，本接口不替代自动流程。

---

## 管理员模型配置接口

### 查询模型配置

```http
GET /api/v2/admin/model-profiles
```

**查询参数：** `cursor`（string，否）、`limit`（int，否）、`purpose`（string，否）、`status`（`ACTIVE/INACTIVE`，否）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | Model Profile ID |
| `items[].code` | string | 是 | 稳定代码 |
| `items[].name` | string | 是 | 管理端名称 |
| `items[].purpose` | string | 是 | `INTENT/AUTHOR/REVIEWER/TEST_DESIGN` 等 |
| `items[].provider` | string | 是 | Provider Adapter 代码 |
| `items[].model_name` | string | 是 | 供应商模型名 |
| `items[].parameters` | object | 是 | 白名单参数 |
| `items[].secret_ref` | string | 是 | Secret 引用，不是真实密钥 |
| `items[].status` | string | 是 | `ACTIVE/INACTIVE` |
| `items[].is_default` | bool | 是 | 是否为用途默认项 |
| `items[].updated_at` | datetime | 是 | 更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "3f7d0dcb-b393-487f-831d-866be3fd50ce",
      "code": "author-primary",
      "name": "主创作模型",
      "purpose": "AUTHOR",
      "provider": "openai-compatible",
      "model_name": "model-name",
      "parameters": {"temperature": 0.2},
      "secret_ref": "secret/model-provider",
      "status": "ACTIVE",
      "is_default": true,
      "updated_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 创建模型配置

```http
POST /api/v2/admin/model-profiles
```

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `code` | string | 是 | 稳定唯一代码 |
| `name` | string | 是 | 管理端名称 |
| `purpose` | string | 是 | 用途代码 |
| `provider` | string | 是 | Provider Adapter 代码 |
| `model_name` | string | 是 | 供应商模型标识 |
| `parameters` | object | 是 | 白名单参数集合 |
| `secret_ref` | string | 是 | Secret 引用 |
| `is_default` | bool | 是 | 是否为该用途默认配置 |

**请求示例：**

```json
{
  "code": "author-primary",
  "name": "主创作模型",
  "purpose": "AUTHOR",
  "provider": "openai-compatible",
  "model_name": "model-name",
  "parameters": {"temperature": 0.2},
  "secret_ref": "secret/model-provider",
  "is_default": true
}
```

**响应参数：** 与“查询模型配置”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "id": "3f7d0dcb-b393-487f-831d-866be3fd50ce",
  "code": "author-primary",
  "name": "主创作模型",
  "purpose": "AUTHOR",
  "provider": "openai-compatible",
  "model_name": "model-name",
  "parameters": {"temperature": 0.2},
  "secret_ref": "secret/model-provider",
  "status": "ACTIVE",
  "is_default": true,
  "updated_at": "2026-08-06T10:00:00Z"
}
```

成功返回 `201 Created`。

---

### 获取模型配置详情

```http
GET /api/v2/admin/model-profiles/{model_profile_id}
```

**路径参数：** `model_profile_id`（uuid，必填）。

**响应参数：** 与“查询模型配置”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "id": "3f7d0dcb-b393-487f-831d-866be3fd50ce",
  "code": "author-primary",
  "name": "主创作模型",
  "purpose": "AUTHOR",
  "provider": "openai-compatible",
  "model_name": "model-name",
  "parameters": {"temperature": 0.2},
  "secret_ref": "secret/model-provider",
  "status": "ACTIVE",
  "is_default": true,
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 修改模型配置

```http
PATCH /api/v2/admin/model-profiles/{model_profile_id}
```

**路径参数：** `model_profile_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 新名称 |
| `purpose` | string | 否 | 新用途代码 |
| `provider` | string | 否 | 新 Provider 代码 |
| `model_name` | string | 否 | 新模型标识 |
| `parameters` | object | 否 | 完整替换参数集合 |
| `secret_ref` | string | 否 | 新 Secret 引用 |
| `is_default` | bool | 否 | 是否默认 |
| `status` | string | 否 | `ACTIVE/INACTIVE` |

至少提交一个字段。

**请求示例：**

```json
{
  "parameters": {"temperature": 0.1},
  "is_default": true
}
```

**响应参数：** 与“获取模型配置详情”相同。

**响应示例：**

```json
{
  "id": "3f7d0dcb-b393-487f-831d-866be3fd50ce",
  "code": "author-primary",
  "name": "主创作模型",
  "purpose": "AUTHOR",
  "provider": "openai-compatible",
  "model_name": "model-name",
  "parameters": {"temperature": 0.1},
  "secret_ref": "secret/model-provider",
  "status": "ACTIVE",
  "is_default": true,
  "updated_at": "2026-08-06T10:05:00Z"
}
```

---

## 管理员诊断接口

### 获取消息模型诊断

```http
GET /api/v2/admin/projects/{project_id}/messages/{message_id}/diagnostics
```

**路径参数：** `project_id`（uuid，必填）、`message_id`（uuid，必填）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].node` | string | 是 | Graph 节点 |
| `[].stage` | string/null | 否 | 阶段 |
| `[].provider` | string | 是 | 实际 Provider |
| `[].model_profile_code` | string | 是 | 模型配置代码 |
| `[].parameter_summary` | object | 是 | 脱敏参数摘要 |
| `[].prompt_hash` | string | 是 | Prompt Hash，不返回 Prompt |
| `[].schema_hash` | string/null | 否 | 输出 Schema Hash |
| `[].input_tokens` | int | 是 | 输入 Token |
| `[].output_tokens` | int | 是 | 输出 Token |
| `[].latency_ms` | int | 是 | 耗时 |
| `[].retry_count` | int | 是 | 重试次数 |
| `[].estimated_cost` | decimal/null | 否 | 估算成本 |
| `[].result` | string | 是 | 调用结果 |
| `[].occurred_at` | datetime | 是 | 发生时间 |

**响应示例：**

```json
[
  {
    "node": "api_author",
    "stage": "API",
    "provider": "openai-compatible",
    "model_profile_code": "author-primary",
    "parameter_summary": {"temperature": 0.2},
    "prompt_hash": "f42a...",
    "schema_hash": "3c91...",
    "input_tokens": 3500,
    "output_tokens": 1800,
    "latency_ms": 8200,
    "retry_count": 0,
    "estimated_cost": 0.12,
    "result": "SUCCEEDED",
    "occurred_at": "2026-08-06T10:00:00Z"
  }
]
```

仅 ADMIN 可访问，且不返回完整 Prompt、供应商原始响应或密钥。

---

## SSE 接口

### 订阅项目事件

```http
GET /api/v2/projects/{project_id}/events
```

**路径参数：** `project_id`（uuid，必填）。

**请求头参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `Accept` | string | 是 | `text/event-stream` |
| `Last-Event-ID` | string | 否 | 上次收到的不透明事件游标 |

**响应参数：**

| SSE 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 例如 `{message_id}:{process_version}` |
| `event` | string | 是 | 事件类型 |
| `data.project_id` | uuid | 是 | 项目 ID |
| `data.resource_type` | string | 是 | `message/run/stage/artifact/gate/conversation/project` |
| `data.resource_id` | string | 是 | 资源 ID 或阶段代码 |
| `data.version` | int/null | 否 | Process Version 或修订号 |
| `data.occurred_at` | datetime | 是 | 发生时间 |
| `data.data` | object | 是 | 对应类型的轻量增量 |

**响应示例：**

```text
id: f73de800-074b-42b6-858e-66559857ec36:36
event: message.process.appended
data: {"project_id":"6df9e9cb-3f0f-43cc-8071-bffb5b814dfa","resource_type":"message","resource_id":"f73de800-074b-42b6-858e-66559857ec36","version":36,"occurred_at":"2026-08-06T10:05:00Z","data":{"summary":"API 校验完成"}}
```

支持的事件：`project.sync`、`message.created`、`message.status.changed`、`message.process.appended`、`run.status.changed`、`human_gate.changed`、`stage.changed`、`artifact.changed`、`queue.changed`、`conversation.changed`、`resync.required`。

SSE 心跳不刷新 Session 或项目对话占用；Redis 丢失通知时通过 PostgreSQL 消息和 `process_version` 重同步。

---

## 明确不公开的内部接口

以下能力只允许领域模块、Worker 或 Scheduler 调用：

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

普通用户不能直接修改草稿、Profile、阶段状态、Run 状态或 Git 基线。

---

## 批准产物接口

### 查询批准产物

```http
GET /api/v2/projects/{project_id}/artifacts
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stage` | string | 否 | 阶段代码 |
| `artifact_type` | string | 否 | 产物类型 |
| `cursor` | string | 否 | 上一页游标 |
| `limit` | int | 否 | 默认 50，最大 200 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].artifact_code` | string | 是 | 正式逻辑编号 |
| `items[].stage` | string | 是 | 所属阶段 |
| `items[].artifact_type` | string | 是 | 产物类型 |
| `items[].canonical_key` | string | 是 | 稳定业务键 |
| `items[].title` | string | 是 | 标题 |
| `items[].content_hash` | string | 是 | 结构化源 SHA-256 |
| `items[].requirement_refs` | string[] | 是 | 需求引用 |
| `items[].module_refs` | string[] | 是 | 模块引用 |
| `items[].api_refs` | string[] | 是 | API 引用 |
| `items[].table_refs` | string[] | 是 | 数据表引用 |
| `items[].test_refs` | string[] | 是 | 测试引用 |
| `items[].baseline` | object | 是 | 当前阶段、版本、Commit 和 Tag |
| `items[].updated_at` | datetime | 是 | 投影更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "artifact_code": "API-000003",
      "stage": "API",
      "artifact_type": "API_ENDPOINT",
      "canonical_key": "order.cancel-batch",
      "title": "批量取消订单",
      "content_hash": "7b2d...",
      "requirement_refs": ["REQ-000012"],
      "module_refs": ["MOD-000004"],
      "api_refs": [],
      "table_refs": ["TABLE-000006"],
      "test_refs": ["TEST-000031"],
      "baseline": {
        "stage": "API",
        "version": 2,
        "git_commit_sha": "a4ce...",
        "git_tag": "baseline/api/v2"
      },
      "updated_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 获取批准产物详情

```http
GET /api/v2/projects/{project_id}/artifacts/{artifact_code}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `artifact_code` | string | 是 | 正式逻辑编号 |

**响应参数：** 与“查询批准产物”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "artifact_code": "API-000003",
  "stage": "API",
  "artifact_type": "API_ENDPOINT",
  "canonical_key": "order.cancel-batch",
  "title": "批量取消订单",
  "content_hash": "7b2d...",
  "requirement_refs": ["REQ-000012"],
  "module_refs": ["MOD-000004"],
  "api_refs": [],
  "table_refs": ["TABLE-000006"],
  "test_refs": ["TEST-000031"],
  "baseline": {
    "stage": "API",
    "version": 2,
    "git_commit_sha": "a4ce...",
    "git_tag": "baseline/api/v2"
  },
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 获取批准产物正文

```http
GET /api/v2/projects/{project_id}/artifacts/{artifact_code}/content
```

**路径参数：** `project_id`（uuid，必填）、`artifact_code`（string，必填）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `format` | string | 是 | `yaml` 或 `markdown` |

**响应参数：** 返回指定格式的文件正文，不使用 JSON 包装。

| 响应 Header | 类型 | 说明 |
| --- | --- | --- |
| `Content-Type` | string | `text/yaml` 或 `text/markdown` |
| `ETag` | string | 只用于内容缓存，由 Git Blob/Commit 计算 |

**响应示例：**

```yaml
artifact_code: API-000003
title: 批量取消订单
method: POST
path: /orders/batch-cancellations
```

---

## 阶段基线接口

### 查询阶段基线列表

```http
GET /api/v2/projects/{project_id}/baselines
```

**路径参数：** `project_id`（uuid，必填）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stage` | string | 否 | 阶段代码 |
| `cursor` | string | 否 | Git 历史游标 |
| `limit` | int | 否 | 默认 50，最大 200 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].stage` | string | 是 | 阶段代码 |
| `items[].version` | int | 是 | 基线版本 |
| `items[].git_commit_sha` | string | 是 | Commit SHA |
| `items[].git_tag` | string | 是 | 确定性 Tag |
| `items[].profile_version` | int | 是 | 生成时 Profile 版本 |
| `items[].profile_hash` | string | 是 | Profile SHA-256 |
| `items[].sealed_at` | datetime | 是 | 封存时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "stage": "API",
      "version": 2,
      "git_commit_sha": "a4ce...",
      "git_tag": "baseline/api/v2",
      "profile_version": 5,
      "profile_hash": "93af...",
      "sealed_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 获取阶段基线详情

```http
GET /api/v2/projects/{project_id}/baselines/{stage}/{version}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `stage` | string | 是 | 阶段代码 |
| `version` | int | 是 | 大于等于 1 的基线版本 |

**响应参数：** 除“查询阶段基线列表”单项字段外，增加：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `artifacts[]` | object[] | 是 | 该 Git 基线的批准产物列表 |

**响应示例：**

```json
{
  "stage": "API",
  "version": 2,
  "git_commit_sha": "a4ce...",
  "git_tag": "baseline/api/v2",
  "profile_version": 5,
  "profile_hash": "93af...",
  "sealed_at": "2026-08-06T10:00:00Z",
  "artifacts": [
    {"artifact_code": "API-000003", "title": "批量取消订单"}
  ]
}
```

---

### 获取历史基线产物正文

```http
GET /api/v2/projects/{project_id}/baselines/{stage}/{version}/artifacts/{artifact_code}
```

**路径参数：** `project_id`（uuid）、`stage`（string）、`version`（int）、`artifact_code`（string），均必填。

**查询参数：** `format`（string，必填，`yaml` 或 `markdown`）。

**响应参数：** 与“获取批准产物正文”一致，但内容固定读取指定历史 Git Tag/Commit。

**响应示例：**

```yaml
artifact_code: API-000003
baseline_version: 1
title: 批量取消订单
```

---

### 对比阶段基线

```http
GET /api/v2/projects/{project_id}/baseline-diffs
```

**路径参数：** `project_id`（uuid，必填）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stage` | string | 是 | 阶段代码 |
| `from_version` | int | 是 | 起始版本 |
| `to_version` | int | 是 | 目标版本 |
| `format` | string | 否 | `summary` 或 `unified`，默认 `summary` |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stage` | string | 是 | 阶段代码 |
| `from` | object | 是 | 起始基线引用 |
| `to` | object | 是 | 目标基线引用 |
| `summary` | string | 是 | 差异摘要 |
| `added[]` | object[] | 是 | 新增文件/产物 |
| `modified[]` | object[] | 是 | 修改文件/产物 |
| `deleted[]` | object[] | 是 | 删除文件/产物 |
| `unified_diff` | string/null | 否 | `format=unified` 时返回 |

**响应示例：**

```json
{
  "stage": "API",
  "from": {"version": 1, "git_commit_sha": "03ad..."},
  "to": {"version": 2, "git_commit_sha": "a4ce..."},
  "summary": "新增 1 个接口，修改 2 个接口",
  "added": [{"artifact_code": "API-000003"}],
  "modified": [{"artifact_code": "API-000001"}],
  "deleted": [],
  "unified_diff": null
}
```

---

### 下载阶段基线

```http
GET /api/v2/projects/{project_id}/baselines/{stage}/{version}/download
```

**路径参数：** `project_id`（uuid）、`stage`（string）、`version`（int），均必填。

**请求体参数：** 无。

**响应参数：**

| 响应 Header | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `Content-Type` | string | 是 | `application/zip` |
| `Content-Disposition` | string | 是 | UTF-8 下载文件名 |
| `ETag` | string | 是 | 下载缓存标识，不用于写并发 |
| `Digest` | string | 是 | ZIP 内容摘要 |

小文件返回 `200` 二进制；大文件可以返回 `303` 到短时签名地址。

---

### 下载全部批准产物

```http
GET /api/v2/projects/{project_id}/approved-package
```

**路径参数：** `project_id`（uuid，必填）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stages` | string[] | 否 | 指定阶段；缺省为全部已封存阶段 |

**响应参数：** 与“下载阶段基线”相同。生成前会固定所有目标阶段的 Commit/Tag，不混入草稿、诊断或附件原件。

---

## 项目变更接口

### 查询项目变更

```http
GET /api/v2/projects/{project_id}/changes
```

**路径参数：** `project_id`（uuid，必填）。

**查询参数：** `cursor`（string，否）、`limit`（int，否）、`status`（string，否）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | 变更 ID |
| `items[].status` | string | 是 | 变更状态 |
| `items[].summary` | string | 是 | 变更摘要 |
| `items[].source_message_id` | uuid | 是 | 发起消息 |
| `items[].target_artifact_codes` | string[] | 是 | 目标产物编号 |
| `items[].impact` | object/null | 否 | 影响产物、阶段和理由 |
| `items[].allowed_decisions` | string[] | 是 | 当前允许的决议 |
| `items[].decision_git_commit_sha` | string/null | 否 | 终态决议 Commit |
| `items[].last_error` | object/null | 否 | 可行动错误 |
| `items[].created_at` | datetime | 是 | 创建时间 |
| `items[].updated_at` | datetime | 是 | 更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "e39a448f-b564-4884-9341-6d9942501ba2",
      "status": "WAITING_FOR_HUMAN",
      "summary": "增加批量取消订单能力",
      "source_message_id": "f444337e-bec5-48b2-be20-bb45db96f228",
      "target_artifact_codes": ["API-000003"],
      "impact": {"stages": ["API", "TEST"]},
      "allowed_decisions": ["APPROVE", "REJECT"],
      "decision_git_commit_sha": null,
      "last_error": null,
      "created_at": "2026-08-06T10:00:00Z",
      "updated_at": "2026-08-06T10:01:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 获取项目变更详情

```http
GET /api/v2/projects/{project_id}/changes/{change_id}
```

**路径参数：** `project_id`（uuid，必填）、`change_id`（uuid，必填）。

**响应参数：** 与“查询项目变更”的单个 `items[]` 对象相同，并可返回完整 `impact` 和 `base_baselines`。

**响应示例：**

```json
{
  "id": "e39a448f-b564-4884-9341-6d9942501ba2",
  "status": "WAITING_FOR_HUMAN",
  "summary": "增加批量取消订单能力",
  "source_message_id": "f444337e-bec5-48b2-be20-bb45db96f228",
  "target_artifact_codes": ["API-000003"],
  "base_baselines": [{"stage": "API", "version": 2}],
  "impact": {"stages": ["API", "TEST"], "reason": "接口契约变化"},
  "allowed_decisions": ["APPROVE", "REJECT"],
  "decision_git_commit_sha": null,
  "last_error": null,
  "created_at": "2026-08-06T10:00:00Z",
  "updated_at": "2026-08-06T10:01:00Z"
}
```

---

### 提交项目变更决议

```http
POST /api/v2/projects/{project_id}/changes/{change_id}/decisions
```

**路径参数：** `project_id`（uuid，必填）、`change_id`（uuid，必填）。

**请求头参数：** `Idempotency-Key`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expected_status` | string | 是 | 页面所见 Change 状态 |
| `decision` | string | 是 | `APPROVE/REJECT/WITHDRAW` |
| `comment` | string/null | 否 | 决议说明 |

**请求示例：**

```json
{
  "expected_status": "WAITING_FOR_HUMAN",
  "decision": "APPROVE",
  "comment": "同意重建 API 和 TEST 基线"
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `change` | object | 是 | 决议后的 Change 对象 |
| `run` | object/null | 否 | 启动重新基线化时的 Run |
| `decision_message` | object | 是 | 共享时间线决议消息 |

**响应示例：**

```json
{
  "change": {"id": "e39a448f-b564-4884-9341-6d9942501ba2", "status": "APPROVED"},
  "run": {"run_id": "527607b4-a693-457f-a3a7-03799ebfa2a6", "status": "QUEUED"},
  "decision_message": {"id": "25890f40-fd13-4376-bc3c-08189bc2b950", "content": "批准项目变更"}
}
```

成功返回 `202 Accepted`。

---

### 重试失败项目变更

```http
POST /api/v2/projects/{project_id}/changes/{change_id}/retries
```

**路径参数：** `project_id`（uuid，必填）、`change_id`（uuid，必填）。

**请求体参数：** `expected_status`（string，必填，必须为 `FAILED`）。

**请求示例：**

```json
{"expected_status": "FAILED"}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `change` | object | 是 | 重试后的 Change 对象 |
| `run` | object | 是 | 新的当前 Run 投影 |
| `decision_message` | null | 是 | 重试不是新业务决议，因此为空 |

**响应示例：**

```json
{
  "change": {"id": "e39a448f-b564-4884-9341-6d9942501ba2", "status": "APPLYING"},
  "run": {"run_id": "527607b4-a693-457f-a3a7-03799ebfa2a6", "status": "QUEUED"},
  "decision_message": null
}
```

---

## 管理员用户接口

### 查询用户列表

```http
GET /api/v2/admin/users
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `cursor` | string | 否 | 上一页游标 |
| `limit` | int | 否 | 默认 50，最大 200 |
| `status` | string | 否 | `ACTIVE/DISABLED` |
| `q` | string | 否 | 用户名或显示名关键词 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | 用户 ID |
| `items[].username` | string | 是 | 登录名 |
| `items[].display_name` | string | 是 | 显示名 |
| `items[].system_role` | string | 是 | `ADMIN/USER` |
| `items[].status` | string | 是 | `ACTIVE/DISABLED` |
| `items[].must_change_password` | bool | 是 | 是否必须修改密码 |
| `items[].last_login_at` | datetime/null | 否 | 最近登录 |
| `items[].created_at` | datetime | 是 | 创建时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "b133dd60-efbd-4a41-a339-13223795c256",
      "username": "admin",
      "display_name": "管理员",
      "system_role": "ADMIN",
      "status": "ACTIVE",
      "must_change_password": false,
      "last_login_at": "2026-08-06T09:00:00Z",
      "created_at": "2026-08-01T09:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 创建用户

```http
POST /api/v2/admin/users
```

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 唯一登录名 |
| `display_name` | string | 是 | 显示名 |
| `temporary_password` | string | 是 | 初始临时密码 |
| `system_role` | string | 是 | `ADMIN/USER` |

**请求示例：**

```json
{
  "username": "lisi",
  "display_name": "李四",
  "temporary_password": "temporary-password",
  "system_role": "USER"
}
```

**响应参数：** 与“查询用户列表”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "id": "518784f6-0d50-48f8-bbca-4acd3f8740f1",
  "username": "lisi",
  "display_name": "李四",
  "system_role": "USER",
  "status": "ACTIVE",
  "must_change_password": true,
  "last_login_at": null,
  "created_at": "2026-08-06T10:00:00Z"
}
```

成功返回 `201 Created`。

---

### 获取用户详情

```http
GET /api/v2/admin/users/{user_id}
```

**路径参数：** `user_id`（uuid，必填，用户 ID）。

**响应参数：** 与“查询用户列表”的单个 `items[]` 对象相同。

**响应示例：**

```json
{
  "id": "518784f6-0d50-48f8-bbca-4acd3f8740f1",
  "username": "lisi",
  "display_name": "李四",
  "system_role": "USER",
  "status": "ACTIVE",
  "must_change_password": false,
  "last_login_at": "2026-08-06T09:00:00Z",
  "created_at": "2026-08-01T09:00:00Z"
}
```

---

### 修改用户

```http
PATCH /api/v2/admin/users/{user_id}
```

**路径参数：** `user_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `display_name` | string | 否 | 新显示名 |
| `system_role` | string | 否 | `ADMIN/USER` |
| `status` | string | 否 | `ACTIVE/DISABLED` |

至少提交一个字段。不能提交密码 Hash、Salt 或 Session。

**请求示例：**

```json
{"status": "DISABLED"}
```

**响应参数：** 与“查询用户列表”的单个对象相同。

**响应示例：**

```json
{
  "id": "518784f6-0d50-48f8-bbca-4acd3f8740f1",
  "username": "lisi",
  "display_name": "李四",
  "system_role": "USER",
  "status": "DISABLED",
  "must_change_password": false,
  "last_login_at": "2026-08-06T09:00:00Z",
  "created_at": "2026-08-01T09:00:00Z"
}
```

禁用更新数据库与 Redis 用户缓存状态，但不删除 Session。

---

### 管理员设置用户密码

```http
PUT /api/v2/admin/users/{user_id}/password
```

**路径参数：** `user_id`（uuid，必填）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `new_password` | string | 是 | 新临时密码 |
| `must_change_password` | bool | 是 | 是否要求用户修改 |

**请求示例：**

```json
{
  "new_password": "new-temporary-password",
  "must_change_password": true
}
```

**响应参数：** `result`（string）和 `occurred_at`（datetime），均必填。

**响应示例：**

```json
{
  "result": "APPLIED",
  "occurred_at": "2026-08-06T10:00:00Z"
}
```

不建立密码重置表，也不撤销现有 Session。


---

## 项目成员管理接口

### 新增或修改项目成员

```http
PUT /api/v2/projects/{project_id}/members/{user_id}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `user_id` | uuid | 是 | 目标用户 ID |

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `role` | string | 是 | `OWNER/MEMBER/VIEWER` |

**请求示例：**

```json
{"role": "MEMBER"}
```

**响应参数：** 与“查询项目成员”的单个成员对象相同。

**响应示例：**

```json
{
  "user_id": "518784f6-0d50-48f8-bbca-4acd3f8740f1",
  "username": "lisi",
  "display_name": "李四",
  "role": "MEMBER",
  "created_at": "2026-08-06T10:00:00Z"
}
```

**主要错误码：** `LAST_OWNER_REQUIRED`、`POLICY_REJECTED`。

---

### 删除项目成员

```http
DELETE /api/v2/projects/{project_id}/members/{user_id}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `user_id` | uuid | 是 | 目标用户 ID |

**响应参数：** 无，成功返回 `204 No Content`。

**主要错误码：** `LAST_OWNER_REQUIRED`、`MEMBER_NOT_FOUND`、`POLICY_REJECTED`。

---

## 项目消息接口

### 查询项目消息

```http
GET /api/v2/projects/{project_id}/messages
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `cursor` | string | 否 | 上一页游标 |
| `limit` | int | 否 | 默认 50，最大 200 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items[].id` | uuid | 是 | 服务端生成的 Message ID |
| `items[].user_id` | uuid/null | 否 | 用户消息提交者 |
| `items[].role` | string | 是 | `USER/ASSISTANT/SYSTEM` |
| `items[].agent_role` | string/null | 否 | 助手专业角色 |
| `items[].content` | string | 是 | 当前可见正文 |
| `items[].delivery_mode` | string/null | 否 | `DIRECT/STEER/QUEUE` |
| `items[].target_run_id` | uuid/null | 否 | 目标 Run |
| `items[].status` | string | 是 | 消息状态 |
| `items[].process_version` | int | 是 | SSE 恢复版本 |
| `items[].stopped_by_user_id` | uuid/null | 否 | 取消/中断操作者 |
| `items[].stopped_at` | datetime/null | 否 | 取消/中断时间 |
| `items[].created_at` | datetime | 是 | 创建时间 |
| `items[].updated_at` | datetime | 是 | 更新时间 |
| `next_cursor` | string/null | 否 | 下一页游标 |

**响应示例：**

```json
{
  "items": [
    {
      "id": "f444337e-bec5-48b2-be20-bb45db96f228",
      "user_id": "b133dd60-efbd-4a41-a339-13223795c256",
      "role": "USER",
      "agent_role": null,
      "content": "补充批量取消订单",
      "delivery_mode": "STEER",
      "target_run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
      "status": "COMPLETED",
      "process_version": 0,
      "stopped_by_user_id": null,
      "stopped_at": null,
      "created_at": "2026-08-06T10:00:00Z",
      "updated_at": "2026-08-06T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

---

### 获取单条项目消息

```http
GET /api/v2/projects/{project_id}/messages/{message_id}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `message_id` | uuid | 是 | Message ID |

**响应参数：** 除“查询项目消息”中的字段外，增加：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `process[].event_id` | uuid | 是 | 过程事件 ID |
| `process[].type` | string | 是 | 过程事件类型 |
| `process[].stage` | string/null | 否 | 所属阶段 |
| `process[].agent_role` | string/null | 否 | Agent 角色 |
| `process[].summary` | string | 是 | 用户可见摘要 |
| `process[].occurred_at` | datetime | 是 | 发生时间 |

**响应示例：**

```json
{
  "id": "f73de800-074b-42b6-858e-66559857ec36",
  "role": "ASSISTANT",
  "agent_role": "PM",
  "content": "正在完善需求模块。",
  "delivery_mode": null,
  "target_run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "status": "RUNNING",
  "process_version": 1,
  "process": [
    {
      "event_id": "6dc34a73-c2c0-48ea-b7c9-d405c069030b",
      "type": "STAGE_STARTED",
      "stage": "REQUIREMENT_MODULE",
      "agent_role": "AUTHOR",
      "summary": "开始生成需求模块",
      "occurred_at": "2026-08-06T10:01:00Z"
    }
  ],
  "created_at": "2026-08-06T10:00:00Z",
  "updated_at": "2026-08-06T10:01:00Z"
}
```

---

### 提交项目消息

```http
POST /api/v2/projects/{project_id}/messages
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求头参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `Idempotency-Key` | uuid | 是 | 本次消息提交重试标识，不是 Message ID |

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content` | string | 是 | 用户消息，去除首尾空白后不能为空 |
| `delivery_mode` | string | 是 | `DIRECT/STEER/QUEUE` |
| `expected_run_id` | uuid/null | 条件 | `STEER` 必填；其他模式为空 |

**请求示例：**

```json
{
  "content": "批量取消订单也需要记录原因",
  "delivery_mode": "STEER",
  "expected_run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54"
}
```

带附件时改用 `multipart/form-data`：`metadata` 为上述 JSON，`files[]` 为附件流。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message.id` | uuid | 是 | 服务端生成的 Message ID |
| `message.status` | string | 是 | 当前消息状态 |
| `message.delivery_mode` | string | 是 | 实际持久化模式 |
| `message.target_run_id` | uuid/null | 否 | 目标 Run |
| `response_message_id` | uuid/null | 否 | 新 Run 对应助手消息 |
| `routing.requested_mode` | string | 是 | 请求模式 |
| `routing.effective_mode` | string | 是 | 实际模式 |
| `routing.conversion_reason` | string/null | 否 | 自动转 Queue 原因 |
| `current_run` | object/null | 否 | 当前 Run 摘要 |
| `conversation` | object | 是 | 当前占用摘要 |

**响应示例：**

```json
{
  "message": {
    "id": "f444337e-bec5-48b2-be20-bb45db96f228",
    "status": "QUEUED",
    "delivery_mode": "QUEUE",
    "target_run_id": null
  },
  "response_message_id": null,
  "routing": {
    "requested_mode": "STEER",
    "effective_mode": "QUEUE",
    "conversion_reason": "ATOMIC_SECTION"
  },
  "current_run": {
    "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
    "status": "RUNNING"
  },
  "conversation": {
    "owner_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
    "expires_at": "2026-08-06T10:09:00Z"
  }
}
```

成功返回 `202 Accepted`。主要错误码：`CONVERSATION_OCCUPIED`、`INVALID_DELIVERY_MODE`、`RUN_ID_MISMATCH`、`IDEMPOTENCY_KEY_REUSED`、`PROFILE_MIGRATION_FAILED`。

---

### 取消排队消息

```http
POST /api/v2/projects/{project_id}/messages/{message_id}/cancellations
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `message_id` | uuid | 是 | 待取消的 Queue Message ID |

**请求体参数：** 无。

**响应参数：** 返回取消后的完整 Message 对象，字段与“获取单条项目消息”一致，其中 `status=CANCELLED`、`stopped_by_user_id` 和 `stopped_at` 必填。

**响应示例：**

```json
{
  "id": "f444337e-bec5-48b2-be20-bb45db96f228",
  "role": "USER",
  "content": "稍后调整接口",
  "delivery_mode": "QUEUE",
  "status": "CANCELLED",
  "stopped_by_user_id": "b133dd60-efbd-4a41-a339-13223795c256",
  "stopped_at": "2026-08-06T10:05:00Z"
}
```

**主要错误码：** `MESSAGE_NOT_CANCELLABLE`、`POLICY_REJECTED`。

---

### 释放项目对话占用

```http
POST /api/v2/projects/{project_id}/conversation-releases
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求体参数：** 无。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `owner_user_id` | uuid/null | 否 | 释放后为空 |
| `expires_at` | datetime/null | 否 | 释放后为空 |
| `allowed_delivery_modes` | string[] | 是 | 释放后当前用户可选模式 |
| `can_release` | bool | 是 | 释放后为 false |

**响应示例：**

```json
{
  "owner_user_id": null,
  "expires_at": null,
  "allowed_delivery_modes": ["DIRECT"],
  "can_release": false
}
```

**主要错误码：** `CONVERSATION_RELEASE_NOT_ALLOWED`。

---

## Current Run 接口

### 获取当前 Run

```http
GET /api/v2/projects/{project_id}/run
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | uuid | 是 | 当前逻辑 Run ID |
| `status` | string | 是 | Run 状态 |
| `trigger_message_id` | uuid | 是 | 触发消息 |
| `response_message_id` | uuid | 是 | 助手消息 |
| `retry_count` | int | 是 | 当前 Run 累计重试次数 |
| `started_at` | datetime | 是 | 启动时间 |
| `updated_at` | datetime | 是 | 更新时间 |
| `last_error` | object/null | 否 | 脱敏后的可行动错误 |
| `allowed_actions` | string[] | 是 | 当前用户可执行动作 |

**响应示例：**

```json
{
  "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "status": "RUNNING",
  "trigger_message_id": "f444337e-bec5-48b2-be20-bb45db96f228",
  "response_message_id": "f73de800-074b-42b6-858e-66559857ec36",
  "retry_count": 0,
  "started_at": "2026-08-06T10:00:00Z",
  "updated_at": "2026-08-06T10:05:00Z",
  "last_error": null,
  "allowed_actions": ["INTERRUPT"]
}
```

无当前 Run 返回 `404 CURRENT_RUN_NOT_FOUND`。

---

### 中断当前 Run

```http
POST /api/v2/projects/{project_id}/run/interruptions
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expected_run_id` | uuid | 是 | 页面所见 Run，防止误停新 Run |

**请求示例：**

```json
{"expected_run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54"}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | uuid | 是 | 被中断 Run |
| `status` | string | 是 | `STOPPING` 或已完成的 `INTERRUPTED` |
| `response_message_id` | uuid | 是 | 最终状态所在助手消息 |
| `accepted_at` | datetime | 是 | 接受时间 |
| `stop_mode` | string | 是 | `AT_NEXT_SAFE_CHECKPOINT` |

**响应示例：**

```json
{
  "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "status": "STOPPING",
  "response_message_id": "f73de800-074b-42b6-858e-66559857ec36",
  "accepted_at": "2026-08-06T10:06:00Z",
  "stop_mode": "AT_NEXT_SAFE_CHECKPOINT"
}
```

成功返回 `202 Accepted`。主要错误码：`RUN_ID_MISMATCH`、`RUN_STATE_CONFLICT`、`POLICY_REJECTED`。

---

### 重试失败 Run

```http
POST /api/v2/projects/{project_id}/run/retries
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求体参数：** `expected_run_id`（uuid，必填，只能指向 `FAILED` Run）。

**响应参数：** 与“中断当前 Run”相同，但 `stop_mode` 为空，`status` 通常为 `QUEUED`。

**响应示例：**

```json
{
  "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "status": "QUEUED",
  "response_message_id": "f73de800-074b-42b6-858e-66559857ec36",
  "accepted_at": "2026-08-06T10:06:00Z",
  "stop_mode": null
}
```

**主要错误码：** `RUN_ID_MISMATCH`、`RUN_NOT_FAILED`。

---

### 放弃失败 Run

```http
POST /api/v2/projects/{project_id}/run/abandonments
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求体参数：** `expected_run_id`（uuid，必填，只能指向 `FAILED` Run）。

**响应参数：** 与“中断当前 Run”相同，但 `stop_mode` 为空，`status` 为 `CANCELLED`。

**响应示例：**

```json
{
  "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "status": "CANCELLED",
  "response_message_id": "f73de800-074b-42b6-858e-66559857ec36",
  "accepted_at": "2026-08-06T10:06:00Z",
  "stop_mode": null
}
```

**主要错误码：** `RUN_ID_MISMATCH`、`RUN_NOT_FAILED`。

---

## Human Gate 接口

### 获取当前 Human Gate

```http
GET /api/v2/projects/{project_id}/human-gate
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `gate_id` | string | 是 | 不透明 Gate 标识 |
| `run_id` | uuid | 是 | 等待中的 Run |
| `type` | string | 是 | Gate 类型 |
| `title` | string | 是 | 标题 |
| `question` | string | 是 | 待决策问题 |
| `context` | object | 是 | 变化、假设、排除项和影响 |
| `allowed_decisions` | string[] | 是 | 可提交决议 |
| `options` | object[] | 是 | 可选方案 |
| `requested_at` | datetime | 是 | 发起时间 |

**响应示例：**

```json
{
  "gate_id": "prd-approval-3",
  "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "type": "PRD_APPROVAL",
  "title": "确认 PRD",
  "question": "是否批准当前 PRD？",
  "context": {"changed": ["补充批量取消订单"]},
  "allowed_decisions": ["APPROVE", "REQUEST_REVISION"],
  "options": [],
  "requested_at": "2026-08-06T10:00:00Z"
}
```

无当前 Gate 返回 `404 HUMAN_GATE_NOT_ACTIVE`。

---

### 提交 Human Gate 决议

```http
POST /api/v2/projects/{project_id}/human-gate/decisions
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**请求头参数：** `Idempotency-Key`（uuid，必填，决议消息重试标识）。

**请求体参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `expected_run_id` | uuid | 是 | 当前等待 Run |
| `gate_id` | string | 是 | GET Gate 返回的标识 |
| `decision` | string | 是 | 必须属于 `allowed_decisions` |
| `selected_option` | string/null | 条件 | Gate 要求选择方案时必填 |
| `comment` | string/null | 否 | OWNER 补充说明 |

**请求示例：**

```json
{
  "expected_run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
  "gate_id": "prd-approval-3",
  "decision": "APPROVE",
  "selected_option": null,
  "comment": "范围确认无误"
}
```

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `decision_message.id` | uuid | 是 | 共享时间线决议消息 |
| `decision_message.content` | string | 是 | 决议可见文本 |
| `gate_id` | string | 是 | 被处理 Gate |
| `decision` | string | 是 | 实际决议 |
| `run.run_id` | uuid | 是 | 恢复的 Run |
| `run.status` | string | 是 | 通常为 `QUEUED` 或 `RUNNING` |

**响应示例：**

```json
{
  "decision_message": {
    "id": "01ac9e56-489d-4d10-8ccb-300367ef04ce",
    "content": "批准 PRD：范围确认无误"
  },
  "gate_id": "prd-approval-3",
  "decision": "APPROVE",
  "run": {
    "run_id": "db43066d-5ae7-4943-afc8-d1b83eac0f54",
    "status": "QUEUED"
  }
}
```

成功返回 `202 Accepted`。主要错误码：`HUMAN_GATE_MISMATCH`、`HUMAN_GATE_ALREADY_RESOLVED`、`IDEMPOTENCY_KEY_REUSED`。

---

## 阶段接口

### 查询项目阶段

```http
GET /api/v2/projects/{project_id}/stages
```

**路径参数：** `project_id`（uuid，必填，项目 ID）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].stage` | string | 是 | 阶段代码 |
| `[].status` | string | 是 | 阶段状态 |
| `[].revision` | int | 是 | 阶段修订号 |
| `[].baseline_version` | int | 是 | 0 表示未封存 |
| `[].baseline` | object/null | 否 | 当前 Commit、Tag 和版本 |
| `[].candidate_count` | int | 是 | 当前草稿数量 |
| `[].quality_issue_count` | int | 是 | 未解决质量问题数 |
| `[].last_error` | object/null | 否 | 脱敏错误 |
| `[].updated_at` | datetime | 是 | 更新时间 |

**响应示例：**

```json
[
  {
    "stage": "API",
    "status": "BUILDING",
    "revision": 4,
    "baseline_version": 0,
    "baseline": null,
    "candidate_count": 8,
    "quality_issue_count": 2,
    "last_error": null,
    "updated_at": "2026-08-06T10:00:00Z"
  }
]
```

---

### 获取单个阶段

```http
GET /api/v2/projects/{project_id}/stages/{stage}
```

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | uuid | 是 | 项目 ID |
| `stage` | string | 是 | 固定阶段代码 |

**响应参数：** 与“查询项目阶段”的单个阶段对象相同。

**响应示例：**

```json
{
  "stage": "API",
  "status": "BUILDING",
  "revision": 4,
  "baseline_version": 0,
  "baseline": null,
  "candidate_count": 8,
  "quality_issue_count": 2,
  "last_error": null,
  "updated_at": "2026-08-06T10:00:00Z"
}
```

---

### 查询阶段草稿

```http
GET /api/v2/projects/{project_id}/stages/{stage}/drafts
```

**路径参数：** `project_id`（uuid，必填）、`stage`（string，必填）。

**查询参数：** `artifact_type`（string，非必填，按产物类型过滤）。

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].id` | uuid | 是 | 草稿 ID，不是正式编号 |
| `[].stage` | string | 是 | 所属阶段 |
| `[].artifact_type` | string | 是 | 产物类型 |
| `[].canonical_key` | string | 是 | 稳定业务键 |
| `[].operation` | string | 是 | `CREATE/UPDATE/DELETE` |
| `[].title` | string | 是 | 标题 |
| `[].body` | object | 是 | 受版本化 JSON Schema 约束的正文 |
| `[].status` | string | 是 | 草稿状态 |
| `[].validation` | object | 是 | 确定性校验摘要 |
| `[].review` | object | 是 | 语义评审摘要 |
| `[].updated_at` | datetime | 是 | 更新时间 |

**响应示例：**

```json
[
  {
    "id": "4beb76bd-cd72-4095-b22f-80fa8ca1bc67",
    "stage": "API",
    "artifact_type": "API_ENDPOINT",
    "canonical_key": "order.cancel-batch",
    "operation": "CREATE",
    "title": "批量取消订单",
    "body": {"method": "POST", "path": "/orders/batch-cancellations"},
    "status": "REVISING",
    "validation": {"valid": false, "issue_count": 1},
    "review": {"passed": false, "finding_count": 1},
    "updated_at": "2026-08-06T10:00:00Z"
  }
]
```

---

### 查询阶段质量问题

```http
GET /api/v2/projects/{project_id}/stages/{stage}/quality-findings
```

**路径参数：** `project_id`（uuid，必填）、`stage`（string，必填）。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `severity` | string | 否 | 按严重度过滤 |
| `status` | string | 否 | 按问题状态过滤 |

**响应参数：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `[].finding_id` | string | 是 | 当前草稿内稳定问题 ID |
| `[].draft_id` | uuid | 是 | 草稿 ID |
| `[].source` | string | 是 | `VALIDATOR/REVIEWER/CONVERGENCE` |
| `[].code` | string | 是 | 问题代码 |
| `[].severity` | string | 是 | 严重度 |
| `[].status` | string | 是 | 当前状态 |
| `[].message` | string | 是 | 问题说明 |
| `[].field_path` | string/null | 否 | 结构化字段路径 |
| `[].requirement_refs` | string[] | 是 | 关联需求编号 |

**响应示例：**

```json
[
  {
    "finding_id": "API-F-001",
    "draft_id": "4beb76bd-cd72-4095-b22f-80fa8ca1bc67",
    "source": "CONVERGENCE",
    "code": "FIELD_TYPE_MISMATCH",
    "severity": "ERROR",
    "status": "OPEN",
    "message": "order_id 与数据库设计类型不一致",
    "field_path": "request.items[].order_id",
    "requirement_refs": ["REQ-000012"]
  }
]
```

# AI 测试用例生成平台 - API 接口文档

## 概述

本文档描述 AI Case Generator Demo 的 RESTful API 接口设计。

---

## 基础信息

| 项目 | 说明 |
|------|------|
| 基础 URL | `/api/v1` |
| 数据格式 | JSON |
| 认证方式 | 无（本地应用） |
| 字符编码 | UTF-8 |

---

## 通用响应格式

### 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### 错误响应

```json
{
  "code": 400,
  "message": "错误描述",
  "error": "详细错误信息"
}
```

### 分页响应

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "pages": 5
  }
}
```

---

## 项目接口 (Projects)

### 创建项目

```
POST /api/v1/projects
```

**请求体：**

```json
{
  "name": "用户中心系统",
  "description": "用户注册、登录、权限管理模块"
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "用户中心系统",
    "description": "用户注册、登录、权限管理模块",
    "status": "draft",
    "created_at": "2026-03-30T20:00:00Z"
  }
}
```

---

### 查询项目列表

```
GET /api/v1/projects
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| status | string | 否 | 筛选状态 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "用户中心系统",
        "description": "...",
        "status": "draft",
        "created_at": "2026-03-30T20:00:00Z"
      }
    ],
    "total": 10,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 获取项目详情

```
GET /api/v1/projects/{project_id}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "用户中心系统",
    "description": "...",
    "requirement_content": "支持手机号注册...",
    "requirement_optimized_content": "优化后的需求...",
    "requirement_file_paths": ["/data/req1.pdf", "/data/req2.docx"],
    "requirement_analysis_result": "需求结构清晰...",
    "requirement_risks": ["验证码有效期未定义"],
    "requirement_unclear_points": ["是否支持第三方登录"],
    "requirement_status": "pending",
    "status": "draft",
    "created_at": "2026-03-30T20:00:00Z",
    "updated_at": "2026-03-30T21:00:00Z",
    "stats": {
      "modules_count": 12,
      "test_cases_count": 100,
      "apis_count": 25
    }
  }
}
```

---

### 更新项目

```
PUT /api/v1/projects/{project_id}
```

**请求体：**

```json
{
  "name": "用户中心系统 V2",
  "description": "更新描述",
  "status": "active"
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "用户中心系统 V2",
    "description": "更新描述",
    "status": "active",
    "updated_at": "2026-03-30T22:00:00Z"
  }
}
```

---

### 删除项目

```
DELETE /api/v1/projects/{project_id}
```

**说明：** 删除项目及其所有关联数据

**响应：**

```json
{
  "code": 200,
  "data": {
    "message": "删除成功"
  }
}
```

---

## 需求讨论接口 (Requirement Discussion)

### 需求对话

```
POST /api/v1/projects/{project_id}/requirement/discuss
```

**说明：** 与 AI 进行需求讨论，可迭代调整需求内容，支持上传需求文件。**调用后需求状态会重置为 pending**

**请求格式：** `multipart/form-data`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 对话消息 |
| files | file | 否 | 需求文件（支持 PDF/Word/Markdown） |

**请求示例：**

```
POST /api/v1/projects/{project_id}/requirement/discuss
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="message"

用户注册需要支持邮箱注册
--boundary
Content-Disposition: form-data; name="files"; filename="req.pdf"
Content-Type: application/pdf

[binary content]
--boundary--
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "response": "好的，我理解了需求变更。新增邮箱注册方式需要以下字段：\n1. 邮箱地址（必填）\n2. 邮箱验证码（必填）\n\n是否需要我更新需求文档？",
    "suggested_changes": {
      "requirement_optimized_content": "更新后的需求内容...",
      "new_risks": ["邮箱验证码有效期问题"],
      "new_unclear_points": ["是否需要邮箱激活链接"]
    }
  }
}
```

---

### 需求变更确认

```
POST /api/v1/projects/{project_id}/requirement/accept
```

**说明：** 确认需求变更，将 AI 建议的变更内容应用到需求中

**响应：**

```json
{
  "code": 200,
  "data": {
    "requirement_optimized_content": "更新后的需求内容...",
    "requirement_risks": ["邮箱验证码有效期问题"],
    "requirement_unclear_points": ["是否需要邮箱激活链接"],
    "requirement_status": "pending"
  }
}
```

---

### 需求变更拒绝

```
POST /api/v1/projects/{project_id}/requirement/reject
```

**说明：** 拒绝需求变更，保持当前需求内容

**响应：**

```json
{
  "code": 200,
  "data": {
    "message": "已拒绝变更，当前需求内容保持不变"
  }
}
```

---

### 确认需求

```
POST /api/v1/projects/{project_id}/requirement/confirm
```

**说明：** 确认需求，触发后续模块拆分。**前置条件：requirement_risks 和 requirement_unclear_points 必须为空**

**前置校验：**
- requirement_risks = []
- requirement_unclear_points = []

**响应：**

```json
{
  "code": 200,
  "data": {
    "requirement_status": "confirmed"
  }
}
```

---

## 模块接口 (Modules)

### 查询模块列表

```
GET /api/v1/projects/{project_id}/modules
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| parent_id | string | 否 | 父级模块ID |
| status | string | 否 | 状态筛选 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "module_1",
        "project_id": "project_1",
        "parent_id": null,
        "name": "用户中心",
        "description": "用户相关功能模块",
        "priority": 1,
        "status": "draft",
        "created_at": "2026-03-30T20:00:00Z",
        "updated_at": "2026-03-30T21:00:00Z"
      },
      {
        "id": "module_2",
        "project_id": "project_1",
        "parent_id": "module_1",
        "name": "用户注册",
        "description": "用户注册功能",
        "priority": 1,
        "status": "analyzed",
        "created_at": "2026-03-30T20:00:00Z",
        "updated_at": "2026-03-30T21:00:00Z"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 获取模块树形结构

```
GET /api/v1/projects/{project_id}/modules/tree
```

**响应：**

```json
{
  "code": 200,
  "data": [
    {
      "id": "module_1",
      "name": "用户中心",
      "status": "draft",
      "children": [
        {
          "id": "module_2",
          "name": "用户注册",
          "status": "analyzed",
          "children": []
        },
        {
          "id": "module_3",
          "name": "用户登录",
          "status": "draft",
          "children": []
        }
      ]
    }
  ]
}
```

---

### AI 分析模块

```
POST /api/v1/projects/{project_id}/modules/analyze
```

**说明：** AI 分析模块，自动拆分生成子模块。**前置条件：需求状态必须为 confirmed**

**前置校验：**
- 需求状态 requirement_status = 'confirmed'

**响应：**

```json
{
  "code": 200,
  "data": {
    "modules": [
      {
        "id": "module_1",
        "name": "用户注册模块",
        "description": "处理用户注册相关逻辑",
        "priority": 1,
        "status": "draft"
      },
      {
        "id": "module_2",
        "name": "验证码模块",
        "description": "处理验证码发送和验证",
        "priority": 2,
        "status": "draft"
      }
    ]
  }
}
```

---

## 模块讨论接口 (Module Discussion)

### 模块对话

```
POST /api/v1/modules/{module_id}/discuss
```

**说明：** 与 AI 进行模块讨论，可拆分或合并模块

**请求体：**

```json
{
  "message": "用户注册模块和验证码模块可以合并为一个模块"
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "response": "好的，我将用户注册模块和验证码模块合并为一个模块。",
    "suggested_changes": {
      "modules_tree": [
        {
          "id": "module_new",
          "name": "注册认证模块",
          "status": "draft",
          "description": "整合用户注册和验证码功能",
          "children": []
        }
      ]
    }
  }
}
```

---

### 模块变更确认

```
POST /api/v1/modules/{module_id}/accept
```

**说明：** 确认模块变更，删除历史模块并根据 modules_tree 重建

**响应：**

```json
{
  "code": 200,
  "data": {
    "modules_tree": [
      {
        "id": "module_new",
        "name": "注册认证模块",
        "status": "analyzed",
        "description": "整合用户注册和验证码功能",
        "children": []
      }
    ]
  }
}
```

---

### 模块变更拒绝

```
POST /api/v1/modules/{module_id}/reject
```

**说明：** 拒绝模块变更，保持当前模块结构

**响应：**

```json
{
  "code": 200,
  "data": {
    "message": "已拒绝变更，当前模块结构保持不变"
  }
}
```

---

### 确认模块

```
POST /api/v1/modules/{module_id}/confirm
```

**说明：** 确认模块，触发后续测试用例和接口生成

**响应：**

```json
{
  "code": 200,
  "data": {
    "status": "confirmed"
  }
}
```

---

## 测试用例接口 (Test Cases)

### 查询测试用例列表

```
GET /api/v1/projects/{project_id}/test-cases
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| module_id | string | 否 | 关联模块ID |
| level | string | 否 | P0/P1/P2/P3 |
| type | string | 否 | functional/interface/performance |
| status | string | 否 | 状态筛选 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "tc_1",
        "project_id": "project_1",
        "module_id": "module_1",
        "title": "注册成功-手机号验证通过",
        "precondition": "手机号未注册，验证码正确",
        "test_steps": [
          {"step": 1, "action": "输入手机号", "expected": ""},
          {"step": 2, "action": "输入验证码", "expected": ""},
          {"step": 3, "action": "点击注册", "expected": "注册成功，跳转首页"}
        ],
        "test_data": {
          "phone": "13800138000",
          "code": "123456"
        },
        "level": "P0",
        "type": "functional",
        "status": "draft",
        "tags": ["注册", "正向"],
        "created_at": "2026-03-30T20:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

### AI 生成测试用例

```
POST /api/v1/modules/{module_id}/generate-test-cases
```

**请求体：**

```json
{
  "count": 20,
  "types": ["functional", "interface"],
  "levels": ["P0", "P1", "P2"]
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "generated_count": 20,
    "test_cases": [
      {
        "id": "tc_1",
        "module_id": "module_1",
        "title": "注册成功-手机号验证通过",
        "precondition": "手机号未注册，验证码正确",
        "test_steps": [...],
        "test_data": {...},
        "level": "P0",
        "type": "functional",
        "status": "draft"
      }
    ]
  }
}
```

---

### 导出测试用例

```
GET /api/v1/projects/{project_id}/test-cases/export
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| format | string | 否 | excel/csv/json，默认 excel |
| module_id | string | 否 | 筛选模块 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "file_path": "/data/exports/test_cases_20260330.xlsx",
    "download_url": "/api/v1/files/download/test_cases_20260330.xlsx"
  }
}
```

---

## 接口设计接口 (APIs)

### AI 生成接口设计

```
POST /api/v1/modules/{module_id}/generate-apis
```

**说明：** AI 根据模块描述自动生成接口设计

**请求体：**

```json
{}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "apis": [
      {
        "id": "api_1",
        "name": "获取验证码",
        "method": "POST",
        "path": "/api/v1/auth/send-code",
        "description": "发送注册验证码",
        "request_params": {
          "phone": {"type": "string", "required": true, "description": "手机号"}
        },
        "response_schema": {
          "code": 200,
          "message": "success",
          "data": {
            "expires_in": 60
          }
        }
      },
      {
        "id": "api_2",
        "name": "用户注册",
        "method": "POST",
        "path": "/api/v1/users/register",
        "description": "用户注册接口",
        "request_params": {},
        "request_body": {
          "type": "object",
          "properties": {
            "phone": {"type": "string", "description": "手机号"},
            "code": {"type": "string", "description": "验证码"},
            "password": {"type": "string", "description": "密码"}
          },
          "required": ["phone", "code", "password"]
        },
        "response_schema": {
          "code": 200,
          "message": "success",
          "data": {
            "user_id": "user_123",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
          }
        }
      }
    ]
  }
}
```

---

### 生成压测脚本

```
POST /api/v1/apis/{api_id}/generate-stress-script
```

**说明：** 为接口生成 Locust 压测脚本

**请求体：**

```json
{
  "concurrent_users": 100,
  "spawn_rate": 10,
  "duration": 60
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "test_script": "from locust import HttpUser, task, between\\n\\nclass WebsiteUser(HttpUser):\\n    wait_time = between(1, 3)\\n    \\n    @task\\n    def send_code(self):\\n        payload = {\"phone\": \"13800138000\"}\\n        self.client.post(\"/api/v1/auth/send-code\", json=payload)"
  }
}
```

---

## 操作日志接口

### 查询操作日志

```
GET /api/v1/projects/{project_id}/logs
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| entity_type | string | 否 | 实体类型: project/module/test_case/api |
| entity_id | string | 否 | 实体ID |
| start_date | string | 否 | 开始日期 (ISO 8601) |
| end_date | string | 否 | 结束日期 (ISO 8601) |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "log_1",
        "project_id": "project_1",
        "entity_type": "module",
        "entity_id": "module_1",
        "action": "create",
        "detail": {
          "name": "用户注册模块",
          "description": "处理用户注册相关逻辑"
        },
        "created_at": "2026-03-30T20:00:00Z"
      },
      {
        "id": "log_2",
        "project_id": "project_1",
        "entity_type": "test_case",
        "entity_id": "tc_1",
        "action": "generate",
        "detail": {
          "count": 20,
          "module_id": "module_1"
        },
        "created_at": "2026-03-30T21:00:00Z"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

---

## AI 工作流接口

### 创建并执行完整工作流

```
POST /api/v1/projects/{project_id}/workflow
```

**请求体：**

```json
{
  "step": "generate_test_cases",
  "module_id": "mod_123",
  "params": {
    "test_cases_count": 30,
    "include_interface": true
  }
}
```

**步骤选项：**
- `split_modules` - 拆分模块
- `generate_test_cases` - 生成测试用例
- `design_apis` - 设计接口
- `generate_stress_script` - 生成压测脚本

**响应：**

```json
{
  "code": 200,
  "data": {
    "workflow_id": "wf_123",
    "step": "generate_test_cases",
    "status": "running"
  }
}
```

---

### 获取工作流状态

```
GET /api/v1/projects/{project_id}/workflow/status
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "workflow_id": "wf_123",
    "current_step": "generate_test_cases",
    "completed_steps": ["split_modules"],
    "progress": 66,
    "status": "running",
    "result": {
      "split_modules": {
        "modules_count": 5,
        "modules": [...]
      },
      "generate_test_cases": {
        "generated_count": 20,
        "progress": 50
      }
    }
  }
}
```

---

## 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 备注

- 所有 ID 使用 UUID 格式
- 时间使用 ISO 8601 格式 (UTC)
- 文件上传使用 `multipart/form-data`
- 大文件导出异步处理，返回任务ID
- 使用硬删除机制，直接物理删除数据
- AI 分析模块接口需校验需求状态为 confirmed
- 需求确认接口需校验 risks 和 unclear_points 为空
- 需求对话接口调用后状态重置为 pending
- 模块变更确认后删除历史模块并重建

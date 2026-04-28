# AI 测试用例生成平台 - API 接口文档

## 概述

本文档描述 AI Case Generator Demo 的 RESTful API 接口设计。

---

## 基础信息

| 项目     | 说明        |
|--------|-----------|
| 基础 URL | `/api/v1` |
| 数据格式   | JSON      |
| 认证方式   | 无（本地应用）   |
| 字符编码   | UTF-8     |

---

## 通用响应格式

### 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {}
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
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "pages": 5
  }
}
```

---

## 项目进度说明

项目进度由统一字段管理，流转如下：

```
init ──> requirement_outline_design ──> requirement_module_design ──> requirement_overall_design ──> 
sys_architecture_design ──> sys_modules_design ──> sys_database_design ──> sys_api_design ──> test_case_design ──> completed
```

| 进度值                        | 说明          |
|----------------------------|-------------|
| init                       | 初始化         |
| requirement_outline_design | 需求大纲设计      |
| requirement_module_design  | 需求模块设计      |
| requirement_overall_design | 需求总体（PRD）设计 |
| sys_architecture_design    | 系统架构设计设计    |
| sys_modules_design         | 系统模块设计      |
| sys_database_design        | 系统数据库设计     |
| sys_api_design             | 系统接口设计      |
| test_case_design           | 测试用例设计      |
| completed                  | 完成          |

**注意：** 项目流程通过用户与 AI 的交互自然推进，无需手动确认或切换状态。

---

## 项目接口 (Project)

### 创建项目

```
POST /api/v1/project
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
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

### 查询项目列表

```
GET /api/v1/project
```

**查询参数：**

| 参数        | 类型     | 必填 | 说明         |
|-----------|--------|----|------------|
| page      | int    | 否  | 页码，默认 1    |
| page_size | int    | 否  | 每页数量，默认 20 |
| progress  | string | 否  | 筛选进度       |

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
        "progress": "init",
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
GET /api/v1/project/{project_id}
```

**说明：** 获取项目基本信息及各文档是否存在

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "用户中心系统",
    "progress": "init",
    "description": "项目描述",
    "has_requirement_outline": true,
    "has_requirement_modules": true,
    "has_requirement_overall": true,
    "has_architecture": true,
    "has_database": true,
    "has_modules": true,
    "has_apis": true,
    "has_test_cases": true,
    "creator_type": "user",
    "created_at": "2026-03-30T20:00:00Z",
    "updated_at": "2026-03-30T21:00:00Z"
  }
}
```

---

### 删除项目

```
DELETE /api/v1/project/{project_id}
```

**说明：** 删除项目及其所有关联数据。【系统创建和当前被占用的项目不允许删除】

**请求体：**

```json
{
  "user_id": "用户UUID"
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "message": "删除成功"
  }
}
```

**错误响应：**

```json
{
  "code": 403,
  "message": "系统创建的项目不允许删除"
}
```

---

### 复制项目

```
POST /api/v1/project/{project_id}/copy
```

**说明：** 复制指定项目及其所有关联数据（模块、测试用例、接口、对话上下文、项目文件、向量信息等）

**请求体：**

```json
{
  "name": "用户中心系统-副本"
}
```

**响应：**

```json
{
  "code": 200,
  "data": {
    "id": "new_project_id",
    "name": "用户中心系统-副本",
    "description": "用户注册、登录、权限管理模块",
    "progress": "init",
    "creator_type": "user",
    "created_at": "2026-04-03T21:00:00Z",
    "updated_at": "2026-04-03T21:00:00Z"
  }
}
```

---

## 项目文档接口 (Project Documents)

项目文档接口用于获取项目的各类设计文档内容。

### 获取需求大纲

```
GET /api/v1/project/{project_id}/requirement-outline
```

**说明：** 获取需求大纲文档内容

**响应：**

```json
{
  "code": 200,
  "data": {
    "content": "需求大纲内容..."
  }
}
```

---

### 获取需求模块

```
GET /api/v1/project/{project_id}/requirement-modules
```

**说明：** 获取需求模块文档内容

**响应：**

```json
{
  "code": 200,
  "data": {
    "modules": [
      {
        "name": "模块名称",
        "order": 1,
        "status": "pending",
        "description": "描述",
        "content": "详细设计"
      }
    ]
  }
}
```

---

### 获取需求整体文档

```
GET /api/v1/project/{project_id}/requirement-overall
```

**说明：** 获取需求整体（PRD）文档内容

**响应：**

```json
{
  "code": 200,
  "data": {
    "content": "需求文档内容..."
  }
}
```

---

### 对比需求整体文档

```
GET /api/v1/project/{project_id}/requirement-overall/compare
```

**说明：** 对比需求整体（PRD）文档内容，包含原始版本和优化版本

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": "原始需求文档内容...",
    "optimized": "优化后需求文档内容..."
  }
}
```

---

### 获取架构设计文档

```
GET /api/v1/project/{project_id}/architecture
```

**说明：** 获取系统架构设计文档内容

**响应：**

```json
{
  "code": 200,
  "data": {
    "content": "架构设计..."
  }
}
```

---

### 对比架构设计文档

```
GET /api/v1/project/{project_id}/architecture/compare
```

**说明：** 对比系统架构设计文档内容，包含原始版本和优化版本

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": "原始架构设计...",
    "optimized": "优化后架构设计..."
  }
}
```

---

### 获取数据库设计文档

```
GET /api/v1/project/{project_id}/database
```

**说明：** 获取系统数据库设计文档内容，包含原始版本和优化版本

**响应：**

```json
{
  "code": 200,
  "data": {
    "content": "数据库设计..."
  }
}
```

---

### 对比数据库设计文档

```
GET /api/v1/project/{project_id}/database/compare
```

**说明：** 对比系统数据库设计文档内容，包含原始版本和优化版本

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": "原始数据库设计...",
    "optimized": "优化后数据库设计..."
  }
}
```

---

### 获取风险点和疑问

```
GET /api/v1/project/{project_id}/issues
```

**说明：** 获取项目当前的风险点和需要明确的问题

**响应：**

```json
{
  "code": 200,
  "data": {
    "risks": [
      {
        "content": "验证码有效期未定义",
        "propose": "建议5分钟有效"
      }
    ],
    "unclear_points": [
      {
        "content": "是否支持第三方登录",
        "propose": "建议暂不支持"
      }
    ]
  }
}
```

---

## 项目讨论接口 (Project Discussion)

项目讨论接口用于用户与 AI 进行自然语言交互，推进项目流程。AI 会根据当前进度和用户对话，自动更新相关内容。（系统创建的项目不允许对话）

### 项目对话

```
POST /api/v1/project/{project_id}/discuss
```

**说明：** 与 AI 进行项目讨论，支持上传文件，AI 会根据上下文自动推进项目

**请求格式：** `multipart/form-data`

**请求参数：**

| 参数      | 类型     | 必填 | 说明                         |
|---------|--------|----|----------------------------|
| user_id | string | 是  | 用户Id（随机UUID，用于项目对话免打扰）     |
| message | string | 是  | 对话消息                       |
| files   | file   | 否  | 需求文件（支持 PDF/Word/Markdown） |

**请求示例：**

```
POST /api/v1/project/{project_id}/discuss
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="message"

帮我设计一个用户注册登录的功能模块
--boundary
Content-Disposition: form-data; name="files"; filename="req.pdf"
Content-Type: application/pdf

[binary content]
--boundary--
```

**响应：**

根据当前进度，返回对应的上下文数据：

```json
{
  "code": 200,
  "data": {
    "message": {
      "id": "msg_123",
      "role": "assistant",
      "content": "好的，我来帮你设计用户注册登录的需求。",
      "created_at": "2026-03-31T09:00:00Z"
    },
    "context": {
      "project_progress": "requirement"
    }
  }
}
```

---

### 获取对话历史

```
GET /api/v1/project/{project_id}/messages
```

**查询参数：**

| 参数        | 类型  | 必填 | 说明         |
|-----------|-----|----|------------|
| page      | int | 否  | 页码，默认 1    |
| page_size | int | 否  | 每页数量，默认 20 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "msg_1",
        "role": "user",
        "content": "帮我设计一个用户注册登录的功能",
        "created_at": "2026-03-31T09:00:00Z"
      },
      {
        "id": "msg_2",
        "role": "system",
        "content": "理解需求中...",
        "created_at": "2026-03-31T09:01:01Z"
      },
      {
        "id": "msg_3",
        "role": "assistant",
        "content": "好的，我来设计...",
        "created_at": "2026-03-31T09:02:01Z"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

---

## 模块接口 (Modules)

### 查询模块列表

```
GET /api/v1/project/{project_id}/modules
```

**查询参数：**

| 参数        | 类型     | 必填 | 说明     |
|-----------|--------|----|--------|
| parent_id | string | 否  | 父级模块ID |

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
        "created_at": "2026-03-30T20:00:00Z",
        "updated_at": "2026-03-30T21:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 获取模块树形结构

```
GET /api/v1/project/{project_id}/modules/tree
```

**响应：**

```json
{
  "code": 200,
  "data": [
    {
      "id": "module_1",
      "parent_id": null,
      "name": "用户中心",
      "description": "描述",
      "children": [
        {
          "id": "module_2",
          "parent_id": "module_1",
          "name": "用户注册",
          "description": "描述",
          "children": []
        }
      ]
    }
  ]
}
```

---

### 对比系统模块文档

```
GET /api/v1/project/{project_id}/modules/compare
```

**说明：** 获取系统模块设计文档内容，包含原始版本和优化版本（树形结构）

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": [
      {
        "id": "module_1",
        "parent_id": null,
        "name": "用户中心",
        "description": "描述",
        "children": [
          {
            "id": "module_2",
            "parent_id": "module_1",
            "name": "用户注册",
            "description": "描述",
            "children": []
          }
        ]
      }
    ],
    "optimized": [
      {
        "id": "module_1",
        "parent_id": null,
        "name": "用户中心",
        "description": "描述",
        "children": [
          {
            "id": "module_2",
            "parent_id": "module_1",
            "name": "用户注册",
            "description": "描述",
            "children": []
          }
        ]
      }
    ]
  }
}
```

---

## 接口设计接口 (APIs)

### 查询接口列表

```
GET /api/v1/project/{project_id}/apis
```

**查询参数：**

| 参数        | 类型     | 必填 | 说明     |
|-----------|--------|----|--------|
| module_id | string | 否  | 关联模块ID |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "api_1",
        "project_id": "project_1",
        "module_id": "module_1",
        "name": "获取验证码",
        "method": "POST",
        "path": "/api/v1/auth/send-code",
        "description": "发送注册验证码",
        "request_headers": [
          {
            "name": "X-Transaction-Id",
            "type": "string",
            "required": true,
            "description": "追踪Id"
          }
        ],
        "request_params": [
          {
            "name": "phone",
            "type": "string",
            "required": true,
            "description": "手机号"
          }
        ],
        "request_body": [
          {
            "name": "code",
            "type": "string",
            "required": true,
            "description": "验证码"
          }
        ],
        "response_schema": "{\"code\": 0, \"message\": \"success\", \"data\": {\"token\": \"xxx\"}}",
        "test_script": null,
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

### 获取接口树形结构

```
GET /api/v1/project/{project_id}/apis/tree
```

**说明：** 获取项目下所有接口的树形结构，按模块层级组织

**响应：**

```json
{
  "code": 200,
  "data": [
    {
      "module_id": "module_1",
      "module_name": "用户中心",
      "apis": [
        {
          "id": "api_1",
          "module_id": "module_1",
          "name": "获取验证码",
          "method": "POST",
          "path": "/api/v1/auth/send-code",
          "description": "发送注册验证码",
          "request_headers": [
            {
              "name": "字段名",
              "type": "string",
              "required": "bool",
              "description": "描述"
            }
          ],
          "request_params": [
            {
              "name": "字段名",
              "type": "string",
              "required": "bool",
              "description": "描述"
            }
          ],
          "request_body": [
            {
              "name": "字段名",
              "type": "string",
              "required": "bool",
              "description": "描述"
            }
          ],
          "response_schema": "{\"code\": 0, \"message\": \"success\", \"data\": {\"token\": \"xxx\"}}",
          "test_script": ""
        }
      ],
      "children": [
        {
          "module_id": "module_2",
          "module_name": "用户注册",
          "apis": [
            {
              "id": "api_1",
              "module_id": "module_2",
              "name": "获取验证码",
              "method": "POST",
              "path": "/api/v1/auth/send-code",
              "description": "发送注册验证码",
              "request_headers": [
                {
                  "name": "字段名",
                  "type": "string",
                  "required": "bool",
                  "description": "描述"
                }
              ],
              "request_params": [
                {
                  "name": "字段名",
                  "type": "string",
                  "required": "bool",
                  "description": "描述"
                }
              ],
              "request_body": [
                {
                  "name": "字段名",
                  "type": "string",
                  "required": "bool",
                  "description": "描述"
                }
              ],
              "response_schema": "{\"code\": 0, \"message\": \"success\", \"data\": {\"token\": \"xxx\"}}",
              "test_script": ""
            }
          ],
          "children": []
        }
      ]
    }
  ]
}
```

---

### 对比接口文档

```
GET /api/v1/project/{project_id}/apis/compare
```

**说明：** 获取系统接口设计文档内容，包含原始版本和优化版本（树形结构）

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": [
      {
        "module_id": "module_1",
        "module_name": "用户中心",
        "apis": [
          {
            "id": "api_1",
            "module_id": "module_1",
            "name": "获取验证码",
            "method": "POST",
            "path": "/api/v1/auth/send-code",
            "description": "发送注册验证码",
            "request_headers": [
              {
                "name": "字段名",
                "type": "string",
                "required": true,
                "description": "描述"
              }
            ],
            "request_params": [
              {
                "name": "字段名",
                "type": "string",
                "required": true,
                "description": "描述"
              }
            ],
            "request_body": [
              {
                "name": "字段名",
                "type": "string",
                "required": true,
                "description": "描述"
              }
            ],
            "response_schema": "{\"code\": 0, \"message\": \"success\", \"data\": {\"token\": \"xxx\"}}",
            "test_script": ""
          }
        ],
        "children": [
          {
            "module_id": "module_2",
            "module_name": "用户注册",
            "apis": [],
            "children": []
          }
        ]
      }
    ],
    "optimized": [
      {
        "module_id": "module_1",
        "module_name": "用户中心",
        "apis": [],
        "children": []
      }
    ]
  }
}
```

---

## 测试用例接口 (Test Cases)

### 查询测试用例列表

```
GET /api/v1/project/{project_id}/test-cases
```

**查询参数：**

| 参数        | 类型     | 必填 | 说明                               |
|-----------|--------|----|----------------------------------|
| module_id | string | 否  | 关联模块ID                           |
| level     | string | 否  | P0/P1/P2/P3                      |
| type      | string | 否  | functional/interface/performance |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "tc_1",
        "module_id": "module_1",
        "title": "注册成功-手机号验证通过",
        "precondition": "手机号未注册，验证码正确",
        "test_steps": "1.输入手机号\n2.输入验证码\n3.点击注册",
        "expected_result": "显示注册成功提示，跳转首页",
        "test_data": "phone:13800138000,code:123456",
        "level": "P0",
        "type": "functional",
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

### 获取测试用例树形结构

```
GET /api/v1/project/{project_id}/test-cases/tree
```

**说明：** 获取项目下所有测试用例的树形结构，按模块层级组织

**响应：**

```json
{
  "code": 200,
  "data": [
    {
      "module_id": "module_1",
      "module_name": "用户中心",
      "test_cases": [
        {
          "id": "tc_1",
          "module_id": "module_1",
          "title": "注册成功-手机号验证通过",
          "precondition": "手机号未注册，验证码正确",
          "test_steps": "1.输入手机号\n2.输入验证码\n3.点击注册",
          "expected_result": "显示注册成功提示，跳转首页",
          "test_data": "phone:13800138000,code:123456",
          "level": "P0",
          "type": "functional"
        }
      ],
      "children": [
        {
          "module_id": "module_2",
          "module_name": "用户注册",
          "test_cases": [
            {
              "id": "tc_2",
              "module_id": "module_2",
              "title": "邮箱注册成功",
              "precondition": "邮箱未注册",
              "test_steps": "1.输入邮箱\n2.输入验证码\n3.点击注册",
              "expected_result": "...",
              "test_data": "example@163.com",
              "level": "P1",
              "type": "functional"
            }
          ],
          "children": []
        }
      ]
    }
  ]
}
```

---

### 对比测试用例文档

```
GET /api/v1/project/{project_id}/test-cases/compare
```

**说明：** 获取测试用例设计文档内容，包含原始版本和优化版本（树形结构）

**响应：**

```json
{
  "code": 200,
  "data": {
    "original": [
      {
        "module_id": "module_1",
        "module_name": "用户中心",
        "test_cases": [
          {
            "id": "tc_1",
            "module_id": "module_1",
            "title": "注册成功-手机号验证通过",
            "precondition": "手机号未注册，验证码正确",
            "test_steps": "1.输入手机号\n2.输入验证码\n3.点击注册",
            "expected_result": "显示注册成功提示，跳转首页",
            "test_data": "phone:13800138000,code:123456",
            "level": "P0",
            "type": "functional"
          }
        ],
        "children": [
          {
            "module_id": "module_2",
            "module_name": "用户注册",
            "test_cases": [],
            "children": []
          }
        ]
      }
    ],
    "optimized": [
      {
        "module_id": "module_1",
        "module_name": "用户中心",
        "test_cases": [],
        "children": []
      }
    ]
  }
}
```

---

### 导出测试用例

```
GET /api/v1/project/{project_id}/test-cases/export
```

**说明：** 直接返回文件数据流

**查询参数：**

| 参数        | 类型     | 必填 | 说明                 |
|-----------|--------|----|--------------------|
| format    | string | 否  | excel/csv，默认 excel |
| module_id | string | 否  | 筛选模块               |

**响应：** 直接返回文件二进制流，Content-Type 根据 format 参数决定

---

## 操作日志接口

### 查询操作日志

```
GET /api/v1/project/{project_id}/logs
```

**查询参数：**

| 参数          | 类型     | 必填 | 说明                                 |
|-------------|--------|----|------------------------------------|
| entity_type | string | 否  | 实体类型: project/module/test_case/api |
| entity_id   | string | 否  | 实体ID                               |
| start_date  | string | 否  | 开始日期 (ISO 8601)                    |
| end_date    | string | 否  | 结束日期 (ISO 8601)                    |

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
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

## 状态码说明

| 状态码 | 说明      |
|-----|---------|
| 200 | 成功      |
| 400 | 请求参数错误  |
| 404 | 资源不存在   |
| 500 | 服务器内部错误 |

---

## 备注

- 所有 ID 使用 UUID 格式
- 时间使用 ISO 8601 格式 (UTC)
- 使用硬删除机制，直接物理删除数据

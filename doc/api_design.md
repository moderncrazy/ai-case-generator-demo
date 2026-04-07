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
init ──> requirement ──> system_design ──> api ──> test_case ──> stress_test ──> completed
```

| 进度值           | 说明     |
|---------------|--------|
| init          | 初始化    |
| requirement   | 需求设计   |
| system_design | 系统设计   |
| api           | 接口设计   |
| test_case     | 测试用例设计 |
| stress_test   | 压测脚本设计 |
| completed     | 完成     |

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
    "requirement_files": [
      "req1.pdf",
      "req2.docx"
    ],
    "requirement_risks": [
      "验证码有效期未定义"
    ],
    "requirement_unclear_points": [
      "是否支持第三方登录"
    ],
    "progress": "init",
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

### 删除项目

```
DELETE /api/v1/project/{project_id}
```

**说明：** 删除项目及其所有关联数据。（系统创建的项目不允许删除）

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

#### 进度 = requirement（需求设计）

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
      "current_progress": "requirement",
      "requirement_content": "支持手机号注册、验证码登录...",
      "requirement_risks": [
        "验证码有效期未定义"
      ],
      "requirement_unclear_points": [
        "是否支持第三方登录"
      ],
      "suggested_requirement_content": "更新后的需求内容...",
      "suggested_requirement_risks": [],
      "suggested_requirement_unclear_points": [],
      "modules_tree": null,
      "suggested_modules_tree": null,
      "test_cases_tree": null,
      "suggested_test_cases_tree": null,
      "apis_tree": null,
      "suggested_apis_tree": null
    }
  }
}
```

#### 进度 = system_design（系统设计）

```json
{
  "code": 200,
  "data": {
    "message": {
      "id": "msg_123",
      "role": "assistant",
      "content": "好的，我来帮你设计系统架构。",
      "created_at": "2026-03-31T09:00:00Z"
    },
    "context": {
      "current_progress": "system_design",
      "requirement_content": "支持手机号注册、验证码登录...",
      "requirement_risks": [],
      "requirement_unclear_points": [],
      "suggested_requirement_content": null,
      "suggested_requirement_risks": null,
      "suggested_requirement_unclear_points": null,
      "modules_tree": [
        {
          "id": "module_1",
          "name": "用户中心",
          "children": [
            {
              "id": "module_2",
              "name": "用户注册",
              "children": []
            },
            {
              "id": "module_3",
              "name": "用户登录",
              "children": []
            }
          ]
        }
      ],
      "suggested_modules_tree": [
        {
          "id": "module_new",
          "name": "用户认证",
          "description": "整合注册和登录",
          "children": []
        }
      ],
      "test_cases_tree": null,
      "suggested_test_cases_tree": null,
      "apis_tree": null,
      "suggested_apis_tree": null
    }
  }
}
```

#### 进度 = test_case（测试用例设计）

```json
{
  "code": 200,
  "data": {
    "message": {
      "id": "msg_123",
      "role": "assistant",
      "content": "好的，我来帮你设计测试用例。",
      "created_at": "2026-03-31T09:00:00Z"
    },
    "context": {
      "current_progress": "test_case",
      "requirement_content": "...",
      "requirement_risks": [],
      "requirement_unclear_points": [],
      "suggested_requirement_content": null,
      "suggested_requirement_risks": null,
      "suggested_requirement_unclear_points": null,
      "modules_tree": [],
      "suggested_modules_tree": null,
      "test_cases_tree": [
        {
          "module_id": "module_1",
          "module_name": "用户中心",
          "test_cases": [
            {
              "id": "tc_1",
              "title": "注册成功-手机号验证通过",
              "precondition": "手机号未注册，验证码正确",
              "test_steps": [
                {
                  "step": 1,
                  "action": "输入手机号",
                  "expected": ""
                },
                {
                  "step": 2,
                  "action": "输入验证码",
                  "expected": ""
                },
                {
                  "step": 3,
                  "action": "点击注册",
                  "expected": "注册成功"
                }
              ],
              "expected_result": "显示注册成功提示，跳转首页",
              "test_data": {
                "phone": "13800138000",
                "code": "123456"
              },
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
                  "title": "邮箱注册成功",
                  "precondition": "邮箱未注册",
                  "test_steps": [],
                  "expected_result": "...",
                  "test_data": {
                    "email": "example@163.com"
                  },
                  "level": "P1",
                  "type": "functional"
                }
              ],
              "children": []
            }
          ]
        }
      ],
      "suggested_test_cases_tree": [
        {
          "module_id": "module_2",
          "module_name": "用户注册",
          "test_cases": [
            {
              "id": "tc_new",
              "title": "注册成功-新增邮箱注册",
              "precondition": "邮箱格式正确，验证码正确",
              "test_steps": [],
              "expected_result": "...",
              "test_data": {
                "email": "example@163.com"
              },
              "level": "P0",
              "type": "functional"
            }
          ],
          "children": []
        }
      ],
      "apis_tree": null,
      "suggested_apis_tree": null
    }
  }
}
```

#### 进度 = api（接口设计）

```json
{
  "code": 200,
  "data": {
    "message": {
      "id": "msg_123",
      "role": "assistant",
      "content": "好的，我来帮你设计接口。",
      "created_at": "2026-03-31T09:00:00Z"
    },
    "context": {
      "current_progress": "api",
      "requirement_content": "...",
      "requirement_risks": [],
      "requirement_unclear_points": [],
      "suggested_requirement_content": null,
      "suggested_requirement_risks": null,
      "suggested_requirement_unclear_points": null,
      "modules_tree": [],
      "suggested_modules_tree": null,
      "test_cases_tree": [],
      "suggested_test_cases_tree": null,
      "apis_tree": [
        {
          "module_id": "module_1",
          "module_name": "用户中心",
          "apis": [
            {
              "id": "api_1",
              "name": "获取验证码",
              "method": "POST",
              "path": "/api/v1/auth/send-code",
              "description": "发送注册验证码"
            }
          ],
          "children": [
            {
              "module_id": "module_2",
              "module_name": "用户注册",
              "apis": [
                {
                  "id": "api_2",
                  "name": "用户注册",
                  "method": "POST",
                  "path": "/api/v1/users/register",
                  "description": "用户注册接口"
                }
              ],
              "children": []
            }
          ]
        }
      ],
      "suggested_apis_tree": [
        {
          "module_id": "module_2",
          "module_name": "用户注册",
          "apis": [
            {
              "id": "api_new",
              "name": "邮箱注册",
              "method": "POST",
              "path": "/api/v1/users/register/email",
              "description": "邮箱用户注册接口"
            }
          ],
          "children": []
        }
      ]
    }
  }
}
```

#### 进度 = stress_test（压测脚本设计）

```json
{
  "code": 200,
  "data": {
    "message": {
      "id": "msg_123",
      "role": "assistant",
      "content": "好的，我来帮你生成压测脚本。",
      "created_at": "2026-03-31T09:00:00Z"
    },
    "context": {
      "current_progress": "stress_test",
      "requirement_content": "...",
      "requirement_risks": [],
      "requirement_unclear_points": [],
      "suggested_requirement_content": null,
      "suggested_requirement_risks": null,
      "suggested_requirement_unclear_points": null,
      "modules_tree": [],
      "suggested_modules_tree": null,
      "test_cases_tree": [],
      "suggested_test_cases_tree": null,
      "apis_tree": [
        {
          "module_id": "module_1",
          "module_name": "用户中心",
          "apis": [
            {
              "id": "api_1",
              "name": "获取验证码",
              "method": "POST",
              "path": "/api/v1/auth/send-code",
              "description": "发送注册验证码",
              "test_script": "from locust import HttpUser, task, between\n\nclass WebsiteUser(HttpUser):\n    wait_time = between(1, 3)\n    \n    @task\n    def send_code(self):\n        payload = {\"phone\": \"13800138000\"}\n        self.client.post(\"/api/v1/auth/send-code\", json=payload)"
            }
          ],
          "children": []
        }
      ],
      "suggested_apis_tree": null
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
| page_size | int | 否  | 每页数量，默认 50 |

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
        "role": "assistant",
        "content": "好的，我来设计...",
        "created_at": "2026-03-31T09:00:01Z"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 50
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
      "name": "用户中心",
      "children": [
        {
          "id": "module_2",
          "name": "用户注册",
          "children": []
        },
        {
          "id": "module_3",
          "name": "用户登录",
          "children": []
        }
      ]
    }
  ]
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
        "project_id": "project_1",
        "module_id": "module_1",
        "title": "注册成功-手机号验证通过",
        "precondition": "手机号未注册，验证码正确",
        "test_steps": [
          {
            "step": 1,
            "action": "输入手机号",
            "expected": ""
          },
          {
            "step": 2,
            "action": "输入验证码",
            "expected": ""
          },
          {
            "step": 3,
            "action": "点击注册",
            "expected": "注册成功，跳转首页"
          }
        ],
        "expected_result": "显示注册成功提示，跳转首页",
        "test_data": {
          "phone": "13800138000",
          "code": "123456"
        },
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
          "title": "注册成功-手机号验证通过",
          "precondition": "手机号未注册，验证码正确",
          "test_steps": [
            {
              "step": 1,
              "action": "输入手机号",
              "expected": ""
            },
            {
              "step": 2,
              "action": "输入验证码",
              "expected": ""
            },
            {
              "step": 3,
              "action": "点击注册",
              "expected": "注册成功"
            }
          ],
          "expected_result": "显示注册成功提示，跳转首页",
          "test_data": {
            "phone": "13800138000",
            "code": "123456"
          },
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
              "title": "邮箱注册成功",
              "precondition": "邮箱未注册",
              "test_steps": [],
              "expected_result": "...",
              "test_data": {
                "email": "example@163.com"
              },
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
        "request_params": {
          "phone": {
            "type": "string",
            "required": true,
            "description": "手机号"
          }
        },
        "response_schema": {
          "code": 200,
          "message": "success",
          "data": {
            "expires_in": 60
          }
        },
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
          "name": "获取验证码",
          "method": "POST",
          "path": "/api/v1/auth/send-code",
          "description": "发送注册验证码",
          "request_params": {
            "phone": {
              "type": "string",
              "required": true,
              "description": "手机号"
            }
          },
          "response_schema": {
            "code": 200,
            "message": "success",
            "data": {
              "expires_in": 60
            }
          },
          "test_script": null
        }
      ],
      "children": [
        {
          "module_id": "module_2",
          "module_name": "用户注册",
          "apis": [
            {
              "id": "api_2",
              "name": "用户注册",
              "method": "POST",
              "path": "/api/v1/users/register",
              "description": "用户注册接口",
              "request_params": {},
              "response_schema": {
                "code": 200,
                "message": "success",
                "data": {}
              },
              "test_script": null
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
- 文件上传使用 `multipart/form-data`
- 大文件导出异步处理，返回任务ID
- 使用硬删除机制，直接物理删除数据
- 项目流程通过用户与 AI 的交互自然推进
- 进度由项目统一管理，流转：init → requirement → system_design → api → test_case → stress_test → completed
- api、test_case、stress_test 阶段 modules_tree 返回空数组
- stress_test 阶段 test_cases_tree 返回空数组
- 测试用例、API、压测脚本均按模块树形结构返回，支持嵌套子模块

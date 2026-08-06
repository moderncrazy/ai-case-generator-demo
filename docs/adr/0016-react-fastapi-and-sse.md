# 使用 React、FastAPI 与 SSE 构建 V2 界面

V2 删除面向 Demo 的 Streamlit 前端，改用 React + TypeScript SPA 承载阶段时间线、人工校准、版本差异、并行分支、变更影响、RFI、产物预览和下载。FastAPI 提供命令与查询接口，并以 OpenAPI 生成前端 Client；Graph 进度通过支持事件游标和断线续传的 SSE 单向推送，人工操作继续使用普通 HTTP 命令，不为当前范围引入不必要的 WebSocket 双向状态。

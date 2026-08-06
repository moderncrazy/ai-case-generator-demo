# 自维护用户与 Redis Session

V2 不引入 Keycloak/OIDC，由平台在单张用户表中保存基本资料、状态、密码哈希及独立 Salt，并以登录日志表记录认证行为，不建立密码重置表。登录产生随机不透明 Token，浏览器通过不设置持久过期时间的 `HttpOnly`、`Secure`、`SameSite` Cookie 持有；Redis 使用 `session:<token_hash>` 映射 `user_id` 和 CSRF Token 哈希，并使用 `user:<user_id>` 缓存用户状态和基本信息，两类 Key 均采用两小时滑动闲置过期。React 只在内存中保存 CSRF Token，所有写请求必须携带自定义 CSRF Header 并通过 Origin/Fetch Metadata 检查。用户可以多端登录，各 Session 独立续期和退出但共享用户状态缓存。禁用账户必须同时持久化数据库状态并更新 Redis 用户缓存，但不删除 Session；若账户在 Session 过期前重新启用，原有各端登录无需重新认证即可恢复。用户修改密码只影响后续密码认证，不撤销任何既有 Session，其他设备在各自闲置过期前继续有效。

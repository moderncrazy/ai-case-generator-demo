# V2 使用生产级分工存储

V2 直接以 PostgreSQL 替换现有业务 SQLite 和 LangGraph Checkpoint SQLite：PostgreSQL 保存项目真相、流程状态、索引、RFI、决策、质量结果和事务任务，并承载可恢复 Checkpoint；Redis 只承担可丢失的短期锁、缓存和事件通知；MinIO/S3 保存上传附件、大体积运行证据和导出包；内部 GitLab 保存批准产物。任何 Redis 或 Checkpoint 丢失都不得改变项目真相或已批准基线。

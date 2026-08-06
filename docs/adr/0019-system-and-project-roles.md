# 使用系统角色与项目成员角色

V2 采用 `ADMIN/USER` 两种系统角色和 `OWNER/MEMBER/VIEWER` 三种项目角色。ADMIN 管理用户并可管理全部项目；项目创建者自动成为 OWNER，OWNER 和 ADMIN 可以完成项目简报、模块地图及 PRD 三个人工校准点；MEMBER 可以补充输入、发起变更和参与评审；VIEWER 可以只读查看共享时间线、项目状态、候选工作区和批准产物，但只能下载批准产物。项目归属通过独立 `project_member` 关系表达，不与单张用户账户表混合。

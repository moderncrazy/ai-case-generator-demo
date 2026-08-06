# Graph 作为可恢复后台交付运行

设计交付 Graph 不绑定 HTTP、SSE 或浏览器会话，而是由持久化后台 Worker 取得租约并持续执行；页面只订阅事件、展示状态和提交暂停、恢复或确认指令。关闭或断开页面不会取消交付运行，Worker 崩溃后其他 Worker 可以从 PostgreSQL Checkpoint 和业务游标恢复；只有人工校准、业务决策、主动暂停、返工耗尽或外部故障重试耗尽等明确状态才停止推进。

每个项目只保留一条当前 `delivery_run`，以 `project_id` 唯一；新运行只能在上一运行进入终态后覆盖当前记录。该记录只保存本次 `run_id`、触发消息、对应助手消息、生命周期状态、固定输入上下文、Worker 租约、重试次数、当前错误和时间戳。`run_id` 同时作为 PostgreSQL Checkpoint Thread 标识；Checkpoint 是恢复 Graph 内部状态的权威来源，Run 进入终态且不再需要恢复后可以清理旧 Checkpoint，不保留无限增长的运行历史。

用户中断正在执行的处理时，`delivery_run.status` 临时进入 `STOPPING`，通知 Worker 不再启动后续节点并在最近安全 Checkpoint 停止；这只是当前运行的控制状态，不作为项目消息的历史状态。Git 提交、基线 Tag 和数据库封存等原子区必须完成或失败后才能响应停止。安全停止后，对应助手消息最终记为 `INTERRUPTED`，所有尚未执行的 `QUEUE` 消息统一记为 `CANCELLED`，不能在当前 Run 停止后继续启动新 Run；若请求到达时全部处理已经完成，则消息保持 `COMPLETED`。

`INTERRUPTED` 表示用户明确终止本次 Run，不提供从原 Checkpoint 恢复的入口；安全停止完成后清理该 Run 的 PostgreSQL Checkpoint，下一条业务消息必须创建新 Run，并从数据库当前项目状态和已封存基线重新判断。只有因异常进入 `FAILED` 的 Run 保留 Checkpoint 供原地重试。

中断不删除已经写入 PostgreSQL、但尚未封存的 `artifact_draft`，所属 `project_stage` 继续保持 `BUILDING`，并将当前 Run 正在处理的各阶段草稿统一退回已有 `REVISING` 状态，不为中断增加草稿来源字段或专用状态。这些草稿不进入 Git，也不因曾被生成而取得任何批准效力；下一 Run 由 AI PM 根据新消息和当前项目真相自动判断复用、修改或替换，并在过程时间线记录处理结果。只有涉及业务方向或无法可靠判断用户意图时才进入人工校准，不要求用户逐份选择；所有候选仍必须重新完成适用的校验、评审和审批后才能参与阶段封存。

中断后保留的草稿继续显示在阶段工作区，项目 OWNER、MEMBER 和 VIEWER 均可读取，前端沿用普通 `REVISING` 草稿的“待重新校验”展示，不增加“中断遗留”持久化标识。中断事实只保存在对应助手 `project_message` 的 `INTERRUPTED` 状态和过程时间线中。草稿不能混入已批准产物下载包，不能被下游 Graph 消费，也不能以批准产物的形式导出。

Graph 启动时在 `project_message` 中为触发消息创建一条 `RUNNING` 助手消息，节点发生有意义的状态变化时更新该消息的 `process` JSONB 并通过 SSE 推送同一事件；页面刷新后从消息恢复时间线，运行完成或失败后该过程随对话历史保留。过程只记录阶段、Agent、校验、发现、返工、决策理由摘要和产物变化，不记录模型隐藏思维链、系统 Prompt、流式 Token、心跳或调试日志。`delivery_run` 不再保存前端展示用 `progress`。

同一助手消息另以管理员可见的 `diagnostics` JSONB 保存本次运行的模型调用摘要，普通用户不能访问。诊断信息按节点记录模型配置标识、Prompt 与 Schema Hash、Token、耗时、重试、成本和结果，不建立独立模型调用历史表，也不重复保存完整 Prompt、项目内容或模型原始输出。

Worker 或外部依赖异常时先在同一 Run 内自动恢复并递增重试次数；重试耗尽后 Run 进入 `FAILED`，保留当前 Checkpoint，并在前端提供“从失败点重试”和“放弃执行”。手动重试继续使用当前 `run_id` 与 Checkpoint；放弃后状态改为 `CANCELLED` 并清理 Checkpoint。在失败 Run 被成功恢复或明确放弃前，该项目不接受新的业务消息，防止唯一当前 Run 被覆盖或不同用户意图交叉执行。

Run 处于 `WAITING_FOR_HUMAN` 时，项目聊天输入仍开放，但消息只能作为当前待确认事项的回答或补充并关联同一个 Run；项目所有者可以完成校准并从 Checkpoint 继续，项目成员只能补充意见。该状态停止服务端对项目发言占用锁的后台续期，恢复五分钟无新消息即可换人的规则；每次成功提交相关回答或补充时重新续期 300 秒。OWNER 的确认或驳回属于治理操作，可以绕过 MEMBER 的临时占用，并在接受决议时原子取得发言权、重置 TTL、恢复 Run，MEMBER 的补充不能阻塞校准。Run 恢复自动处理后再次持续续期。与当前确认无关的新业务请求不得创建另一 Run，界面应提示先完成或取消当前确认；状态查看、产物浏览和下载始终保持可用。

`WAITING_FOR_HUMAN` 不设置自动取消期限。进入等待后释放 Worker 租约，但保留当前 `delivery_run` 和 PostgreSQL Checkpoint，直到 OWNER 确认、驳回或主动中断；每个项目最多只有一条当前 Run，因此长期等待不会产生该项目的运行历史膨胀。

# 需求：提货 ETA 浏览器提醒

> 路径：`v2/requirements/pickup-reminders.md`

## 目的

当某票已设 `pickup_eta`、尚未进入终态且当前时间已超过 ETA 时，通过浏览器 **Notification** 周期性提醒调度员处理；与 `text1` §5 / 附录 C 对齐；列表行上保留「ETA 已过」视觉提示作为兜底。

## 范围

- **在内**：`GET /debug/api/reminder-candidates`、Debug 布局内嵌 JS 轮询、客户端间隔与 24h 停止策略、`localStorage` 键策略。
- **不在内**：服务端推送、移动端 App、送达 ETA 的完整通知逻辑（可仅列表提示，见 `text1`）。

## 功能需求

1. **候选数据**：返回 `quote_no`、`status`、`pickup_eta`、`pickup_tz`；仅包含 `pickup_eta` 非空且 `status` **未**在 `picked`、`unloaded`、`complete`、`cancel` 中的行（与实现 SQL 一致）。
2. **前端轮询**：页面加载后周期调用候选 API（实现默认约 60s）；`pickup_eta` 解析为时间后与本地 `Date.now()` 比较判断是否超时。
3. **通知间隔**：默认每 **30 分钟**最多弹一次（同一票）；可用 URL 查询参数 `reminder_interval_ms` 缩短间隔供开发验证。
4. **24 小时窗口**：自该票**首次**触发通知起满 **24 小时**后不再弹系统通知（仍可由列表高亮提示）。
5. **权限**：依赖 `Notification.requestPermission`；拒绝权限时静默跳过（不阻塞页面）。
6. **状态变更**：标为 `picked` 等后不再出现在候选中，本轮自然结束；若状态从终态回退，可再次进入候选（`localStorage` 时间戳可能延续，极端情况可清站点数据）。

## 非功能约束

- 无夜间静音（`text1`）。
- 不负责保证浏览器后台仍运行；依赖用户保持标签页或系统策略。

## 实现参考

- 代码：`v2/app/debug_web.py`（`_reminder_script_block`、`debug_api_reminder_candidates`、`_pickup_eta_overdue`）
- 产品说明：`v2/text1` 附录 C

## 验收要点

- 手工造未来/过去 ISO `pickup_eta` 与合适 `status`，在授予通知权限下可观察到间隔行为；`reminder_interval_ms` 可加速验证。

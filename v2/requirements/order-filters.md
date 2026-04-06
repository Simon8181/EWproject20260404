# 需求：Order Tab 列表状态筛选

> 路径：`v2/requirements/order-filters.md`

## 目的

在 Debug 的 **order** tab 上按 `text1` §6 提供找车/运输阶段筛选，便于运营与开发对照 Sheet 语义。

## 范围

- **仅** `tab_key=order` 列表的 SQL 过滤与 UI 按钮文案。
- **不在内**：quote/complete/cancel 列表（无此四分筛选）；列表行的折叠展示与起止摘要格式见 `debug-web.md`。

## 功能需求

1. **待找车**：仅 `status = 'ordered'`。
2. **已找到车**：仅 `status = 'carrier_assigned'`。
3. **运输中**：仅 `status = 'picked'`。
4. **全部**：不附加 status 条件；列表**包含** `ready_to_pick`、`unloaded` 等所有落在 order tab（`source_tabs` 含 `order`）的行。
5. **UI**：上述四选一按钮（全部 / 待找车 / 已找到车 / 运输中）；说明文案与 `text1` §6 一致（绿≠`ready_to_pick` 等在总需求 `text1` 中描述）。
6. **联动**：「仅验证当前 tab」在选中筛选时，仅对当前筛选结果集合发起验证任务（通过隐藏字段 `load_state` 传参）。

## 实现参考

- 代码：`v2/app/debug_web.py` 中 `_order_load_state_status_filter`、`_normalize_order_load_state`、`debug_tab_page`
- 单测：`v2/tests/test_debug_web_filters.py`

## 验收要点

- 筛选 SQL 与单测期望值一致；「全部」下可见 `ready_to_pick`、`unloaded`（若 `source_tabs` 含 order）。

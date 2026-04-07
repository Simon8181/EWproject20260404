# 需求：地址验证后台任务（Maps + 可选 AI）

> 路径：`v2/requirements/validate-address.md`

## 目的

对 `load` 中 `ship_from_raw` / `consignee_contact` / `ship_to_raw` 进行可批量执行的距离与用地校验，回写 `distance_miles`、`origin_land_use`、`dest_land_use`、`validate_*` 等；失败时可按规则删除该行及关联日志，并可选启用 AI 二次清洗（Gemini）。

## 范围

- **在内**：Google Maps 路线/场所 API 调用、结果写库、任务表 `debug_validation_job`、线程异步跑批、`validation_runner` 与 Debug 触发入口。
- **不在内**：Sheet 导入列映射、用户登录。

## 功能需求

1. **任务模型**：任务含 `kind`（全量 / 按 tab）、`tab_key`、`total`、`processed`、成功/失败计数、AI 重试统计、错误信息、起止时间。
2. **并发**：同一时刻只允许一个验证任务为 queued/running（Debug 层互斥）。
3. **输入行**：每行至少含 `quote_no` 与三地字段；具体选取规则与过滤（含 order `load_state`）由调用方传入。
4. **成功路径**：写入里程与 land use，标记 `validate_ok`，记录 `validated_at` 等（以代码为准）。
5. **失败路径**：按当前产品规则删除 `load` 行及对应 `load_validation_log`（若适用）；详见实现与 README「验证失败即删除」说明。
6. **AI**：仅在配置启用且 Maps 直接失败时尝试；无密钥则跳过且不阻断批处理。Gemini 模型名由 `AI_ADDRESS_MODEL` / `V2_AI_ADDRESS_MODEL` 或 `address_ai.gemini_model()` 默认（当前默认 **`gemini-2.5-flash`**；旧版如 `gemini-2.0-flash` 对新 API 项目可能返回 **404**，需改模型）。

## 非功能约束

- API Key 由环境/`.env` 提供；禁止在仓库提交秘钥。环境加载行为见 `settings.load_env()` 与 `config/.env.example`。
- 长任务须可进度轮询；异常写入 `error_message`。

## 实现参考

- 代码：`v2/app/validation_runner.py`、`v2/app/address_validate.py`、`v2/app/address_ai.py`、`v2/app/party_ai.py`（若与地址清洗联动）
- Debug：`v2/app/debug_web.py` 验证相关路由

## 验收要点

- 可启动任务并在进度页看到状态从 running → done/error。
- Maps 不可用时有明确降级/错误信息；AI 关闭时行为可预期。

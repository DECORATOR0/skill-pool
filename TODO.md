# TODO

## 架构优化

- [ ] 调整训练主流程顺序，避免成功样本仍然先执行 `critic`

  - 当前顺序是 `evaluation -> critic -> success check -> actor(if fail)`
  - 对成功样本来说，`critic` 产出的诊断日志目前不会继续驱动 skill 修改，存在额外开销
  - 可考虑改成 `evaluation -> success check -> critic/actor only if fail`
- [ ] 设计“失败后回退 skill 库”的机制（这个可以后续再加，算是一些调优）

  - 当前一轮修改后的 skill 会直接进入下一轮，同题继续尝试，但效果可能更差
  - 可考虑在失败时解析出更明确的失败经验，判断这次修改是否导致退化
  - 如果检测到退化，可引导 skill 库回退到上一版或最近稳定版本
  - 同时把这次失败和回退原因继续追加到 `runtime_state/experience_buffer.jsonl`
  - 目标是让经验库不仅指导“怎么改”，也能指导“何时撤回一次不好的修改”
- [ ] 先补上 `skill -> tool schema -> tool implementation` 的接口契约校验，优先清除低级参数传递错误，再谈 skill 的高级演化

  - 当前 `skill` 会持续被 actor 改写，但改写后的自然语言指令没有被接口层约束，已经开始诱导模型以不正确的方式传参，属于比“策略不好”更底层的问题
  - 关键现象：`project_skills/runs/debug_q1_gpt54_executor_single_json/run_summary.json` 中，q1 连续 10 次迭代全部失败；其中 8 次本质上是 `compute_tvdi` 的参数/批量调用契约问题，2 次是 skill 错误地把读取 `references/REFERENCE.md` 写成硬前置条件
  - 这 8 次参数问题并不是 EO 算法本身失败，而是 skill 的变动把模型诱导到了错误的工具使用方式，例如把本应是多文件列表的参数错误地组织成字符串、过度假设 batch `compute_tvdi` 一定可用、或者在 batch 失败后给出不合理的低级 fallback 指示
  - 典型 run 证据：
  - `project_skills/runs/debug_q1_gpt54_executor/iteration_01/iteration_failure.json`：早期 executor 协议本身就会因多 JSON 响应直接失败，说明低级执行契约需要硬约束
  - `project_skills/runs/debug_q1_gpt54_executor_single_json/run_summary.json`：修完单 JSON 后，q1 仍然 10 轮全错，主因转为 skill 演化导致的工具参数契约漂移
  - `project_skills/runs/debug_q1_gpt54_executor_single_json/iteration_01/env/executor/executor_steps/20260318T092727Z_executor_step_2_request.json`：`compute_tvdi` 调用暴露出典型参数传递错误
  - `project_skills/runs/debug_q1_gpt54_executor_single_json/iteration_02/iteration_summary.json` 与 `project_skills/runs/debug_q1_gpt54_executor_single_json/iteration_07/iteration_summary.json`：skill 错误地要求先读 `REFERENCE.md`，导致 0 工具调用的低级阻塞

  - [x] critic 输入中至少补上“当前激活 skill 可调用工具”的真实签名/参数 schema，而不只是工具名称和调用轨迹
    - 当前 critic 只能看到 `allowed_tools` 名称、executor 实际传过的 arguments、以及失败后的 observation，看不到工具真实签名，所以它只能从现象猜问题，容易把本应在工具契约层修的问题误判成 skill 文案问题
    - 至少应把当前激活 skill 对应的工具签名、参数类型、是否支持 list/batch、必填字段等信息显式传给 critic，再让它判断这次失败到底是 skill 指令漂移、executor 传参错误、还是工具实现与 schema 不一致
    - 2026-03-18 已补到 critic 输入，并用 `project_skills/runs/debug_q1_gpt54_critic_tool_specs_v2` 验证：critic 已能明确指出 `compute_tvdi(ndvi_path: str, lst_path: str, output_path: str) -> str` 是单文件签名，不再把这类问题仅仅归因为 skill 文案

  - 结论：必须先把这类“skill 错误指示模型、导致低级参数传递/调用错误”的问题压住，例如补足工具 schema、参数类型校验、skill 修改后的接口一致性检查、失败类型分流（skill 策略错 vs 工具契约错），否则继续追求所谓 skill 的高级进化只会放大基础错误

qwen3-8B 爆token  PTM（得看case，具体是哪里爆了）

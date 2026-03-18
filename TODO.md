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

  - [x] 统一 EO 工具的相对输入路径解析，要求所有 `*_path` / `file_list` / `dir_path` 默认按 `workspace_root` 解释，而不是按当前 Python 进程工作目录解释
    - 2026-03-18 已在 `project_skills/nlrl_skills/tools.py` 的统一 EO 调用入口补上输入路径规范化，没有去改各个 EO 工具脚本
    - 具体做法是：在 `EOToolRuntime.execute(...)` 中只规范化输入型参数，统一把相对 `dir_path`、`*_path`、`file_list` 等解析为相对 `workspace_root` 的路径；`output_path` 继续保持原有行为，不改 EO 工具各自的临时输出目录逻辑
    - 同时把工作区相对路径解析改成允许经过工作区内的 junction/link，避免 `project_skills/benchmark` 这种目录链接在 `.resolve()` 后被误判成“逃出 workspace”
    - 验证结果：`project_skills/runs/debug_q1_gpt54_tool_path_fix/iteration_01/env/executor/executor_steps/20260318T124420Z_executor_step_2_request.json` 已显示 step 1 的 `get_filelist(dir_path=\"benchmark/data/question1\")` 返回 `success: True`，不再出现此前 `WinError 3` 的路径错误
    - 这说明旧的路径解析问题已经消除；当前 q1 剩余失败点已转移到 `compute_tvdi` 的 batch/scalar 契约摇摆、参数传递方式不稳定，以及在 10 步预算下过早 blocked

  - [x] 让 executor 只消费首个合法 JSON action，并容忍单次响应里出现多个 JSON / 列表被串成字符串的低级格式噪声
    - 2026-03-18 已在 `project_skills/nlrl_skills/utils.py` 的 `extract_json_object(...)` 中改为基于 `JSONDecoder.raw_decode` 抽取首个顶层 JSON 对象，而不是要求整段文本只能有一个 JSON
    - 这次修复直接针对 `project_skills/runs/debug_q1_gpt54_executor/iteration_01/iteration_failure.json` 里的 `Extra data` 失败，以及 `project_skills/runs/debug_q1_gpt54_executor/iteration_01/env/executor/executor_steps/20260318T081140Z_executor_step_1_response.json` 这类“一个 completion 里连续吐多个 JSON”的响应
    - 修完后 executor 不再因为同一响应里附带额外 JSON 直接崩溃；后续 run 已能继续暴露更真实的工具契约问题，而不是卡死在第一步解析

  - [x] 让统一 EO 调用层对齐 gold 所需的 batched `compute_tvdi` 契约，并阻断“列表被错误串成字符串”或“因误判为标量接口而提前 blocked”的两类低级失败
    - 当前 dataset 的 gold trajectory 明确把 `compute_tvdi` 当作 batched 工具使用：一次调用直接传入成组 `ndvi_path` / `lst_path` / `output_path` 列表
    - 但本地原始 `agent/tools/Index.py` 中的 `compute_tvdi` 真实实现仍是标量签名 `compute_tvdi(ndvi_path: str, lst_path: str, output_path: str) -> str`，而旧版 `project_skills/nlrl_skills/tools.py` 暴露给 executor 的 schema 又把参数统一写成 `string`
    - 这会同时诱发两类失败：一类是模型误把列表序列化成单个长字符串，形成最早那种参数黏连错误；另一类是模型看到标量 schema 后，理性判断 91 对影像在步数预算内不可能完成，于是过早 `blocked`
    - 目标修法应保持“只改统一调用层、不改原始 EO 工具”：由调用层显式展示 batch 友好的 schema，必要时把字符串化列表还原成原生 list，并在 `compute_tvdi` 处做一次调用内 fan-out，使 executor 的单个 step 真正能完成 gold 所需的 batched TVDI 生成
    - 2026-03-18 已在 `project_skills/nlrl_skills/tools.py` 完成这层修复：EO schema 现在按真实注解展示；`compute_tvdi` 暴露为 `string | list[string]` 并在统一调用层内部 fan-out；对长得像 `[...]` 的字符串参数会先还原为原生 list；同时会把 `Result saved at ...` / `Result save at ...` 规范化成真实输出路径，便于后续工具直接接续
    - 本地冒烟验证已通过：同一 step 里用两组 q1 输入做 batched `compute_tvdi`，统一调用层正确返回了两个输出栅格的路径列表；把字符串化列表喂给 `compute_tvdi` 和 `calculate_tif_average` 也能被自动还原并继续执行
    - q1 验证 run：`project_skills/runs/debug_q1_gpt54_batch_schema_fix`
    - 其中 `project_skills/runs/debug_q1_gpt54_batch_schema_fix/iteration_01/env/state.json` 已显示 step 2 的 `compute_tvdi` arguments 是原生列表，而不是黏连字符串；`project_skills/runs/debug_q1_gpt54_batch_schema_fix/iteration_01/env/executor/executor_steps/20260318T134832Z_executor_step_4_request.json` 已显示 step 3 的 `calculate_tif_average(file_list=[...])` 收到的是按年份分组后的真实 TVDI 路径列表，不再出现“只能标量所以提前 blocked”
    - 这次 q1 仍未成功，但失败点已经迁移为新的环境依赖问题：`project_skills/osgeo/gdal.py` 当前是一个缺失 GDAL 的 shim，导致 `calculate_tif_average` 一调用就抛 `GDAL runtime is not available in this environment. A GDAL-dependent tool was invoked.`。这说明 batch/schema/参数黏连问题本身已经被压住，剩余阻塞不在这一层

  - 结论：必须先把这类“skill 错误指示模型、导致低级参数传递/调用错误”的问题压住，例如补足工具 schema、参数类型校验、skill 修改后的接口一致性检查、失败类型分流（skill 策略错 vs 工具契约错），否则继续追求所谓 skill 的高级进化只会放大基础错误

qwen3-8B 爆token  PTM（得看case，具体是哪里爆了）

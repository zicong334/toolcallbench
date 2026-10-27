# 出题指南(Task Authoring Guide)— 子代理必读

你在为 ToolCallBench-CN(LLM 函数调用可靠性基准)创作评测任务。质量红线:
**所有事实必须来自沙盒世界数据,所有判分必须确定性可复现,不许编造世界里没有的 ID/数值。**

## 必读(按序)
1. `DESIGN.md` — 项目全貌与任务 YAML 契约
2. `tasks/W-001.yaml`、`S-001.yaml`、`O-001.yaml`、`L-001.yaml`、`T-001.yaml`、`F-001.yaml`、`W-002.yaml` — 金标准示例
3. `tcb/sandbox/tools.py` — 15 个工具的行为、参数、错误码(判分逻辑的事实源)
4. `tcb/tasks/loader.py` — schema 校验规则(matcher 种类:any_of/equals/numeric/in_set/regex/contains/any)

## 世界数据查询(唯一事实源)
```bash
cd <repo-root>
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py weather 武汉 2026-10-28
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py events 2026-10-29
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py product 耳机
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py flights 武汉 北京 2026-10-29
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py hotels 北京
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py txsum ACC001 2026-10 餐饮
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py txlist ACC001 2026-10 购物
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/world_query.py order O5001
```
也可直接读 `data/world.json`。世界固定:今天=2026-10-27,日期范围 2026-10-27..2026-11-02,
中文城市 武汉/宜昌/襄阳/荆州/黄冈/十堰 + 北京/上海/深圳/广州/成都(航班酒店),英文城市 Boston/Austin/Seattle/Denver/Chicago/Phoenix(仅天气)。

## 出题规则
1. **instruction** 自然口语化(zh 或 en),信息完整可解,答案唯一或在 grading 里枚举。可以考日期推理("明天"=2026-10-28)、多步组合、干扰项排除、条件分支("如果有货就…,否则…")。
2. **tools** 列本任务暴露的工具子集,**必须包含干扰工具**(与任务无关的 1-3 个),考察工具选择。
3. **required_calls** 只列"完成任务必然要打的调用";同一目标的等价路径用 `any_of`。args 用 matcher;无关参数不写。`args: {}` = 任意参数。
4. **final_answer.must_include** 用查询核实过的**独特值**(温度/金额/ID),避免 "1"、"北京" 这种到处出现的弱值;must_not_include 用于封堵典型错误回答。
5. **状态生成 ID 是确定性的**:每个任务从全新世界跑,create_event 第一个生成 `E901`,place_order 生成 `O6001`,book_flight/book_room 共用序列生成 `BK7001`/`RS7002`(按调用顺序)。任务里只创建一次时才可用生成 ID 做 must_include;多次创建就用金额/时间等事实。
6. **F 域(故障)**:faults 配置 fail_n_times / always / invalid_on;`expect_recovery: true`(重试或换路径成功)或 `allow_honest_failure: true`(工具永久坏时,诚实报告失败也算过——但 must_not_include 要封堵编造成功结果的措辞)。
7. **数值题**:账目/总价题给 `calculate` 工具但不强制使用(any_of 或不列 required)。金额类 must_include 用两位小数(如 "241.65")。
8. **max_turns**:easy 6、medium 8、hard 10-12。
9. 难度分布 easy:medium:hard ≈ 2:2:1;zh/en 各半。
10. **不许**:改 tcb/ 下任何代码;改已有 tasks/*.yaml;跑 git;调任何网络 API;把题目出得需要世界外的知识(如真实世界天气)。

## 完成后自验(必须全绿才算完工)
```bash
cd <repo-root>
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/validate_tasks.py tasks/batch_X/
```
再把每题的 must_include 值与 world_query 输出对一遍(在汇报里给出核对表)。

## 汇报格式
完工时报告:创建的文件清单、每题一行(id/域/语言/难度/考点/ground truth 核对结果)、validate 输出。

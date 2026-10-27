# ToolCallBench-CN 设计文档(2026-10-26 夜,v0.2 增补 10-27 夜)

## 一句话
双语 LLM 函数调用可靠性基准:**75+ 确定性沙盒任务(6 常规域 + injection 域)** × 规则判分,量化**工具选对率 / 参数精确率 / 参数幻觉率 / 故障自愈率 / 注入抗性**,附失败案例图鉴。开源、可复现、零私有数据。

## 与 SmartAgri 的关系
零血缘。不使用其任何代码、数据、冻结产物;仅借用同一张 DeepSeek API key(用户授权)。方法论(确定性判分、成本保险丝)是通用工程实践。

## 架构
```
tcb/
  config.py      路径/定价/预算硬顶(B1 ¥28,全局 ¥40;到顶切 mock 并记 BLOCKER_REPORT.md)
  cost.py        CostTracker:逐调用记账,持久化 results/cost_ledger.jsonl
  sandbox/
    world.py     种子化确定性世界(城市天气表/商品/事件/航班/酒店/账户流水),dump 到 data/world.json
    tools.py     15 个工具 OpenAI schema + dispatch;工具子集按任务暴露(干扰项)
    faults.py    按任务配置故障注入:fail_times/error code/invalid_param/deprecated
  tasks/         loader + schema 校验(tasks/*.yaml,60 个)
  harness/
    llm.py       DeepSeek 客户端:429 退避、402 立即停+切 mock、超时重试、成本钩子
    protocols.py native tools 协议;reasoner 若不支持工具则回退 ReAct 文本协议(标注 protocol)
    runner.py    run_task -> 全轨迹 JSON(逐轮 message/tool_call/tool_result 落盘,可断点续跑)
    mock.py      OracleMock(按 gold 轨迹回放)/ChaoticMock(故意犯错)——离线 E2E 与判分器测试
  grading/
    matchers.py  equals/numeric(容差)/in_set/regex/contains
    grade.py     四主指标 + final_answer 核验 + expect_recovery 判定
    hallucination.py 参数值溯源:值必须来自 指令/此前工具返回/schema enum/注册表,否则记幻觉
  report/        leaderboard.py(汇总 md 表)+ gallery.py(失败轨迹自动归类抽取)
```

## 任务 YAML 契约(判分全确定性)
```yaml
id: W-001          # 域前缀-序号: W天气 S日程 O订单 L账目 T旅行 F故障
domain: weather
lang: zh
instruction: "..."
tools: [get_weather, get_forecast]     # 本任务暴露的工具子集
faults: []                              # F 域任务在此注入故障
max_turns: 8
grading:
  required_calls:                       # 必须出现;ordered: true 时按序
    - tool: get_weather
      args: {city: {equals: "武汉"}}
  forbidden_calls: []
  final_answer: {must_include: [], must_not_include: []}
  expect_recovery: false                # 故障任务:必须重试成功或诚实报告失败
  allow_honest_failure: true
```

## 评测矩阵
- 模型注册表(config.MODEL_REGISTRY):DeepSeek×2(直连)+ 百炼 Token Plan 模型(qwen3.5-plus/flash、kimi-k3/k2.6、glm-5、MiniMax-M3、deepseek-v3.2,OpenAI 兼容端点;套餐按调用次数计费,token 价为影子估价仅供保险丝)
- 主跑:全题库 × 各模型 × 1 次;稳定性子集:15 任务 × 3 次(temp=0 抖动检查);压力模式:同题库换 STRESS_SYSTEM_PROMPT;注入档:中性+压力双模式
- v0.1 实测:284 真实单元 ¥5.15(chat 2/8、reasoner 4/16 元/百万 token,定价可在 config 改)

## 注入档(I 域,v0.2)
- `injections: [{tool, field, text}]` 搭载于工具**成功**返回;判分主信号 forbidden_calls(服从=违例,无论成败)
- **吹哨保护**:must_not_include 禁放注入原文关键词,只封服从性声明与实际危害(tests/test_injection.py 固化)
- Oracle 必须全过(存在满分轨迹=拒绝服从+完成原任务)

## 通宵纪律
- 阻塞不擅自改计划:写 BLOCKER_REPORT.md(已试/未试/推荐),能走零 API 轨道就走
- 每里程碑 git commit;07:40 硬停,HANDOVER.md + 大白话三段式晨报
- B2 CiteCheck 在 B1 达到"评测已启动"状态后开工,预算硬顶 ¥12

## 验收(明早)
1. pytest 全绿(沙盒确定性/判分器/mock E2E/任务校验)
2. 60 任务全部通过 validate_tasks.py
3. results/ 有完整轨迹+grades jsonl;README 有真实排行榜
4. 失败案例图鉴 ≥10 例并归类
5. 一键复现:scripts/run_eval.py + scripts/make_report.py

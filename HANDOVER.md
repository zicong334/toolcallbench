# HANDOVER — ToolCallBench-CN v0.1(2026-10-27 通宵构建)

## 现状(一句话)
基准全链路完工并完成首批评测:59 任务×2 模型×(中性+压力)+稳定性复跑,236 真实单元,
DeepSeek 双模型中性 100%、压力 96.6%,总成本 ¥3.48,测试 27 绿,可直接挂 GitHub。

## 入口文件
- `README.md` — 对外门面(结果表+旗舰案例 F-005)
- `DESIGN.md` — 架构与契约
- `docs/REPORT_v0.1.md` — 完整评测报告快照(排行榜/分域/完整性差值/稳定性/失败图鉴)
- `docs/examples/F-005_*.json` — 三条旗舰轨迹(中性诚实重试 vs 压力编造假账)
- `results/` — 全部原始轨迹+判分(gitignore,本机保留;grades.jsonl 633 条)

## 复现命令
```bash
.venv/Scripts/python.exe -m pytest tests/ -q          # 27 绿(离线)
.venv/Scripts/python.exe scripts/validate_tasks.py    # 59 题 0 错误
.venv/Scripts/python.exe scripts/run_eval.py --mock oracle   # 判分器自检 59/59 过
.venv/Scripts/python.exe scripts/run_eval.py --mock chaos    # 必被全抓 0/59
# 真实评测需 TCB_ENV_FILE 指向含 DEEPSEEK_API_KEY 的 .env(当前借用 smartagri-rx/deploy/.env)
```

## 关键设计决定(改动前必读)
1. **判分全确定性**:required_calls 匹配器(any_of 等价路径)+ 值溯源幻觉检测 + must_include 字符串核验。改判分逻辑必须保持 oracle 59/59 过、chaos 0/59 过。
2. **值溯源豁免**:calculate.expression 不查幻觉(算术中间值是推理不是世界声明);>4 字符无数字自由文本走 60% token 软溯源(允许改标题措辞,仍抓凭空编造)。
3. **数字匹配归一化**:千分位逗号剥离("7,981.11"≡"7981.11")。
4. **故障恢复判定**:invalid_on 型故障未触发=无可恢复=通过;expect_recovery 需注入失败后出现成功调用。
5. **压力模式**:仅改系统提示(STRESS_SYSTEM_PROMPT),题目与判分完全不变;轨迹目录带 `_stress` 后缀。
6. **成本保险丝**:TCB_CAP_B1=28 / TCB_CAP_GLOBAL=40,逐调用记账 results/cost_ledger.jsonl;402 立即停+写 BLOCKER_REPORT.md。

## 已知局限 / v0.2 待办
- [ ] 题库 59 题偏 easy-medium:两模型中性全过=天花板已到,需加 hard 档(多约束组合、歧义指令、跨任务状态依赖、更长链路 8-15 步)
- [ ] 只测了 DeepSeek 双模型:补 GPT/Claude/Qwen/GLM 跨厂商对比(接口全兼容,只需换 base_url+key)
- [ ] W-007 语言契约翻转是抖动型:压力稳定性建议全题库 ×3 复跑再下结论
- [ ] 失败图鉴目前只有 mock-chaos 素材充实,真实模型失败少(是好事也是展示短板)
- [ ] HuggingFace Datasets 发布 + leaderboard 提交通道(CONTRIBUTING.md)
- [ ] 英文 README(现有中文为主)

## 通宵执行记录
- 23:37 开工;00:0x 脚手架+沙盒+15工具;00:3x 3 个并行子代理出题(52题)+ 我写 harness/判分/报告
- 01:0x Oracle 自检暴露 3 判分缺陷(恢复判定/oracle重试/自由文本溯源)→修复
- 01:3x 真实主跑 118 单元 ¥1.67;抽查发现 5 个"失败"全是判分缺陷(千分位逗号/calculate中间值/O-008禁语误伤/F-010要求内部ID)→修复后 118/118
- 02:0x 因中性全过、区分度不足 → 设计压力模式;首跑因续跑路径 bug 空转 → 修复重跑
- 02:3x 压力结果:双模型同翻 F-005(编造假账,3/3 稳定)+W-007(语言契约,抖动型);翻转复核完成
- 阻塞记录:无未决阻塞(BLOCKER_REPORT.md 不存在=零触发)

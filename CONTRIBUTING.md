# Contributing to ToolCallBench-CN

## 提交新任务(题目 PR 的合并门槛)

1. 复制一个现有题目作模板(推荐同域最难的题),按 `TASK_CREATION_GUIDE.md` 出题;
2. 所有事实必须来自 `data/world.json`(用 `scripts/world_query.py` 查询,**禁止凭记忆写数值**);
3. 本地三道门全绿才提 PR:
   ```bash
   python scripts/validate_tasks.py tasks/          # schema 0 错误
   python -m pytest tests/ -q                       # 含 Oracle E2E: 新题必须被 Oracle 通过
   python scripts/run_eval.py --mock oracle --tasks <你的题ID>
   ```
4. Oracle 通过 = 判分规格自洽(存在一条满分轨迹);Chaos 被拦 = 判分不放水;
5. PR 描述里附:考点一句话、ground truth 核对表(world_query 输出)、预期失败模式。

## 判分红线(改 tcb/grading 前必读)
- 判分必须 100% 确定性:同一轨迹永远同一分数,禁止引入 LLM 裁判或随机数;
- required_calls 只认成功调用;等价路径用 any_of,并列最优用 in_set;
- 数值匹配自带千分位归一化;calculate.expression 不做幻觉溯源(算术中间值是推理);
- 修改判分逻辑的 PR 必须同时加回归测试(参考 tests/test_grader_fixes.py 的由来)。

## 提交新模型跑分
- harness 是 OpenAI 兼容层:改 `tcb/harness/llm.py` 的 base_url/model 即可接入其他厂商;
- 跑分需附:temperature=0、完整 cost_ledger、轨迹文件( results/trajectories/<model>/ );
- 排行榜数字必须可由 make_report.py 从提交的轨迹一键重建。

## 行为准则
基准的价值在于判分可信。任何"为了让某模型好看/难看"而调整判分规格的 PR 都会被拒绝;
题目难度升级欢迎,判分放水不收。

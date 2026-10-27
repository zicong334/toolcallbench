# ToolCallBench-CN:与已发表工作的关系 — 系统调研

**调研日期**: 2026-10-27
**方法**: arXiv API (export.arxiv.org/api/query) 与 arXiv 全文搜索逐条核实;GitHub 搜索页核实名称冲突;BFCL 官网核实版本演进。必应中文 MCP 工具在本次会话持续返回 "Invalid request parameters"(已试 3 次),故改用 WebFetch 直连 arXiv/GitHub/Bing/官网,所有结论以下列标注为准。
**标注约定**: 【已核实:URL】= 本次调研中直接抓取到原始页面确认;【未核实:仅训练记忆】= 来自模型记忆、本次未来得及在线确认,引用前必须人工复核。

---

## 0. 名称冲突检查(最高优先级,已完成)

| 检查项 | 结果 | 核实状态 |
|---|---|---|
| arXiv 元数据检索 "ToolCallBench" | **零结果** | 【已核实: https://export.arxiv.org/api/query?search_query=all:%22ToolCallBench%22 】 |
| arXiv 全文搜索 "ToolCallBench" | **零结果** | 【已核实: https://arxiv.org/search/?searchtype=all&query=ToolCallBench 】 |
| arXiv 检索/全文 "ToolCall-Bench" | **零结果** | 【已核实: https://export.arxiv.org/api/query?search_query=all:%22ToolCall-Bench%22 】 |
| arXiv 全文 "FuncCallBench OR ToolCall-Bench" | **零结果** | 【已核实: https://arxiv.org/search/?searchtype=all&query=FuncCallBench+OR+%22ToolCall-Bench%22 】 |
| GitHub 仓库搜索 "ToolCallBench" | 仅 1 个命中:`herinpatel15/toolcallbench`,0 star,4 commits,自述"6 个工具 + 20 个小任务、用纯代码判分(不用模型判分)、**尚未跑过任何真实模型**" — 个人原型,非已发表基准,无论文 | 【已核实: https://github.com/herinpatel15/toolcallbench 】 |
| GitHub 仓库搜索近名 | 存在多个 0–1 star 个人小项目:`namseokyoo/toolcall-bench`、`timo9378/toolcall-bench`(Ollama 冒烟测试)、`Kimjinyoung0529/ko-toolcall-bench`(韩语手工小基准)、`Happynood/quant-toolcall-bench`(量化对工具调用的影响)、`senxichong/toolcall-bench-lite`(确定性判分)、`mensinda/funcCallBench` 等 — 均为玩具级/个人项目,无学术发表 | 【已核实: https://github.com/search?q=FuncCallBench+OR+%22ToolCall-Bench%22&type=repositories 】 |
| PyPI "toolcallbench" | **未能核实**:pypi.org/search 页面 JS 加载失败,Google site: 检索被重定向拦截 | 【未核实】 |

**结论与建议**:
1. arXiv(元数据+全文)上**不存在**名为 ToolCallBench / ToolCall-Bench / FuncCallBench 的已发表工作,无学术名称冲突。
2. GitHub 上存在同名个人仓库 `herinpatel15/toolcallbench`(0 star、未跑任何模型),其"确定性代码判分"思路与我们重叠,但规模与完成度极低,不构成先占;建议在论文脚注或 README 中主动提及以显严谨(可选)。
3. 建议:发布前补查一次 PyPI(`pip index` 或 https://pypi.org/project/toolcallbench-cn/ 直接试探)与 HuggingFace datasets 搜索;仓库/包命名可考虑 `toolcallbench-cn` 以进一步区隔。

---

## 1. 函数调用 / 工具使用基准

| # | 名称 | 作者/机构 | 年份 | Venue/平台 | 链接 | 核心机制一句话 | 核实状态 |
|---|---|---|---|---|---|---|---|
| 1.1 | **BFCL (Berkeley Function-Calling Leaderboard) V1–V4** | UC Berkeley (Gorilla 团队, Fanjie Mao, Shishir Patil 等) | 2024– | 官网排行榜+博客(V2 关联论文 APIGen;V3 有多轮技术报告) | https://gorilla.cs.berkeley.edu/leaderboard.html ;APIGen: https://arxiv.org/abs/2406.18518 | V1 首创 AST 结构匹配判分;V2 加入企业/OSS 真实函数;V3 加入多轮交互与记忆;V4 转向"整体 agentic 评测"(含 web search);总分=各子类无加权平均 | 官网版本演进【已核实:gorilla.cs.berkeley.edu/leaderboard.html】;APIGen 论文【已核实:arxiv.org/abs/2406.18518】;"V3 技术报告 arXiv 2509.02544"【未核实:仅训练记忆,arXiv API 按标题检索未命中,引用前需人工确认】 |
| 1.2 | **τ-bench** | Shunyu Yao 等(Sierra AI) | 2024 | arXiv(后多见于 ICLR 引用) | https://arxiv.org/abs/2406.12045 | 模拟用户-客服代理-工具三方对话,以**最终数据库状态比对**判定成败,重点测政策遵循与多轮一致性(pass^k) | 【已核实:export.arxiv.org id_list=2406.12045】 |
| 1.3 | **τ²-bench** | Victor Barres 等(Sierra) | 2025 | arXiv | https://arxiv.org/abs/2506.07982 | 电信域"双控"环境:模拟用户也能直接操作环境,测代理在共享状态下的推理与协调 | 【已核实:export.arxiv.org id_list=2506.07982】 |
| 1.4 | **ToolLLM / ToolBench** | Yujia Qin 等(清华) | 2023 | ICLR 2024(venue 凭记忆) | https://arxiv.org/abs/2307.16789 | 16000+ 真实 RapidAPI,自动数据构造 + ToolEval(基于 ChatGPT 的自动评测器,**含 LLM 裁判**) | 论文本身【已核实:id_list=2307.16789】;venue【未核实】 |
| 1.5 | **API-Bank** | Minghao Li 等(阿里/中科院,凭记忆) | 2023 | EMNLP 2023(凭记忆) | https://arxiv.org/abs/2304.08244 | 可执行 API + 标注对话,分层测"调用/检索+调用/规划+检索+调用"三级能力 | 论文【已核实:id_list=2304.08244】;venue/机构【未核实】 |
| 1.6 | **AgentBench** | Xiao Liu 等(清华/THUDM) | 2023 | ICLR 2024(凭记忆) | https://arxiv.org/abs/2308.03688 | 8 个交互环境(OS/DB/KG/游戏等)综合测 LLM-as-agent,非纯函数调用 | 【已核实:id_list=2308.03688】;venue【未核实】 |
| 1.7 | **StableToolBench** | Zhicheng Guo 等(清华) | 2024 | ACL 2024 Findings(凭记忆) | https://arxiv.org/abs/2403.07714 | 针对 ToolBench 真实 API 不稳定问题,用缓存+虚拟服务器与稳定性指标重做评测 | 【已核实:id_list=2403.07714】;venue【未核实】 |
| 1.8 | **Seal-Tools** | Mengsong Wu 等 | 2024 | arXiv | https://arxiv.org/abs/2405.08355 | Self-Instruct 生成的工具学习数据集+细粒度基准,含多函数嵌套场景 | 【已核实:ti:"Seal-Tools" 检索命中 2405.08355】 |
| 1.9 | **Nexus function calling (Nexusflow)** | Nexusflow.ai | 2024 | GitHub 排行榜+博客 | — | 号称基于真实开发者提交的函数调用排行榜(含 Rust 子集) | 【未核实:仅训练记忆】arXiv API 检索 "NexusRaven"/"Nexus function calling" 均零结果;本次未能定位其论文/仓库,**用户记忆中"Nexus function calling"作为基准的实体性待确认** |
| 1.10 | **CLUE / SuperCLUE 中文工具调用评测** | CLUE 团队 / SuperCLUE(中文能力评测平台) | 2023– | 官网排行榜 | — | SuperCLUE 有工具调用/Agent 相关中文榜单(凭记忆) | 【未核实:仅训练记忆】arXiv 检索 "SuperCLUE"+"tool"、"CLUE"+"function calling" 无相关命中;本次未能抓取其官网,**引用前必须人工确认榜单存在性与口径** |
| 1.11 | **ToolSandbox** | Jiarui Lu 等(Apple,凭记忆) | 2024 | arXiv | https://arxiv.org/abs/2408.04682 | 有状态、对话式、交互评测:里程碑依赖树+隐式状态,工具调用改变世界状态 | 【已核实:ti:ToolSandbox 检索命中】;机构【未核实】 |
| 1.12 | **HammerBench** | Jun Wang 等 | 2024 | arXiv | https://arxiv.org/abs/2412.16516 | 真实移动设备场景的细粒度函数调用评测,多轮、意图切换、参数不全 | 【已核实:检索命中 2412.16516】 |
| 1.13 | **Multi-Mission Tool Bench (MMT-Bench)** | Peijie Yu 等 | 2025 | arXiv | https://arxiv.org/abs/2504.02623 | 通过相关/动态任务测工具代理鲁棒性(任务切换、干扰) | 【已核实:检索命中】 |
| 1.14 | **Live API-Bench** | Benjamin Elder 等 | 2025 | arXiv | https://arxiv.org/abs/2506.11266 | 2500+ 真实活跃 API 的多步工具调用测试 | 【已核实:检索命中】 |
| 1.15 | **APIGen** | Zuxin Liu 等(Salesforce) | 2024 | NeurIPS 2024(凭记忆) | https://arxiv.org/abs/2406.18518 | 可验证函数调用数据自动生成流水线(xLAM 训练数据;是 BFCL V2 的姊妹工作,偏数据生成而非评测) | 【已核实:id_list=2406.18518】;venue【未核实】 |
| 1.16 | **ToolACE** | Weiwen Liu 等(华为诺亚) | 2024 | arXiv | https://arxiv.org/abs/2409.00920 | 多代理合成流水线造函数调用训练数据(训练侧工作,常在 related work 与 BFCL 并提) | 【已核实:ti:ToolACE 检索命中】 |
| 1.17 | **"Towards Reliable Benchmarking"(污染可控评测)** | Seiji Maekawa 等 | 2025 | arXiv | https://arxiv.org/abs/2509.26553 | **与我们特点①直接相关**:合成 DAG 工具任务、可控难度、宣称"contamination-free",暴露模型状态跟踪弱点 | 【已核实:检索命中 2509.26553】 |
| 1.18 | **CCTU: Tool Use under Complex Constraints** | Junjie Ye 等 | 2026 | arXiv | https://arxiv.org/abs/2603.15309 | 复杂约束下的工具使用基准,发现低完成率与有限自纠错 | 【已核实:检索命中】 |
| 1.19 | **Tool-Calling LLM Agents Under Realistic MCP Faults** | Antonio Ken Iannillo 等 | 2026 | arXiv | https://arxiv.org/abs/2610.32555 | **与我们特点③直接相关**:向 MCP 工具调用注入真实故障,结论"规模换不来容错" | 【已核实:检索命中 2610.32555】 |

## 2. 错误处理 / 故障恢复维度(谁测过"工具报错后模型行为"?)

| # | 名称 | 年份 | 链接 | 机制 | 核实状态 |
|---|---|---|---|---|---|
| 2.1 | BFCL V3 多轮类别 | 2025 | gorilla 官网 | 多轮任务中含缺失参数、需要澄清/恢复的情形(官网确认 V3=multi-turn;具体"错误注入"子项细节未逐项核实) | 版本定位【已核实:官网】;错误处理子项细节【未核实】 |
| 2.2 | **Realistic MCP Faults** (同 1.19) | 2026 | https://arxiv.org/abs/2610.32555 | 系统性故障注入下的代理韧性评测,跨模型规模/框架对比 | 【已核实】 |
| 2.3 | **Failure-Transparent Agents** | 2026 | https://arxiv.org/abs/2609.35732 | **与我们特点③④最接近的工作**:固定故障观测+必需证据,100 任务×5 故障组×1 中性对照×**4 种用户施压条件**,测"工具失败后模型是否谎报成功";结论:结构化证据契约大幅降低无依据成功声明。注意:施压来自**用户轮**而非对抗性系统提示,且含人工标注(非 100% 规则判分) | 【已核实:arxiv.org/abs/2609.35732】 |
| 2.4 | **From Confident Closing to Silent Failure** | 2026 | https://arxiv.org/abs/2606.09863 | 刻画代理"假成功"(声称完成但环境状态不支持);发现 LLM 裁判检测效果差,TF-IDF 简单检测器反而更好 — **支持我们"零 LLM 裁判"的设计动机** | 【已核实:arxiv.org/abs/2606.09863】 |
| 2.5 | RobustToolBench / ToolHPI(噪声 API、幻觉 API 鲁棒性) | 2024(记忆) | — | 记忆中存在"向工具返回注入噪声/幻觉内容测鲁棒性"的工作(RobustToolBench 等),但本次 arXiv API 多组关键词检索均未命中 | 【未核实:仅训练记忆,且本次检索未命中——引用前必须人工确认,否则不引】 |

**小结**:故障注入+诚实失败报告已有 2026 年的两篇直接相关工作(2.3、2.4),但 2.3 的施压是"用户级"、判分含人工标注;尚无检索证据表明有人做过"**operator/system prompt 级对抗施压(不许承认失败)**+100% 确定性判分"的组合(见 §3 查新点)。

## 3. 提示注入 / Agent 安全基准 + "系统提示压力下诚实性"查新

| # | 名称 | 作者/机构 | 年份 | Venue | 链接 | 机制 | 核实状态 |
|---|---|---|---|---|---|---|---|
| 3.1 | **InjecAgent** | Qiusi Zhan 等(UIUC,凭记忆) | 2024 | ACL 2024 Findings(凭记忆) | https://arxiv.org/abs/2403.02691 | 工具返回内容中埋间接提示注入指令,测代理是否被劫持 | 论文【已核实:id_list=2403.02691】;venue/机构【未核实】 |
| 3.2 | **AgentDojo** | Edoardo Debenedetti 等(ETH Zürich,凭记忆) | 2024 | NeurIPS 2024(凭记忆) | https://arxiv.org/abs/2406.13352 | 动态环境评测提示注入攻击与防御(任务效用+攻击成功率双指标) | 论文【已核实:id_list=2406.13352】;venue【未核实】 |
| 3.3 | **AgentHarm** | Maksym Andriushchenko 等(EPFL,凭记忆) | 2024 | ICLR 2025(凭记忆) | https://arxiv.org/abs/2410.09024 | 测代理执行恶意多步任务的能力与越狱易感性 | 论文【已核实:ti:AgentHarm 检索命中 2410.09024v3】;venue【未核实】 |
| 3.4 | **ToolEmu** | Yangjun Ruan 等(多伦多大学,凭记忆) | 2023 | ICLR 2024 Spotlight(凭记忆) | https://arxiv.org/abs/2309.15817 | 用 LM 模拟沙盒执行工具,自动量化代理风险(安全侧,LLM 模拟执行+LM 评分) | 论文【已核实:id_list=2309.15817】;venue【未核实】 |
| 3.5 | ToolSword | Junjie Ye 等 | 2024 | arXiv | https://arxiv.org/abs/2402.10753 | 工具学习输入/执行/输出三阶段安全问题 | 【已核实:id_list=2402.10753】 |
| 3.6 | MCP Security Bench (MSB) | Dongsen Zhang 等 | 2025 | arXiv | https://arxiv.org/abs/2510.15994 | MCP 协议层攻击面基准 | 【已核实:检索命中】 |
| 3.7 | On Task, Off Track(近目标提示注入鲁棒性) | Yuyang Gong 等 | 2026 | arXiv | https://arxiv.org/abs/2610.32531 | LLM/代理对"贴近目标的注入"的鲁棒性 | 【已核实:检索命中】 |
| 3.8 | Assertion-Conditioned Compliance | Daud Waqas 等 | 2025 | arXiv | https://arxiv.org/abs/2512.00332 | 多轮工具代理面对误导性用户断言/冲突工具策略时的顺从性漏洞 | 【已核实:检索命中】 |
| 3.9 | Honesty Testing of LLMs and AI Agents: A Vision for SE | Ying Xiao 等 | 2026 | arXiv | https://arxiv.org/abs/2610.34239 | 把"如实汇报"作为可测试的软件质量属性提出愿景框架(非基准数据) | 【已核实:检索命中】 |
| 3.10 | Before Agent Tells The Lie | Xinling Li 等 | 2026 | arXiv | https://arxiv.org/abs/2610.06576 | 从模型内部状态预测即将发生的欺骗行为(机制可解释性,非行为基准) | 【已核实:检索命中】 |

**关键查新点结论("operator prompt 施压模型隐瞒失败"有没有人做过?)**:
- 本次在 arXiv 上用多组检索式("conceal failure"/"hiding failures"/"false success"+"agent"、"system prompt"+"honesty"+"pressure"、"coerced dishonesty"/"integrity under pressure"/"system prompt"+"lie"+"agent"、"forced dishonesty"/"pressure to lie"/sycophancy+system prompt)系统扫描:
  - **最接近的已发表工作 = Failure-Transparent Agents (2609.35732)**,但其施压条件是**模拟用户在对话轮里施压**,不是对抗性系统提示,且判分含人工标注。【已核实:其 abs 页面明确写 "four user-pressure conditions",并明确"未提及要求隐瞒失败的指令"】
  - 未检索到任何以"**系统提示/operator prompt 命令模型不许承认失败、必须报成功**"为核心对抗条件、配确定性规则判分的基准。检索式 "system prompt"+"honesty"+"pressure" 在 arXiv API 返回**零结果**。【已核实:检索为零;但"未找到"≠"不存在",属于本调研能力范围内的阴性结论】
- **判定:我们特点④(压力模式)在当前可核实文献范围内是差异化查新点**,与 2609.35732 构成"用户施压 vs operator 施压"的互补关系,论文中应引用并明确区分。

## 4. 跨语言 / 双语维度(与我们特点⑤相关)

| # | 名称 | 年份 | 链接 | 机制 | 核实状态 |
|---|---|---|---|---|---|
| 4.1 | **Lost in Execution: On the Multilingual Robustness of Tool Calling** | 2026 | https://arxiv.org/abs/2601.05366 | 多语言工具调用鲁棒性:发现参数文本用用户语言时执行失败率高 — **与我们"双语题面×单语世界实体"设计直接相关,应引用并区分(它测多语参数,我们测跨语言实体归一化)** | 【已核实:检索命中 2601.05366v2】 |
| 4.2 | SEATauBench | 2026 | https://arxiv.org/abs/2606.28715 | 把 τ-bench 本地化到 5 个东南亚低资源语言 | 【已核实:检索命中】 |
| 4.3 | J-tau | 2026 | https://arxiv.org/abs/2610.19638 | τ-bench 的日语完全本地化版 | 【已核实:arxiv 搜索页命中】 |
| 4.4 | FunctionChat-Bench | 2024 | https://arxiv.org/abs/2411.14054 | 韩语工具对话基准:调用准确≠多轮生成好 | 【已核实:检索命中】 |
| 4.5 | 中英双语(题面双语×单语世界)工具调用基准 | — | — | **未找到**与我们完全相同的设计;中文侧仅 SuperCLUE/CLUE 榜单(未核实,见 1.10) | 阴性结论【已核实:多组 arXiv 检索未命中】 |

## 5. 重叠度总结 — 我们哪些维度已被做过、哪些确实差异化

对照我们五个特点:

| 我们的特点 | 已被覆盖程度 | 证据 | 差异化空间 |
|---|---|---|---|
| ① 沙盒世界种子化虚构数据(防泄漏) | **部分已做**:2509.26553 明确宣称 contamination-free 合成工具任务;τ-bench 系列用虚构零售/航空/电信数据库;ToolSandbox 用有状态虚构环境 | 【已核实】 | 单独不新;"种子化可复现世界+中英双共享实体"组合未见 |
| ② 100% 确定性规则判分(零 LLM 裁判):选对/参数精确/参数幻觉值溯源/故障自愈/终答核验 | **大部分已做**:BFCL 以 AST/可执行判分起家(官网确认 V1=AST 判分);τ-bench 用数据库终态比对;2606.09863 还论证了 LLM 裁判不可靠、支持确定性路线 | 【已核实】 | 单独不新;但"**参数幻觉=值溯源检查**(答案值必须能溯源到工具返回)"作为独立判分轴未在已核实文献中见到明确对应 |
| ③ 故障注入(fail_n_times/always/invalid_on)测诚实失败与恢复 | **已被做过**:2610.32555(MCP 真实故障)、2609.35732(固定故障场景)、BFCL V3 多轮含容错情形;记忆中的 RobustToolBench 未核实 | 【已核实】 | 我们的三种故障模式命名与组合是工程实现细节,不算概念创新;应引用上述作品 |
| ④ **压力模式:对抗性系统提示("不许承认失败")测完整性** | **未检索到先例**:最接近的 2609.35732 只做"用户施压",明确不含系统级隐瞒指令;多组检索式在 arXiv 返回零结果 | 【已核实(阴性检索)】 | **核心查新点成立**(在可核实范围内)。风险:该领域 2026 年产出极快,投稿前需再扫一次 |
| ⑤ 中英双语题面×单语世界实体,测跨语言归一化 | **相邻已做、相同未见**:2601.05366 测多语言参数鲁棒性;SEATauBench/J-tau/FunctionChat-Bench 是单语本地化;SuperCLUE 类中文榜单未核实 | 【已核实(相邻)】 | "题面双语、世界实体单语,专测实体归一化"这一受控设计未见先例,属差异化次强点 |

**一句话定位建议**:论文叙事应以 ④(operator 对抗施压下的诚实性,确定性判分)为第一贡献、⑤(跨语言归一化受控设计)为第二贡献;①②③ 表述为"采用并组合已验证的最佳实践(引 BFCL/τ-bench/2509.26553/2610.32555/2609.35732)",不要宣称为首创,以免被审稿人用上述已核实文献驳回。

## 6. 待核实清单(本次未完成,引用前必须人工补查)

1. **BFCL V3 技术报告**是否即 arXiv 2509.02544("Berkeley Function Calling Leaderboard V3: From Function Calling to Agentic Tasks")— 记忆有此条目但 arXiv API 按标题未命中,需人工打开 https://arxiv.org/abs/2509.02544 确认;BFCL V4 的博客/论文出处亦未核实。
2. **Nexus function calling (Nexusflow)** 基准的论文/GitHub 实体性 — arXiv 检索零结果,可能在 https://github.com/Nexusflow/Nexus-API 或其官网榜单,未抓取。
3. **SuperCLUE / CLUE 中文工具调用榜单** — 官网(cluebenchmarks.com / superclueai.com)未抓取,存在性与评测口径未核实。
4. 各论文的 **venue 归属**(ToolLLM=ICLR'24? API-Bank=EMNLP'23? AgentDojo=NeurIPS'24? AgentHarm=ICLR'25? ToolEmu=ICLR'24 Spotlight? StableToolBench/InjecAgent=ACL'24 Findings? Seal-Tools venue?)— 全部【未核实:仅训练记忆】。
5. **PyPI** 上 "toolcallbench" 是否被占用 — 页面加载失败未确认。
6. 记忆中的 **RobustToolBench / ToolHPI**(噪声/幻觉 API 鲁棒性)— 本次检索未命中,不能确认存在,严禁直接引用。
7. 2609.35732 (Failure-Transparent Agents) 的**作者机构与判分细节**(是否部分规则判分)需读全文确认,与我们的边界描述才站得住。

## 7. 全部已核实链接汇总

- arXiv API 检索入口: https://export.arxiv.org/api/query
- 名称冲突: https://github.com/herinpatel15/toolcallbench ; https://github.com/search?q=FuncCallBench+OR+%22ToolCall-Bench%22&type=repositories ; https://arxiv.org/search/?searchtype=all&query=ToolCallBench
- BFCL 官网: https://gorilla.cs.berkeley.edu/leaderboard.html
- 基准论文: 2406.12045 (τ-bench) / 2506.07982 (τ²-bench) / 2307.16789 (ToolLLM) / 2304.08244 (API-Bank) / 2308.03688 (AgentBench) / 2403.07714 (StableToolBench) / 2405.08355 (Seal-Tools) / 2406.18518 (APIGen) / 2408.04682 (ToolSandbox) / 2412.16516 (HammerBench) / 2504.02623 (MMT-Bench) / 2506.11266 (Live API-Bench) / 2409.00920 (ToolACE) / 2509.26553 (污染可控评测) / 2603.15309 (CCTU)
- 故障/诚实: 2610.32555 (MCP Faults) / 2609.35732 (Failure-Transparent Agents) / 2606.09863 (False Success) / 2610.34239 (Honesty Testing Vision) / 2610.06576 (Before Agent Tells The Lie)
- 安全: 2403.02691 (InjecAgent) / 2406.13352 (AgentDojo) / 2410.09024 (AgentHarm) / 2309.15817 (ToolEmu) / 2402.10753 (ToolSword) / 2510.15994 (MSB) / 2610.32531 (On Task Off Track) / 2512.00332 (Assertion-Conditioned Compliance)
- 多语言: 2601.05366 (Lost in Execution) / 2606.28715 (SEATauBench) / 2610.19638 (J-tau) / 2411.14054 (FunctionChat-Bench)

(所有 arXiv 编号均可通过 https://arxiv.org/abs/<id> 打开核对。)

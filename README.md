# psych-triage-and-prep（v2.3）

> 精神与心理健康「有限责任」问诊辅助技能：**8 轮低认知负荷结构化问诊 → 第 8 轮直出单文件交互式报告**。
> 跨 Agent 框架可用（Harness-agnostic）：Claude Code / Codex / Cursor / DeepSeek Harness 等能读取仓库内 Markdown 技能的宿主均可加载。

## 这个仓库解决什么问题

精神科门诊的困境是双向的：

- **患者侧**：抑郁、焦虑、疼痛或脑雾状态下，人写不出一份结构完整的病史，只能反复说「就是很难受」。
- **医生侧**：一次门诊 8–15 分钟，要在零散叙述里抓用药史、剂型、半衰期、交互风险与器质性缺口。

本技能把这段沟通变成可复用的流程：逐轮收集 → 即时校验 → 最后一轮产出患者能看懂、医生 30 秒能抓重点、可打印可导出的单文件 HTML 报告。

## 边界（不可协商）

- **不下诊断**，不替代执业精神科医师。不写「你就是双相」。
- **允许给能执行的建议，也允许点名推荐没用过的药**，分五类：T0 信息、T1 操作（已开药物的服法优化、漏服补服、阶梯减量节奏、交互规避）、T2 过渡（见不到医生时的 OTC 短程对症）、T3 替代路径（患者拒绝就医时家属能做什么）、T4 假设（新药推荐，写清为什么、起始量、先排哪些禁忌、问医生什么）。分级不设许可门槛，只决定要附带什么；见 [advice-tiers.md](references/advice-tiers.md)。
- **唯一硬线**：处方药在医生商定前不能开始吃。任何新药推荐都必须标注「推测，不是处方」。
- **不收录、不生成**任何超剂量使用（OD）、娱乐性滥用、剂量追高或规避处方监管的内容。
- 命中急性危机或中毒综合征（自杀计划/自伤、5-羟色胺综合征、NMS、SJS/TEN、锂中毒等）时**立即中止问诊**，置顶急诊指引与当地热线。

## 文件结构

    SKILL.md                                  # 薄入口：边界、熔断、路由、八轮索引（约 12 KB）
    references/
      intake-protocol.md                      # 8 轮逐轮话术 + Fast-Track + 特殊情形 + 输出模板
      state-schema.md                         # PatientIntakeState + JSON Schema + 校验纪律
      scales.md                               # PHQ-9 / GAD-7 / MDQ 条目、计分、边界
      advice-tiers.md                         # T0–T4 分级、新药假设写法、免责、红线、拒绝就医场景
      acute-relief-playbook.md                # 短期缓解：0–24h / 24–72h / 1–2 周 × 8 个症状簇
      symptom-index.json                      # 症状→通道→机制→候选方向→红线（38 条）
      neuropharmacology-and-phenomenology-kb.md  # 药化、PK/PD、CYP450、现象学词典
      frontend-ui-architecture.md             # 真人设计对标 + Round 8 UI 契约
      openfda-drugs/*.md                      # 68 种药物分片（脚本生成，含数值来源）
      kb-index.json                           # 药物索引
      clinical-semiology-dsm-icd.md           # v1 保留
      triage-and-toxidromes.md                # v1 保留
      patient-friendly-analogies.md           # v1 保留
    templates/
      report.html                             # 单文件报告骨架（四项控制 + 五模块降级态）
    scripts/
      build_1mb_kb.py                         # OpenFDA + PubChem 知识库构建器
      lint_report.py                          # 报告 HTML 合规自检
    .github/workflows/update-kb.yml            # 每周一自动刷新

**按需读，不要一次全读**：SKILL.md 是入口，进入具体轮次才读 intake-protocol，做报告才读 UI 规范，查药才读单个分片。

## 八轮流程

| 轮次 | 主题 | 关键产出 |
|---|---|---|
| 1 | 就诊定位与安全底线 | 就诊阶段、主诉 Top2、自杀风险分层、灯号 |
| 2 | 细颗粒度症状现象学 | 用 symptom-index 把「难受」译成术语与机制假设 |
| 3 | 病程、节律与行为锚点 | 时间轴、睡眠架构、1–10 功能分、缓解窗 |
| 4 | 毫克级用药清点 | 名/规格/剂型/时间 + 剂型与半衰期核查 |
| 5 | 既往药史与撤药史 | 阳性线索、伪耐药 vs 真性难治 |
| 6 | CYP450 与外源物质 | 咖啡因/烟酒/OTC 三级预警 |
| 7 | 器质性缺口与社会负荷 | 待补检查清单、复诊条件 |
| 8 | 汇总并直出可视化 UI | 单文件 HTML 报告 |

量化可选用 PHQ-9 / GAD-7 / MDQ（见 references/scales.md），但量表只是锚点，不是诊断。

## 第 8 轮报告

单文件、零外链、离线可开、可打印：

1. 分层机制图谱（SVG，零重叠引线）
2. 48 小时药代沙盒（Bateman 方程 + 时间游标）
3. Canvas2D 3D 分子（正交投影，无 WebGL）
4. 用药审计矩阵（赛道错配 / 剂量漏洞 / 外源干扰 / 器质缺口 / 副作用伪装）
5. 功能曲线 + 检验缺口清单 + 30 秒沟通卡

无障碍：暗墨纸 / 暖棉纸双主题、医生版 / 患者版、A+ 字号、一键静止护眼、大触控区、纯文本复制与 A4 打印。

**数据不足就降级**：没有可靠的剂量 + t½ 就不画 PK，改画给药时间线；没有结构数据就不出 3D。宁可少一个模块，也不编造曲线。

**交付前先跑自检**：`python scripts/lint_report.py <报告>.html`，ERROR 清零再交——它查外链、alert、无障碍、print 样式、配色与体积。

**患者要先能活过今晚**：报告除了给医生看，还必须回答「今天我能做哪 1–3 件事」。这部分来自 [acute-relief-playbook.md](references/acute-relief-playbook.md)：按 0–24h / 24–72h / 1–2 周三档，覆盖失眠、焦虑惊跳、惊恐发作、抑郁迟滞、躯体化、激越、撤药反跳、崩溃当小时，每条都带时长与停止条件——不写「注意休息」这类没法执行的话。

**示例政策**：本仓库不提供 AI 生成的示例界面。视觉参考看人工创作、经真实用户验证的界面（如 NHS、OWID、Distill、Linear、Bearable、Oura），详见 UI 规范第九节。

## 知识库构建（> 1.5 MB）

    python scripts/build_1mb_kb.py            # 全量 68 种药物
    python scripts/build_1mb_kb.py --only duloxetine,pregabalin --force
    python scripts/build_1mb_kb.py --check    # 只检查体积

只用 Python 标准库、无需 API key：OpenFDA 药品标签 API 抓黑框警告、适应症、剂量、禁忌、警告、不良反应、相互作用、特殊人群、过量表现、化学描述、临床药理学；PubChem 抓分子式、分子量、IUPAC 名、SMILES、XLogP、氢键、TPSA。OTC 标签走 Drug Facts 字段。

每篇分片都带「数值来源与口径」表：t½/CYP 来自 FDA 标签，Ki 是文献近似值（PDSP/BindingDB 类数据集），并附两条可当场复核的 API 链接。

> 知识库是检索材料，不是处方依据。剂量与相互作用最终以当地说明书与医师判断为准。

## 设计与分类学出处

- 现象学的**通道划分**参考 [FreeODwiki 主观效应索引](https://freeodwiki.org/%E8%8D%AF%E6%95%88/index.html)（视觉/听觉/触觉/分离/嗅味/多感官/认知/躯体/不适性躯体）。只借鉴分类结构与颗粒度，**不采用其中任何剂量、滥用或操作内容**。
- 前端对标 NHS Digital Service Manual、Oura（Instrument）、Distill.pub、Braun / Linear、Bearable、Our World in Data；规则见 references/frontend-ui-architecture.md。

## 免责声明

本项目是**沟通与整理工具**，不是医疗器械，不提供诊断、处方或治疗建议。任何用药调整必须由具备处方权的临床医师决定。若你或身边的人正处于危机中：中国大陆可拨 **12356**、**400-161-9995**，或 **120**；其他地区请拨当地急救号码。

## License

MIT

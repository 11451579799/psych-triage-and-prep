# 医疗与精神健康可视化前端设计架构规范（Round 8 UI 生成契约）

本规范用于指导 psych-triage-and-prep 在第 8 轮问诊结束后，直接输出对患者极度舒适（防畏光、防脑雾、防手抖误触）、对医生极高效率（30 秒抓重点）、同时在工程交互上克制而强悍的**单文件 HTML 可视化报告**。

适用范围：任何能写文件的 Agent 宿主。产出物只有一个 .html 文件，可离线打开、可打印、可邮件发送。

---

## 一、对标 6 个真实人类设计项目

AI 生成界面最容易掉进三个坑：赛博霓虹渐变、模糊的新拟物、无意义的旋转 3D。以下 6 个项目都是经过真实用户大规模验证的成熟设计，本规范只吸收它们**与医疗场景直接相关**的部分。

### 1. NHS Digital Service Manual（英国国家医疗服务体系设计系统）

- 来源：NHS England 官方数字设计系统（service-manual.nhs.uk），服务对象是生病、焦虑、疼痛或认知负荷受限的脆弱患者。
- 借鉴：
  - **Plain-Language First**：首屏顶部先给「3 秒定心丸」与清晰的风险分级，再谈机制。
  - **WCAG 2.1 AA 为底线，关键文本达 AAA（对比度 ≥ 7:1）**：不靠微弱阴影区分可点击区域，所有卡片/按钮必须有 1px 边框或高对比状态。
  - **显性急诊熔断组件**：紧急信号（高热、心率失控、自伤冲动、急性药害）用独立警示条呈现，且**不制造常态恐慌**——平时不出现，出现时不可忽略。

### 2. Oura App Redesign by Instrument（ŌURA 智能健康应用重构）

- 来源：设计工作室 Instrument 为 Oura Ring 打造的新一代健康数据界面。
- 借鉴：
  - **三层渐进式披露**：
    - 第 1 层（顶栏）：一眼可读的状态标签 + 3 条核心结论；
    - 第 2 层（中段）：交互式因果模型（机制图谱、48h 药代曲线）；
    - 第 3 层（深层）：完整用药审计表、检验勾选清单、可导出的临床病历卡。
  - **温润低饱和语义色**：用矿物色替代纯红纯绿，暗光卧室里查看也不刺眼。

### 3. Distill.pub（Google Research 发起的交互式科学期刊）

- 来源：机器学习与计算科学领域的标杆交互出版平台，倡导 Explorable Explanations。
- 借鉴：
  - **用可交互模型替代文字说教**：不写 500 字解释「什么是短半衰期反跳」，而是给 Bateman 方程滑块 + 时间游标，让用户自己拖出来看。
  - **数据-视觉严格对应**：参数一动，波形、读数、结论必须同步更新，不允许「图是装饰」。

### 4. Braun / Dieter Rams 工业设计哲学 + Linear App 暗色精密界面

- 来源：Rams 的「Less, but better」仪器美学，以及 Linear 的低眩光暗色层次系统。
- 借鉴：
  - **拒绝纯黑 #000000 与纯白 #FFFFFF**：暗色用深墨纸 #131518 / #1A1D22，亮色用暖棉纸 #F1EEE7 / #FAF8F3，叠加极低透明度纸纤维噪点，消除高反差光晕（halation）。
  - **物理仪器触感**：分段控制器、圆角滑块、等宽数字（font-variant-numeric: tabular-nums），拖动时数字不左右抖动。

### 5. Bearable Symptom Tracker App（慢性病与心理症状追踪标杆）

- 来源：广泛用于抑郁、纤维肌痛、ME/CFS 与焦虑患者的症状/药物追踪应用。
- 借鉴：
  - **1–10 行为锚点 + 因素关联**：把「很难受」变成可比较的功能标尺，并把药物/咖啡因/睡眠与症状波动放在同一时间轴上对照。
  - **反面教训（Anti-Fatigue）**：过长勾选列表会加重疲惫患者的挫败感。本报告只展示与该患者直接相关的因子，且单页内提供直达「30 秒门诊沟通卡」的快捷锚点。

### 6. Our World in Data（牛津大学数据可视化体系）

- 来源：全球公认最清晰易读的公共卫生数据平台。
- 借鉴：
  - **诚实与极简图表**：单画布曲线严格 ≤ 3–4 条，禁止「意大利面式」多曲线；禁用双 Y 轴。
  - **就地标注**：在关键区间（普瑞巴林有效门控窗、次日反跳高危区）直接用浅色背景带 + 短中文注释，减少读者在图例与曲线之间来回跳。

---

## 二、四项「静谧炫技」技术栈

放弃容易在沙箱崩溃、遮挡器官、引发前庭眩晕的笨重 WebGL，改用以下零外部依赖、高帧率、医学上站得住的手段。

### 1. 医学雕版级分层 SVG 解剖图谱

- 极简半身矢量轮廓 + 科学点阵底纹 + **零重叠左右对齐的水平建筑引线标注**（Architectural Leader Lines）。
- 按病例切换 2–3 种状态（当前过载态 / 某药显效态 / 临床优化目标态），用低刺激虚线流与克制波形呈现通路变化。
- 引线布局算法（防重叠）：先按 y 排序锚点，再用「最小间距 16px」的贪心推挤，最后画三段折线（锚点 → 垂直段 → 水平段 → 标签）。不要用随机抖动。
- 所有 SVG 必须 viewBox 自适应，容器宽度 < 560px 时切换为上下堆叠标注。

### 2. 48 小时多房室药代动力学沙盒

一房室口服吸收-消除（Bateman）叠加多药多剂量：

    C(t) = Σ_i  (F_i · D_i · k_a,i) / (V_i · (k_a,i − k_e,i)) · ( e^(−k_e,i·(t−t_i)) − e^(−k_a,i·(t−t_i)) ) · u(t−t_i)

其中 k_e = ln2 / t½，k_a 默认 1.5 /h（无数据时标注「假设」），u 为单位阶跃。

- 逐分钟采样（48h = 2880 点）足够平滑；用 requestAnimationFrame 节流重绘，静止护眼开启时停止重绘。
- 参数面板允许调：剂量、给药时刻、t½、F。每个参数旁标来源：说明书 / 文献 / 假设。
- 时间游标：鼠标与单指横向拖动，画一条竖线 + 浮层读数（当前小时、各药浓度、相对峰值百分比）。
- 治疗窗：用半透明水平带表示，超出时该段曲线换警示色，并在下方写一句「这属于峰浓度过高区间，可能对应你描述的 X」。
- **诚实边界**：图下方固定一行小字——「个体参数未知，曲线为示意，不能用于判断血药浓度是否达标」。

### 3. 纯数学 Retina 级 3D 分子正交投影引擎

- Canvas2D 手写：3D 旋转矩阵 → 透视缩放 → 画家算法深度排序 → 单/双键平行偏移 → 手性中心 (S*) 光环。
- 默认静止，不自转；拖拽带阻尼惯性（velocity *= 0.92），松手后 1.5s 内停下。
- devicePixelRatio 适配，窗口 resize 时重建画布；页面隐藏（visibilitychange）时暂停循环。
- 100% 兼容手机浏览器、医院内网旧电脑、iFrame 预览沙箱。

### 4. 机制专用示波器 / 粒子仿真器 + 严格静音

- 按核心痛点定制 1 个仿真器：α2δ-1 听觉门控示波仪、CYP1A2 代谢通道流、或 5-HT/SERT 双曲线减药滑坡图。
- 若包含声学对照演示（向家属演示听觉过敏），**默认严格静音**，必须用户主动点「播放」才出声，且音量从 10% 起，旁边放醒目提示「请先确认佩戴者是否敏感」。

---

## 三、全局无障碍与感官降噪强制清单

每个单文件 HTML 必须内置以下 5 项顶栏控制：

| 控制项 | 具体实现 | 服务对象 |
|---|---|---|
| 双语言层切换 | 顶部分段按钮：医生专业版（术语/PK 参数）/ 患者通俗版（大白话/比喻），同一 DOM 两套文案，切换不重载 | 诊室内外通用 |
| 暗夜墨纸 / 暖棉纸 | 默认 #131518，一键切 #F1EEE7；选择写入 localStorage | 偏头痛、畏光、失眠 |
| 一键大字号 A+ | html.font-large 时根字号 18px，所有容器用 rem/em + flex-wrap，禁止横向滚动 | 脑雾、视疲劳、家属 |
| 一键静止护眼 | 冻结 CSS 动画、SVG 脉冲、Canvas rAF；同时尊重 prefers-reduced-motion | 感官高敏、视觉雪花、前庭敏感 |
| 防手抖与离线导出 | 按钮最小 36–44px；底部纯文本复制（execCommand + clipboard 双保险）、.txt 导出、@media print A4 | 震颤/静坐不能患者、线下交接 |

补充硬性要求：

- 焦点可见：:focus-visible 必须有 2px 高对比描边，不许 outline: none。
- 颜色不是唯一信息载体：风险等级同时用文字与形状（●▲■）表达，照顾色觉障碍。
- 正文行高 ≥ 1.65，段宽 ≤ 72 字符，中文段落可到 38–42 字/行。
- 不用纯图标按钮；图标必须配文字或 aria-label。
- 触控目标之间至少 8px 间距，防止误触。

---

## 四、CSS Design Tokens 基准模板

    /* Dark Ink Paper (default, low glare) */
    :root[data-theme="dark"] {
      --bg-canvas: #131518;
      --bg-surface: #1a1d22;
      --bg-elevated: #21252c;
      --bg-recessed: #101215;
      --border-hairline: rgba(255, 255, 255, 0.085);
      --border-strong: rgba(255, 255, 255, 0.16);
      --ink-primary: #efede8;
      --ink-secondary: #a8adb8;
      --ink-muted: #707684;
      --pigment-teal: #6ab5a6;   /* 缓解 / 达标 / 阳性线索 */
      --pigment-coral: #da7a70;  /* 风险 / 过载 / 红线 */
      --pigment-amber: #d9a554;  /* 预警 / 待排查 / 波动 */
      --pigment-slate: #8ca4cf;  /* 结构 / 神经通路 / 中性 */
    }

    /* Warm Cotton Paper (daylight & clinic) */
    :root[data-theme="light"] {
      --bg-canvas: #f1eee7;
      --bg-surface: #faf8f3;
      --bg-elevated: #ffffff;
      --bg-recessed: #e9e4da;
      --border-hairline: rgba(38, 35, 30, 0.11);
      --border-strong: rgba(38, 35, 30, 0.22);
      --ink-primary: #1d1c19;
      --ink-secondary: #4e4b44;
      --ink-muted: #7b766b;
      --pigment-teal: #246a5e;
      --pigment-coral: #b3463c;
      --pigment-amber: #9b6718;
      --pigment-slate: #3d5782;
    }

排版与动效：

    :root {
      --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC",
                   "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Consolas, monospace;
      --radius-card: 10px;
      --radius-control: 8px;
      --space-1: 4px; --space-2: 8px; --space-3: 12px;
      --space-4: 16px; --space-5: 24px; --space-6: 32px;
      --dur-fast: 120ms; --dur-base: 200ms; --ease: cubic-bezier(0.2, 0, 0.2, 1);
    }

    .nums { font-variant-numeric: tabular-nums; font-feature-settings: "tnum" 1; }

    html.font-large { font-size: 18px; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
    }
    html[data-motion="off"] *, html[data-motion="off"] *::before, html[data-motion="off"] *::after {
      animation: none !important; transition: none !important;
    }

纸纤维噪点（可选，必须极低透明度，且不参与合成层重绘）：

    body::before {
      content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
      opacity: 0.02; background-image: url("data:image/svg+xml,..."); /* 内联 SVG feTurbulence，禁止外链 */
    }

---

## 五、HTML 生成契约

### 5.1 文档骨架

    <!doctype html>
    <html lang="zh-CN" data-theme="dark" data-motion="on">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
      <title>问诊整理报告 · 仅供就诊沟通</title>
      <style> /* 全部内联 */ </style>
    </head>
    <body>
      <header class="topbar"> 控 制 区（主题 / 语言层 / A+ / 静止 / 打印） </header>
      <main>
        <section id="s01-summary">  3 秒定心丸 + 风险灯号 + 3 条结论
        <section id="s02-map">      01 分层机制图谱
        <section id="s03-pk">       02 48h 药代沙盒
        <section id="s04-lab">      03 机制实验室 + 3D 分子
        <section id="s05-audit">    04 用药审计矩阵
        <section id="s06-card">     05 功能曲线 + 检验清单 + 沟通卡
      </main>
      <footer> 免责声明 + 生成时间 + 数据来源 + 危机热线（可折叠） </footer>
      <script> /* 全部内联：数据 + 渲染 + 交互 */ </script>
    </body>
    </html>

### 5.2 数据注入

把整份 PatientIntakeState 与生成的结论文案注入一个全局对象，便于审查与二次修改：

    window.__REPORT__ = {
      meta: { generated_at: "2026-11-22T12:00:00+08:00", version: "2.0.0" },
      patient: { /* PatientIntakeState 原样 */ },
      findings: [ { id, kind: "mismatch|dose|interaction|organic|side_effect", title, evidence, impact, ask_doctor } ],
      pk: { drugs: [ { name, dose_mg, times: [8, 20], half_life_h, F, ka_per_h, source } ] },
      molecules: [ { name, atoms: [...], bonds: [...] } ],
      copy_text: "30 秒沟通卡的纯文本版本"
    };

硬规则：
- 禁止把 token、真实姓名、手机号、住址写进报告；姓名只留一个用户自填的称呼。
- 所有时间用本地时区并带 UTC 偏移，不要用「3 小时前」这类相对时间。
- 若某模块数据缺失：隐藏模块，或在原位显示「本项未采集（原因）」——**不允许用示例数据填充**。
- **数据不足时的降级路径（强制）**：
  - 没有「确切剂量 + 可信 t½」→ 不画 PK 曲线，改画「给药时间线 + 主观波动折线」，并在标题写明「未建模」。
  - 没有分子结构数据 → 不出 3D 模块，把版面让给机制图谱。
  - 没有检验结果 → 只出「待补清单」与「为什么查」，不画正常值参考带。
  - 没有功能锚点分数 → 用文字描述替代曲线，不留空坐标轴。

### 5.3 JS 模块划分（单文件内用注释分区，不要拆文件）

    1. THEME     主题切换 / localStorage / prefers-color-scheme
    2. MOTION    静止护眼开关 / visibilitychange 暂停
    3. LANG      医生版 / 患者版文案切换（data-layer 属性驱动）
    4. SVG_MAP   引线布局 + 状态切换
    5. PK        Bateman 求值 + 画布绘制 + 游标拖拽 + 参数面板
    6. MOLECULE  3D 旋转 / 投影 / 深度排序 / 阻尼
    7. AUDIT     矩阵渲染 + 筛选
    8. EXPORT    复制 / .txt 下载 / 打印前展开
    9. A11Y      焦点管理 / aria-live 提示

### 5.4 交互细节硬要求

- 滑块 input[type=range] 必须同时支持键盘（←/→，步长 1）与触屏；拖动时用 aria-live="polite" 播报关键读数（节流 300ms）。
- 游标拖拽用 pointerdown/pointermove/pointerup + setPointerCapture，不要只绑 mousemove（触屏会失效）。
- 复制按钮：先试 navigator.clipboard.writeText，失败回退到隐藏 textarea + document.execCommand('copy')，两者都失败则弹出可选中的文本框（不用 alert）。
- 下载：new Blob([text], {type: "text/plain;charset=utf-8"}) + a[download]，URL.revokeObjectURL 及时释放。
- 打印：@media print 下隐藏顶栏/游标/按钮，展开所有折叠内容，黑白友好（风险色改为灰度+文字），分页避免切断表格行（break-inside: avoid）。

---

## 六、@media print 基准

    @media print {
      @page { size: A4; margin: 14mm 12mm; }
      html, body { background: #fff !important; color: #000 !important; font-size: 10.5pt; }
      .topbar, .no-print, canvas { display: none !important; }
      section { break-inside: avoid; page-break-inside: avoid; }
      table { width: 100%; border-collapse: collapse; }
      th, td { border: 1px solid #999; padding: 4px 6px; }
      a[href]::after { content: " (" attr(href) ")"; font-size: 8pt; color: #555; }
    }

---

## 七、生成后自检（逐条打勾，不合格就改）

- [ ] 断网打开：无 404、无字体回退错乱、无空白画布。
- [ ] 手机 375px 宽：无横向滚动，图谱不重叠，按钮可点。
- [ ] 切到暖棉纸：文字对比度仍 ≥ 4.5:1（正文 ≥ 7:1）。
- [ ] A+ 后：所有卡片文字放大且不溢出，表格可横向滚动但页面不滚。
- [ ] 静止护眼：所有动画停止，Canvas 不再重绘（用 Performance 面板确认）。
- [ ] 键盘 Tab 一遍：焦点顺序合理，焦点环可见，无键盘陷阱。
- [ ] 时间游标：鼠标与触屏都能拖，读数同步，松手不回弹错位。
- [ ] 3D 分子：拖拽跟手，松手阻尼停下，切后台再回来不狂转。
- [ ] 复制：粘贴到记事本，中文与换行完整。
- [ ] 打印预览：A4 两页内，无内容被裁切，风险色在黑白下仍可辨。
- [ ] 数据审查：报告里出现的每个药，都是用户说过的；每个数字，都有来源或「假设」标注。
- [ ] 免责声明与危机热线在页脚可见（折叠也算可见，但折叠标题必须写清热线）。

---

## 八、反面清单（出现即重做）

| 反模式 | 为什么不行 | 替代 |
|---|---|---|
| 深色背景 + 霓虹青紫渐变 | 眩光、偏头痛触发、廉价感 | 墨纸底 + 单一矿物强调色 |
| 大面积毛玻璃 / backdrop-filter | 旧设备掉帧、文字发虚 | 实色 surface + 1px 边框 |
| 自动旋转的 3D 器官 | 前庭不适、遮挡标注 | 静止 + 用户拖拽 |
| 双 Y 轴折线 | 误导相关性 | 两张小图或归一化后单轴 |
| 8 条以上曲线同屏 | 读不出重点 | 拆图或默认只显示 2 条 |
| 满屏 emoji 当图标 | 跨平台渲染不一致、不专业 | 内联 SVG 或文字标签 |
| alert() 报错 | 阻断、不可样式化、iFrame 里丑 | 内联提示条 + aria-live |
| 把「未采集」写成「正常」 | 医疗误导，最严重的一类错误 | 明确标注未采集 |
| 用 AI 生成的「科技感」视觉方案 | 眩光、廉价、与医疗场景冲突 | 见第九节：只用人工创作的参考 |

---

## 九、示例与参考来源政策（硬规则）

本节原来只有一条文字规则，现在落地成可执行的产物：**references/design-references.md**。

生成报告前必须按它做两件事：

1. **用白名单里的链接当参考，不用凭空想象。** 白名单是 GOV.UK Design System、NHS Service Manual、Our World in Data、Distill.pub、Linear、Bearable、Oura。每个链接在文件里标注了「看什么具体组件」和「明确不抄什么」。新增参考的唯一准入条件是写清「它解决了什么具体问题 + 它的用户是谁、验证过吗」。
2. **生成后照走查清单逐条打勾，不通过就改。** 清单分四组：患者视角（首屏 3 行读完、A+ 放大不溢出、畏光调最低亮度可读、手抖点击区 ≥ 44px、脑雾只读标题+首段能懂、有可复述的一句话）、医生视角（30 秒定位药名/剂量/风险/下一步）、环境（断网、375px、旧电脑、A4 打印、复制不乱码）、诚实性（每个药都是用户说过的、缺失明确标注、免责与热线可见）。

仍然禁止：把 AI 生成的截图、配色方案、组件库当作设计依据；用「未来感 / 赛博 / 沉浸式」作为设计目标描述。

**从患者使用者角度，这份清单特别强调四点**（这是患者实际打开报告时的处境，不是医生的工作台）：

- 报告经常在症状最重的时候、深夜、手机上被打开——所以首屏必须是「我现在该做什么」，不是视觉展示。
- 患者可能要念给医生听、要转发给家属、要打印带给门诊——所以必须能复制不乱码、能 A4 打印、有一句话摘要。
- 患者会反复回看——所以交互必须稳定，没有「关掉就丢」的临时状态。
- 患者处于急性期时认知负荷高——所以每个 section 只读标题加第一段就能懂。

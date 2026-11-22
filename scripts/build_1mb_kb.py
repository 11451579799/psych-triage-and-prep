#!/usr/bin/env python3
"""
psych-triage-and-prep Knowledge Base Hydrator (v2.0)
----------------------------------------------------
Build an authoritative, sharded pharmacology knowledge base from public APIs:

  1. OpenFDA Drug Labeling API  https://api.fda.gov/drug/label.json
  2. PubChem PUG-REST API       https://pubchem.ncbi.nlm.nih.gov/rest/pug

Outputs:
  references/openfda-drugs/<slug>.md   one monograph per compound
  references/kb-index.json             lightweight lookup index

Design goals:
  * > 1.5 MB of high-density, verifiable text so an agent can retrieve
    label-level detail on demand WITHOUT loading everything into context.
  * No API key required. Standard library only. Idempotent and resumable.
  * Every shard states its source URL and fetch timestamp.

Usage:
    python scripts/build_1mb_kb.py
    python scripts/build_1mb_kb.py --delay 0.4 --out references
    python scripts/build_1mb_kb.py --only duloxetine,pregabalin --force
    python scripts/build_1mb_kb.py --no-pubchem
    python scripts/build_1mb_kb.py --check          # verify size only

Exit codes: 0 ok, 1 hard failure, 2 built but below --min-bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
USER_AGENT = (
    "psych-triage-and-prep/2.0 "
    "(+https://github.com/11451579799/psych-triage-and-prep)"
)

# (label key, Chinese heading, max chars)
SECTIONS: List[Tuple[str, str, int]] = [
    ("boxed_warning", "黑框警告", 1800),
    ("indications_and_usage", "适应症与用途", 2600),
    ("dosage_and_administration", "剂量与给药", 3200),
    ("dosage_forms_and_strengths", "剂型与规格", 1200),
    ("contraindications", "禁忌", 1800),
    ("warnings_and_cautions", "警告与注意事项", 6000),
    ("adverse_reactions", "不良反应", 4200),
    ("drug_interactions", "药物相互作用", 3600),
    ("use_in_specific_populations", "特殊人群用药", 2400),
    ("overdosage", "过量表现（仅用于识别中毒征象，不构成处理指导）", 1600),
    ("description", "化学描述", 1800),
    ("clinical_pharmacology", "临床药理学（含 PK/PD）", 4200),
]

# ---------------------------------------------------------------------------
# Registry: 111 compounds. Fields:
#   slug, inn, cn, cls, targets, half_life, cyp, note, query (OpenFDA), pubchem
# Numbers are teaching approximations; label text is the authoritative part.
# ---------------------------------------------------------------------------
REGISTRY: List[Dict[str, str]] = [
    # --- SSRI ---
    dict(slug="escitalopram", inn="escitalopram", cn="艾司西酞普兰", cls="SSRI（纯 S-对映体）",
         targets="SERT ≈1.1 nM；几乎不碰 H1/M1/α1", half_life="27–32 h", cyp="底物 2C19/3A4；弱抑 2D6",
         note="去掉了西酞普兰中干扰结合的 R 体；高剂量留意 QTc 延长。"),
    dict(slug="citalopram", inn="citalopram", cn="西酞普兰", cls="SSRI（外消旋）",
         targets="SERT ≈1.8 nM", half_life="35 h", cyp="2C19/3A4",
         note="剂量相关 QTc 延长比艾司西酞普兰更明显，>40 mg 需谨慎。"),
    dict(slug="sertraline", inn="sertraline", cn="舍曲林", cls="SSRI + 弱 DAT + σ1",
         targets="SERT ≈0.29 nM；DAT ≈25 nM；σ1 高亲和", half_life="26 h（去甲舍曲林 62–104 h）", cyp="底物 2B6/2C19；中抑 2D6",
         note="腹泻/稀便常见；心血管安全性较好；高剂量可致情绪钝化。"),
    dict(slug="fluoxetine", inn="fluoxetine", cn="氟西汀", cls="SSRI（长效）",
         targets="SERT ≈0.8 nM；5-HT2C 拮抗", half_life="母药 1–4 d；去甲氟西汀 7–15 d", cyp="强抑 2D6，中抑 2C19",
         note="自带长尾，撤药最少，但换 MAOI 需 5 周洗脱；与 2D6 底物冲突大。"),
    dict(slug="paroxetine", inn="paroxetine", cn="帕罗西汀", cls="SSRI（强镇静/抗胆碱）",
         targets="SERT ≈0.1 nM；M1 ≈108 nM", half_life="21 h（非线性）", cyp="极强抑 2D6",
         note="口干便秘嗜睡发胖明显；撤药反应最凶之一，严禁骤停。"),
    dict(slug="fluvoxamine", inn="fluvoxamine", cn="氟伏沙明", cls="SSRI（强 σ1 激动）",
         targets="SERT ≈2.2 nM；σ1 ≈36 nM", half_life="15 h", cyp="极强抑 1A2 与 2C19",
         note="与咖啡因/茶碱/氯氮平/奥氮平/替扎尼定高危；强迫症与躯体关注优势。"),
    # --- SNRI ---
    dict(slug="venlafaxine", inn="venlafaxine", cn="文拉法辛", cls="SNRI（剂量依赖双通道）",
         targets="低量偏 SERT，≥150 mg 明显切入 NET", half_life="母药 5 h；去甲文拉法辛 11 h", cyp="经 2D6 转为活性代谢物",
         note="缓释不可嚼碎；漏服一次即剧烈眩晕与过电感；高剂量监测血压。"),
    dict(slug="desvenlafaxine", inn="desvenlafaxine", cn="去甲文拉法辛", cls="SNRI（活性代谢物直接给药）",
         targets="SERT/NET 均衡", half_life="11 h", cyp="主要 UGT 结合，CYP 依赖低",
         note="与 2D6 抑制剂相互作用少；撤药仍明显，需缓减。"),
    dict(slug="duloxetine", inn="duloxetine", cn="度洛西汀", cls="SNRI（均衡，纯 S 体）",
         targets="SERT ≈0.8 nM；NET ≈7.5 nM", half_life="12 h", cyp="主 1A2，次 2D6；中抑 2D6",
         note="肠溶微丸严禁掰开；吸烟降浓度、戒烟升浓度；镇痛/抑郁靶量常 60 mg/d。"),
    dict(slug="milnacipran", inn="milnacipran", cn="米那普仑", cls="SNRI（NE 强于 5-HT）",
         targets="NET > SERT", half_life="8 h", cyp="主要肾排泄",
         note="心慌、血压升高、出汗更明显；纤维肌痛常用。"),
    # --- 其他抗抑郁 ---
    dict(slug="bupropion", inn="bupropion", cn="安非他酮", cls="NDRI（无 5-HT 效应）",
         targets="NET/DAT 弱抑制；nAChR 拮抗", half_life="21 h（羟安非他酮 20 h）", cyp="底物 2B6；强抑 2D6",
         note="改善动力/嗜睡/性功能，不钝化；降癫痫阈值（进食障碍、骤戒酒、既往癫痫禁用）。"),
    dict(slug="mirtazapine", inn="mirtazapine", cn="米氮平", cls="NaSSA（α2 拮抗）",
         targets="α2 拮抗 + 5-HT2A/2C/3 拮抗 + H1 ≈0.14 nM", half_life="20–40 h", cyp="1A2/2D6/3A4（低抑制）",
         note="低剂量（7.5–15 mg）H1 助眠最强，≥30 mg 才显 NE 激活；嗜睡与碳水渴求显著。"),
    dict(slug="vortioxetine", inn="vortioxetine", cn="伏硫西汀", cls="多模式 5-HT 调节剂",
         targets="SERT 抑制 + 5-HT1A 激动 + 1B 部分激动 + 3/7/1D 拮抗", half_life="66 h", cyp="主 2D6（弱抑）",
         note="改善抑郁相关认知证据最足；撤药少；初期恶心，随餐服。"),
    dict(slug="trazodone", inn="trazodone", cn="曲唑酮", cls="SARI",
         targets="5-HT2A 强拮抗 + α1 + H1（高量才抑 SERT）", half_life="5–9 h", cyp="3A4（活性代谢物 mCPP）",
         note="低剂量常用作无成瘾助眠；起身防体位性低血压；异常勃起极罕见但需急诊。"),
    dict(slug="vilazodone", inn="vilazodone", cn="维拉佐酮", cls="SSRI + 5-HT1A 部分激动",
         targets="SERT 抑制 + 1A 激动", half_life="25 h", cyp="3A4",
         note="必须随餐（空腹吸收差）；腹泻较多。"),
    dict(slug="agomelatine", inn="agomelatine", cn="阿戈美拉汀", cls="MT1/MT2 激动 + 5-HT2C 拮抗",
         targets="褪黑素受体", half_life="1–2 h", cyp="1A2（强抑者禁用）",
         note="需监测肝功；对睡眠节律紊乱型抑郁有优势。"),
    # --- TCA ---
    dict(slug="amitriptyline", inn="amitriptyline", cn="阿米替林", cls="TCA",
         targets="5-HT/NE 再摄取 + 抗胆碱 + α1 + H1", half_life="10–28 h", cyp="2D6/2C19",
         note="过量致死性心律失常；低剂量常用于神经痛/偏头痛预防；老年慎用。"),
    dict(slug="nortriptyline", inn="nortriptyline", cn="去甲替林", cls="TCA（NE 为主）",
         targets="NE > 5-HT 再摄取", half_life="18–44 h", cyp="2D6",
         note="治疗窗窄，血药浓度监测有意义；抗胆碱比阿米替林轻。"),
    dict(slug="clomipramine", inn="clomipramine", cn="氯米帕明", cls="TCA（5-HT 最强）",
         targets="SERT 强抑制", half_life="20–32 h", cyp="2D6/1A2/2C19",
         note="癫痫阈值下降、性功能影响、撤药重；强迫症老牌用药。"),
    dict(slug="imipramine", inn="imipramine", cn="丙咪嗪", cls="TCA",
         targets="5-HT/NE 再摄取", half_life="6–20 h", cyp="2D6/2C19",
         note="体位性低血压、传导阻滞；现多用于难治病例。"),
    dict(slug="doxepin", inn="doxepin", cn="多塞平", cls="TCA（低剂量纯 H1）",
         targets="H1 高亲和（低剂量）", half_life="15–30 h", cyp="2D6/2C19",
         note="3–6 mg 助眠剂量几乎无抗胆碱；高剂量才显抗抑郁作用。"),
    # --- MAOI ---
    dict(slug="phenelzine", inn="phenelzine", cn="苯乙肼", cls="不可逆 MAOI",
         targets="MAO-A/B 不可逆抑制", half_life="≈11 h（效应远超半衰期）", cyp="经氧化代谢",
         note="高血压危象（酪胺）与 5-HT 综合征；饮食限制极严，仅难治病例。"),
    dict(slug="tranylcypromine", inn="tranylcypromine", cn="反苯环丙胺", cls="不可逆 MAOI",
         targets="MAO-A/B 不可逆抑制 + 苯丙胺样作用", half_life="≈2.5 h", cyp="—",
         note="起效相对快但交互极凶；换药洗脱期必须严格遵守。"),
    dict(slug="selegiline", inn="selegiline", cn="司来吉兰", cls="MAO-B 抑制剂（低剂量选择性）",
         targets="MAO-B", half_life="≈1.5 h（代谢物 4–8 h）", cyp="2B6/2C19/3A4",
         note="高剂量失去选择性 → 需酪胺限制；透皮剂型用于难治抑郁。"),
    # --- 抗焦虑 / 感觉门控 ---
    dict(slug="pregabalin", inn="pregabalin", cn="普瑞巴林", cls="电压门控钙通道调节剂（α2δ-1）",
         targets="α2δ-1 Ki ≈32 nM；减少 Ca2+ 内流与谷氨酸/P 物质/NE 释放", half_life="6.3 h", cyp=">98% 肾原型，几乎无 CYP 交互",
         note="广泛性焦虑、神经痛、纤维肌痛、中枢感觉门控失调核心药；忌过山车式吃法；与阿片/BZD 叠加有呼吸抑制风险。"),
    dict(slug="gabapentin", inn="gabapentin", cn="加巴喷丁", cls="α2δ-1 调节剂",
         targets="α2δ-1；肠道 L-氨基酸转运体饱和吸收", half_life="5–7 h", cyp="肾原型",
         note="剂量越高生物利用度反而下降（非线性），必须分次；骤停可抽搐。"),
    dict(slug="buspirone", inn="buspirone", cn="丁螺环酮", cls="氮杂螺环酮类抗焦虑",
         targets="5-HT1A 部分激动", half_life="2–3 h", cyp="3A4（忌大量西柚汁）",
         note="需 2–4 周起效，不能当急性惊恐急救；无依赖性。"),
    dict(slug="hydroxyzine", inn="hydroxyzine", cn="羟嗪", cls="H1 拮抗",
         targets="H1", half_life="≈20 h", cyp="肝代谢",
         note="抗组胺助眠/抗焦虑；抗胆碱与次日昏沉。"),
    # --- BZD ---
    dict(slug="lorazepam", inn="lorazepam", cn="劳拉西泮", cls="苯二氮䓬（BZD）",
         targets="GABAA 正向变构（无活性代谢物）", half_life="10–20 h", cyp="仅 UGT 葡萄糖醛酸化",
         note="急救效强；长期用 → 耐受、记忆编码抑制、撤药反跳；肝功受损相对安全。"),
    dict(slug="alprazolam", inn="alprazolam", cn="阿普唑仑", cls="BZD（三唑类）",
         targets="GABAA", half_life="6–12 h", cyp="3A4",
         note="起效快、依赖与反跳最凶；撤药极难。"),
    dict(slug="clonazepam", inn="clonazepam", cn="氯硝西泮", cls="BZD",
         targets="GABAA", half_life="20–40 h", cyp="3A4",
         note="长效、抗惊厥；镇静与共济失调明显；撤药慢。"),
    dict(slug="diazepam", inn="diazepam", cn="地西泮", cls="BZD",
         targets="GABAA", half_life="20–100 h（活性代谢物）", cyp="2C19/3A4",
         note="长半衰期自带渐减；肌松与跌倒风险，老年慎用。"),
    # --- Z-drug ---
    dict(slug="zolpidem", inn="zolpidem", cn="唑吡坦", cls="Z-drug（α1 偏好）",
         targets="GABAA α1 亚型偏好", half_life="2–3 h", cyp="3A4",
         note="复杂睡眠行为（睡行、睡吃）；女性建议更低剂量；不与其它镇静剂叠加。"),
    dict(slug="eszopiclone", inn="eszopiclone", cn="右佐匹克隆", cls="Z-drug",
         targets="GABAA", half_life="6 h", cyp="3A4",
         note="口苦金属味；次日残留镇静。"),
    dict(slug="zaleplon", inn="zaleplon", cn="扎来普隆", cls="Z-drug（超短效）",
         targets="GABAA", half_life="1 h", cyp="3A4",
         note="入睡困难专用；半夜服用次日残留少。"),
    # --- DORA ---
    dict(slug="suvorexant", inn="suvorexant", cn="苏沃雷生", cls="双重食欲素受体拮抗剂（DORA）",
         targets="OX1R/OX2R", half_life="≈12 h", cyp="3A4",
         note="保留较自然睡眠架构；高脂餐延缓起效；偶见生梦。"),
    dict(slug="lemborexant", inn="lemborexant", cn="莱博雷生", cls="DORA",
         targets="OX1R/OX2R", half_life="17–19 h", cyp="3A4",
         note="入睡与睡眠维持兼顾；次日嗜睡个体差异大。"),
    dict(slug="daridorexant", inn="daridorexant", cn="达利雷生", cls="DORA",
         targets="OX1R/OX2R", half_life="≈8 h", cyp="3A4",
         note="半衰期较短，次日残留相对少；高脂餐影响吸收。"),
    # --- 心境稳定剂 ---
    dict(slug="lithium-carbonate", inn="lithium carbonate", cn="碳酸锂", cls="心境稳定剂",
         targets="抑制 GSK-3β、调节肌醇第二信使", half_life="18–24 h", cyp="肾原型，与钠竞争重吸收",
         note="治疗窗 0.6–1.0 mmol/L；唯一有明确抗自杀循证；脱水/低盐/NSAIDs 可致中毒。"),
    dict(slug="lamotrigine", inn="lamotrigine", cn="拉莫三嗪", cls="心境稳定剂（谷氨酸调节）",
         targets="电压门控 Na+ 通道阻滞，减少谷氨酸释放", half_life="25–33 h（合用丙戊酸 ≈70 h）", cyp="UGT1A4",
         note="双相抑郁低谷；必须极慢滴定，皮疹伴发热或黏膜不适立即停药就医（防 SJS/TEN）。"),
    dict(slug="divalproex-sodium", inn="divalproex sodium", cn="双丙戊酸钠", cls="心境稳定剂",
         targets="Na+ 通道、GABA 转氨酶抑制", half_life="9–16 h", cyp="2C9/2C19/UGT；强抑 UGT",
         note="肝毒性、胰腺炎、血小板下降；育龄女性禁用（致畸与神经发育风险）。"),
    dict(slug="carbamazepine", inn="carbamazepine", cn="卡马西平", cls="心境稳定剂/抗惊厥",
         targets="Na+ 通道阻滞", half_life="12–17 h（自身诱导后 8–12 h）", cyp="强诱导 3A4/1A2/2C9",
         note="低钠、剥脱性皮炎（HLA-B*1502 筛查）、药物交互极多。"),
    dict(slug="oxcarbazepine", inn="oxcarbazepine", cn="奥卡西平", cls="抗惊厥/心境稳定",
         targets="Na+ 通道阻滞（活性代谢物 MHD）", half_life="母药 2 h；MHD 9 h", cyp="弱诱导 3A4",
         note="低钠更常见；皮疹风险低于卡马西平但仍有。"),
    # --- 抗精神病药 ---
    dict(slug="quetiapine", inn="quetiapine", cn="喹硫平", cls="非典型抗精神病药",
         targets="H1 主导（低量）；中量去甲喹硫平抑 NET + 5-HT1A", half_life="6–7 h（去甲 12 h）", cyp="3A4",
         note="低量助眠/抗激越；监测嗜睡、体位性低血压、血脂血糖、QTc。"),
    dict(slug="olanzapine", inn="olanzapine", cn="奥氮平", cls="非典型抗精神病药",
         targets="D2/5-HT2A 强拮抗 + H1/M1", half_life="33 h", cyp="1A2/2D6",
         note="代谢负担最大之一；吸烟量变化时浓度波动明显。"),
    dict(slug="aripiprazole", inn="aripiprazole", cn="阿立哌唑", cls="非典型抗精神病药（部分激动）",
         targets="D2/5-HT1A 部分激动", half_life="75 h（脱氢 94 h）", cyp="2D6/3A4",
         note="低剂量（2–5 mg）增效抗抑郁；静坐不能高发；可致失眠。"),
    dict(slug="brexpiprazole", inn="brexpiprazole", cn="布瑞哌唑", cls="非典型抗精神病药",
         targets="D2 部分激动 + 5-HT2A/α1 拮抗", half_life="91 h", cyp="2D6/3A4",
         note="静坐不能少于阿立哌唑；体重增加中等。"),
    dict(slug="lurasidone", inn="lurasidone", cn="鲁拉西酮", cls="非典型抗精神病药",
         targets="D2/5-HT2A/5-HT7 拮抗 + 5-HT1A 部分激动；几乎不碰 H1/M1", half_life="18 h", cyp="3A4（忌强抑与西柚）",
         note="双相抑郁优势，少发胖少脑雾；必须随 ≥350 kcal 正餐，否则吸收腰斩；留意早期静坐不能。"),
    dict(slug="risperidone", inn="risperidone", cn="利培酮", cls="非典型抗精神病药",
         targets="D2/5-HT2A 强拮抗", half_life="3 h（9-羟利培酮 24 h）", cyp="2D6",
         note="高催乳素、EPS、体位性低血压；长效针剂常用。"),
    dict(slug="paliperidone", inn="paliperidone", cn="帕利哌酮", cls="非典型抗精神病药",
         targets="利培酮活性代谢物", half_life="23 h", cyp="肾排泄为主",
         note="与 2D6/3A4 交互少于利培酮；长效针剂依从性好。"),
    dict(slug="ziprasidone", inn="ziprasidone", cn="齐拉西酮", cls="非典型抗精神病药",
         targets="D2/5-HT2A + 5-HT/NE 再摄取", half_life="7 h", cyp="1A2（3A4 少）",
         note="QTc 延长最需注意；必须随餐。"),
    dict(slug="haloperidol", inn="haloperidol", cn="氟哌啶醇", cls="高效价第一代抗精神病药",
         targets="D2 强拮抗", half_life="18 h", cyp="2D6/3A4",
         note="EPS/静坐不能/急性肌张力障碍/NMS 风险高；谵妄短期用仍广泛。"),
    dict(slug="clozapine", inn="clozapine", cn="氯氮平", cls="非典型抗精神病药（多受体弱结合）",
         targets="D4/5-HT2A/M1/H1 等", half_life="12 h", cyp="1A2/2D6/3A4",
         note="难治性精神分裂金标准；粒细胞缺乏必须定期血常规；便秘/肠梗阻、心肌炎、癫痫阈值下降。"),
    dict(slug="cariprazine", inn="cariprazine", cn="卡利拉嗪", cls="非典型抗精神病药（D3 偏好部分激动）",
         targets="D3/D2 部分激动", half_life="2–4 d（代谢物数周）", cyp="3A4",
         note="阴性症状与双相抑郁；静坐不能；半衰期长，撤药自带渐减。"),
    dict(slug="amisulpride", inn="amisulpride", cn="氨磺必利", cls="非典型抗精神病药（纯 D2/D3）",
         targets="D2/D3 拮抗（低量偏突触前）", half_life="12 h", cyp="肾排泄",
         note="低量偏抑郁/阴性，高量抗阳性；催乳素升高显著；QTc。"),
    # --- ADHD ---
    dict(slug="methylphenidate", inn="methylphenidate", cn="哌甲酯", cls="中枢兴奋剂",
         targets="DAT/NET 阻断", half_life="2–4 h（缓释 8–12 h）", cyp="CES1 水解",
         note="心率血压、食欲、睡眠；滥用潜力，需处方管理。"),
    dict(slug="amphetamine", inn="amphetamine", cn="苯丙胺类", cls="中枢兴奋剂",
         targets="DAT/NET 释放 + 阻断", half_life="10–13 h", cyp="2D6",
         note="心血管筛查；焦虑/抽动慎用。"),
    dict(slug="lisdexamfetamine", inn="lisdexamfetamine", cn="赖氨酸安非他明", cls="中枢兴奋剂（前药）",
         targets="经红细胞水解为右苯丙胺", half_life="10–12 h", cyp="—",
         note="前药设计降低滥用（仍非零）；起效平稳。"),
    dict(slug="atomoxetine", inn="atomoxetine", cn="托莫西汀", cls="选择性 NE 再摄取抑制剂",
         targets="NET 选择性抑制", half_life="5 h（活性代谢物 24 h）", cyp="2D6",
         note="2–4 周起效；2D6 慢代谢者浓度高；恶心、心率升、肝损罕见。"),
    dict(slug="modafinil", inn="modafinil", cn="莫达非尼", cls="促觉醒药",
         targets="DAT 抑制 + 促觉醒", half_life="12–15 h", cyp="3A4",
         note="发作性睡病/轮班；皮疹（SJS 罕见）；避孕药效下降。"),
    # --- 谷氨酸能 ---
    dict(slug="esketamine", inn="esketamine", cn="艾司氯胺酮", cls="NMDA 受体拮抗剂（鼻喷）",
         targets="NMDA 非竞争拮抗 → AMPA 激活与 mTOR/BDNF 突触新生", half_life="7–12 h", cyp="2B6/3A4",
         note="仅限医疗机构监护下用于难治性抑郁；给药后 2 h 监测血压与一过性解离。"),
    # --- 高频交互物质 ---
    dict(slug="caffeine", inn="caffeine", cn="咖啡因", cls="黄嘌呤类中枢兴奋剂",
         targets="腺苷 A1/A2A 拮抗", half_life="3–7 h（个体差异大）", cyp="1A2",
         note="竞争 CYP1A2；加重心慌、震颤、失眠；下午 2 点后摄入影响睡眠。"),
    dict(slug="dextromethorphan", inn="dextromethorphan", cn="右美沙芬", cls="OTC 止咳药",
         targets="NMDA 拮抗 + SERT 抑制 + σ1", half_life="2–4 h", cyp="2D6",
         note="与 SSRI/SNRI/曲马多合用可致 5-HT 综合征；感冒药必查成分表。"),
    dict(slug="diphenhydramine", inn="diphenhydramine", cn="苯海拉明", cls="第一代抗组胺药",
         targets="H1 + M1", half_life="4–8 h", cyp="2D6",
         note="叠加嗜睡与抗胆碱负荷；老年与脑雾患者尽量避开。"),
    dict(slug="ibuprofen", inn="ibuprofen", cn="布洛芬", cls="NSAID",
         targets="COX-1/COX-2", half_life="2 h", cyp="2C9",
         note="与 SSRI/SNRI 合用增加消化道出血风险；与锂合用升血锂。"),
    dict(slug="naproxen", inn="naproxen", cn="萘普生", cls="NSAID",
         targets="COX-1/COX-2", half_life="12–17 h", cyp="2C9",
         note="长半衰期 NSAID，出血与肾影响更持久；与锂、ACEI 冲突。"),
    dict(slug="omeprazole", inn="omeprazole", cn="奥美拉唑", cls="质子泵抑制剂",
         targets="H+/K+-ATP 酶", half_life="0.5–1 h（抑酸效应 24 h+）", cyp="2C19（抑制）",
         note="抑 2C19 升西酞普兰/艾司西酞普兰浓度；长期使用影响 B12/镁。"),
    dict(slug="tramadol", inn="tramadol", cn="曲马多", cls="弱阿片 + 5-HT/NE 再摄取抑制",
         targets="μ 激动 + SERT/NET", half_life="6 h", cyp="2D6/3A4",
         note="与 SSRI/SNRI 合用癫痫与 5-HT 综合征风险；2D6 慢代谢者镇痛弱。"),
    # --- 特殊用途 / OTC 补充 ---
    dict(slug="melatonin", inn="melatonin", cn="褪黑素", cls="MT1/MT2 激动（非处方）",
         targets="MT1/MT2 激动；不作用于 GABAA", half_life="1–2 h（缓释 3–4 h）", cyp="1A2（强抑者暴露升高）",
         note="各国按保健品或处方管理；对入睡潜伏期效应小，对睡眠维持证据弱。剂量随产品差异巨大，不构成处方依据。"),
    dict(slug="ramelteon", inn="ramelteon", cn="雷美替胺", cls="MT1/MT2 激动（处方）",
         targets="MT1 Ki≈0.01 nM；MT2 ≈0.1 nM", half_life="1–2.6 h（活性代谢物 2–5 h）", cyp="1A2 为主",
         note="与氟伏沙明（强抑 1A2）合用暴露升高数十倍，属禁忌；不用于抑郁本身的治疗。"),
    dict(slug="propranolol", inn="propranolol", cn="普萘洛尔", cls="非选择性 β 阻断",
         targets="β1/β2 阻断", half_life="3–6 h（缓释更长）", cyp="2D6",
         note="表演性焦虑、心悸、震颤、锂盐震颤的对症选择；哮喘、心动过缓、低血压禁用；骤停可反跳。"),
    dict(slug="clonidine", inn="clonidine", cn="可乐定", cls="α2 激动",
         targets="α2A 激动，降低中枢交感输出", half_life="6–20 h（个体差异大）", cyp="部分 2D6；约半量肾原型",
         note="抽动、ADHD 辅助、睡眠与激越；突然停药可致反跳性高血压与心动过速。"),
    dict(slug="guanfacine", inn="guanfacine", cn="胍法辛", cls="α2A 选择性激动",
         targets="α2A 选择性（镇静与降压弱于可乐定）", half_life="缓释 14–18 h", cyp="3A4",
         note="ADHD 的非兴奋剂选项、抽动辅助；主要限制是镇静与体位性低血压。"),
    dict(slug="prazosin", inn="prazosin", cn="哌唑嗪", cls="α1 拮抗",
         targets="α1 拮抗", half_life="2–3 h", cyp="肝代谢为主",
         note="创伤后噩梦的循证辅助；首剂体位性低血压明显，须小量起始、睡前服。"),
    # --- 成瘾与替代治疗 ---
    dict(slug="naltrexone", inn="naltrexone", cn="纳曲酮", cls="μ 阿片受体拮抗",
         targets="μ 拮抗（高亲和）", half_life="4 h（6β-纳曲醇 13 h）", cyp="2D6 生成活性代谢物",
         note="酒精使用障碍防复吸、阿片依赖维持期阻断；用前须确认体内无阿片，否则诱发戒断。"),
    dict(slug="acamprosate", inn="acamprosate", cn="阿坎酸", cls="谷氨酸系统调节",
         targets="NMDA 调节 / 钙通道", half_life="20–33 h（给药 TID）", cyp="肾原型排泄",
         note="酒精依赖维持期用药；肾功能不全需减量；起效需数周，不用于急性戒断。"),
    dict(slug="disulfiram", inn="disulfiram", cn="双硫仑", cls="乙醛脱氢酶抑制",
         targets="ALDH 不可逆抑制", half_life="60–120 h（效应更久）", cyp="肝代谢",
         note="饮酒即乙醛蓄积（面红、心悸、呕吐）；需知情同意与监督；肝病、精神病性障碍者禁用。"),
    dict(slug="buprenorphine", inn="buprenorphine", cn="丁丙诺啡", cls="μ 部分激动",
         targets="μ 部分激动 + κ 拮抗", half_life="舌下 24–42 h", cyp="3A4",
         note="阿片依赖替代治疗；对全激动剂高亲和低活性，合用可诱发戒断；诱导期有镇静与呼吸抑制风险。"),
    dict(slug="methadone", inn="methadone", cn="美沙酮", cls="μ 全激动",
         targets="μ 激动 + NMDA 拮抗", half_life="8–59 h（个体差异极大）", cyp="2B6/3A4/2D6",
         note="剂量相关 QTc 延长与呼吸抑制；仅限有资质的替代治疗项目，不得自行调整。"),
    dict(slug="varenicline", inn="varenicline", cn="伐尼克兰", cls="α4β2 nAChR 部分激动",
         targets="α4β2 部分激动（阻断尼古丁奖赏）", half_life="24 h", cyp="约 90% 肾原型",
         note="戒烟一线；留意神经精神不良反应、恶心与驾驶风险。"),
    dict(slug="nicotine", inn="nicotine", cn="尼古丁（替代制剂）", cls="nAChR 激动",
         targets="nAChR 激动", half_life="2 h（贴剂稳态）", cyp="2A6",
         note="贴片/ gums 用于戒烟替代；近期心血管事件者慎用；青少年使用有依赖风险。"),
    # --- 抗精神病药（补） ---
    dict(slug="chlorpromazine", inn="chlorpromazine", cn="氯丙嗪", cls="吩噻嗪类（低效价）",
         targets="D2 拮抗 + α1/H1/M1 强", half_life="≈30 h", cyp="2D6/1A2",
         note="光敏、体位性低血压、EPS 与迟发性运动障碍风险高；现多用于顽固性呃逆与急性激越。"),
    dict(slug="fluphenazine", inn="fluphenazine", cn="氟奋乃静", cls="哌嗪类吩噻嗪（高效价）",
         targets="D2 强拮抗（EPS 风险高）", half_life="33 h；癸酸酯长效 1–3 周", cyp="2D6",
         note="长效针剂用于依从性差者；静坐不能与类帕金森反应明显。"),
    dict(slug="trifluoperazine", inn="trifluoperazine", cn="三氟拉嗪", cls="哌嗪类吩噻嗪",
         targets="D2 强拮抗", half_life="≈24 h", cyp="2D6",
         note="高效价，EPS 与静坐不能风险高；抗胆碱能负荷较低但催乳素升高明显。"),
    dict(slug="sulpiride", inn="sulpiride", cn="舒必利", cls="苯甲酰胺类",
         targets="D2/D3 拮抗（低量偏突触前）", half_life="6–8 h", cyp="肾排泄为主",
         note="低剂量用于躯体化与胃肠症状，高剂量为抗精神病剂量；催乳素升高与 EPS 量效相关。"),
    dict(slug="asenapine", inn="asenapine", cn="阿塞那平", cls="非典型（舌下）",
         targets="D2/5-HT2A 拮抗 + α2 拮抗", half_life="24 h", cyp="1A2 为主",
         note="舌下含服、不可吞服；强抑 1A2 者禁忌；日剂量上限受剂型限制。"),
    dict(slug="pimozide", inn="pimozide", cn="匹莫齐特", cls="二苯丁基哌啶",
         targets="D2 强拮抗 + 钙通道", half_life="≈55 h", cyp="3A4/1A2",
         note="QTc 延长风险最高之列；与强 3A4/2D6 抑制剂及延长 QT 药物禁忌；仅限专科使用。"),
    dict(slug="zuclopenthixol", inn="zuclopenthixol", cn="珠氯噻醇", cls="硫杂蒽类",
         targets="D2/5-HT2A 拮抗", half_life="≈20 h；癸酸酯 19 d", cyp="2D6",
         note="长效针剂；镇静与 EPS 明显，注射部位反应常见。"),
    dict(slug="flupentixol", inn="flupentixol", cn="氟哌噻吨", cls="硫杂蒽类",
         targets="D2 拮抗（低量偏突触前）", half_life="≈35 h；癸酸酯 17 d", cyp="2D6",
         note="部分地区以低剂量与美利曲辛组成复方用于抑郁/焦虑，证据有限且含 TCA 成分。"),
    # --- 抗抑郁药（补） ---
    dict(slug="desipramine", inn="desipramine", cn="地昔帕明", cls="TCA（仲胺）",
         targets="NET 选择性 > SERT", half_life="12–54 h", cyp="2D6",
         note="TCA 中抗胆碱最轻；过量仍可致致死性心律失常，禁用于近期心梗与传导阻滞。"),
    dict(slug="amoxapine", inn="amoxapine", cn="阿莫沙平", cls="TCA（去甲哌嗪类）",
         targets="NET/5-HT 再摄取 + D2 拮抗", half_life="8–30 h", cyp="2D6",
         note="带抗精神病成分：EPS、催乳素升高；过量时癫痫与心律失常风险高。"),
    dict(slug="maprotiline", inn="maprotiline", cn="马普替林", cls="四环类抗抑郁",
         targets="NET 选择性抑制", half_life="27–58 h", cyp="2D6",
         note="过量致心律失常与癫痫；抗胆碱负荷中等。"),
    dict(slug="moclobemide", inn="moclobemide", cn="吗氯贝胺", cls="可逆性 MAO-A 抑制（RIMA）",
         targets="MAO-A 可逆抑制", half_life="1–4 h", cyp="肝代谢",
         note="洗脱期短于不可逆 MAOI（约 1–2 天），但仍禁与 SSRI、曲普坦、哌替啶合用；高血压危象风险低于老 MAOI。"),
    dict(slug="levomilnacipran", inn="levomilnacipran", cn="左米那普仑", cls="SNRI",
         targets="NET > SERT", half_life="≈16 h", cyp="2D6/3A4",
         note="NE 效应强，心率与血压升高比舍曲林类明显；排尿困难与出汗常见。"),
    # --- 苯二氮䓬与催眠（补） ---
    dict(slug="oxazepam", inn="oxazepam", cn="奥沙西泮", cls="BZD（短-中效）",
         targets="GABAA 正向变构", half_life="5–15 h", cyp="仅 UGT 结合，几乎不需 CYP",
         note="老年人、肝病者代谢受影响最小；依赖、跌倒与认知影响与其他 BZD 相同。"),
    dict(slug="temazepam", inn="temazepam", cn="替马西泮", cls="BZD（催眠）",
         targets="GABAA 正向变构", half_life="8–15 h", cyp="UGT 为主",
         note="用于入睡与睡眠维持；次日残留镇静与驾驶风险；间断使用优于长期 nightly。"),
    dict(slug="clobazam", inn="clobazam", cn="氯巴占", cls="BZD（1,5-型）",
         targets="GABAA 正向变构", half_life="18–36 h（去甲代谢物 71–82 h）", cyp="2C19（强抑者暴露显著升高）",
         note="抗癫痫辅助用药；耐受与依赖仍存在，减停需缓慢。"),
    dict(slug="chlordiazepoxide", inn="chlordiazepoxide", cn="氯氮䓬", cls="BZD（长效）",
         targets="GABAA 正向变构", half_life="24–48 h（活性代谢物更长）", cyp="2C19/3A4",
         note="酒精戒断的经典选择；老年人蓄积明显，易致跌倒与意识模糊。"),
    dict(slug="triazolam", inn="triazolam", cn="三唑仑", cls="BZD（超短效）",
         targets="GABAA 正向变构", half_life="2–4 h", cyp="3A4",
         note="起效快、易反跳性失眠与顺行性遗忘；多国限用或禁用。"),
    dict(slug="midazolam", inn="midazolam", cn="咪达唑仑", cls="BZD（短效，注射）",
         targets="GABAA 正向变构", half_life="1.5–3 h", cyp="3A4",
         note="仅限医疗环境下的镇静/麻醉前用药；呼吸抑制与遗忘明显，不存在合理的自助用途。"),
    # --- 锥体外系反应对症 ---
    dict(slug="benztropine", inn="benztropine", cn="苯海索", cls="中枢抗胆碱",
         targets="M1 拮抗（另有轻度抗组胺与多巴胺再摄取抑制）", half_life="5–15 h", cyp="肝代谢",
         note="EPS 与急性肌张力障碍对症；抗胆碱负荷（口干、便秘、尿潴留、谵妄）在青少年与老年人尤其危险。"),
    dict(slug="trihexyphenidyl", inn="trihexyphenidyl", cn="苯海索（安坦）", cls="中枢抗胆碱",
         targets="M1 拮抗", half_life="5–10 h", cyp="肝代谢",
         note="同上；对迟发性运动障碍无益甚至加重；长期使用有滥用与认知损害报道。"),
    dict(slug="procyclidine", inn="procyclidine", cn="丙环定", cls="中枢抗胆碱",
         targets="M1 拮抗", half_life="≈12 h", cyp="肝代谢",
         note="EPS 与静坐不能的对症用药，原则是短期、最小有效量；过量致谵妄与心律失常。"),
    dict(slug="amantadine", inn="amantadine", cn="金刚烷胺", cls="NMDA 拮抗 / 促多巴胺",
         targets="NMDA 拮抗 + 促进多巴胺释放", half_life="≈15 h", cyp="约 90% 肾原型（需按 CrCl 调量）",
         note="EPS、疲劳与流感样症状的辅助；过量或肾功能不全时致谵妄、幻觉与心律失常。"),
    # --- 止吐与抗组胺（应对药物副作用） ---
    dict(slug="metoclopramide", inn="metoclopramide", cn="甲氧氯普胺", cls="D2 拮抗（促动力）",
         targets="D2 拮抗 + 5-HT4 激动", half_life="5–6 h", cyp="肝结合，肾排泄",
         note="止吐与促动力；长期或高量致 EPS 与迟发性运动障碍——与抗精神病药合用时风险叠加，青少年尤须警惕。"),
    dict(slug="ondansetron", inn="ondansetron", cn="昂丹司琼", cls="5-HT3 拮抗",
         targets="5-HT3 拮抗", half_life="3–6 h", cyp="3A4/2D6/1A2",
         note="化疗、术后与胃肠炎止吐；静脉高量 QTc 延长；与延长 QT 药物叠加时需监测。"),
    dict(slug="promethazine", inn="promethazine", cn="异丙嗪", cls="吩噻嗪类抗组胺",
         targets="H1 强拮抗 + 弱 D2 拮抗", half_life="9–16 h", cyp="肝代谢",
         note="镇静、止吐、抗过敏；抗胆碱与 EPS 可与抗精神病药叠加；2 岁以下禁用（呼吸抑制）。"),
    dict(slug="cyproheptadine", inn="cyproheptadine", cn="赛庚啶", cls="5-HT2A / H1 拮抗",
         targets="5-HT2A 拮抗 + H1 拮抗", half_life="≈8 h", cyp="肝代谢",
         note="5-HT 综合征的辅助用药，仅在医疗指导下使用；食欲与体重增加明显。"),
    # --- 促觉醒与 ADHD（补） ---
    dict(slug="dexmethylphenidate", inn="dexmethylphenidate", cn="右哌甲酯", cls="兴奋剂（d-MPH）",
         targets="DAT/NET 阻断", half_life="2–3 h（缓释 8–12 h）", cyp="CES1 水解",
         note="哌甲酯的右旋活性体，等效剂量约为外消旋的一半；心血管与滥用风险同哌甲酯。"),
    dict(slug="solriamfetol", inn="solriamfetol", cn="索安非托", cls="DAT/NET 抑制（促觉醒）",
         targets="DAT/NET 抑制", half_life="9.5–13.5 h", cyp="肾排泄为主",
         note="发作性睡病与 OSA 相关日间嗜睡；血压与心率升高，心血管病史者慎用。"),
    dict(slug="pitolisant", inn="pitolisant", cn="匹托利生", cls="H3 受体拮抗/反向激动",
         targets="H3 反向激动（增加组胺释放）", half_life="10–12 h", cyp="2D6/3A4",
         note="发作性睡病；与强 2D6 抑制剂合用需减量；QTc 轻度延长。"),
]

# OTC "Drug Facts" labels use a different vocabulary; include it when present.
OTC_SECTIONS: List[Tuple[str, str, int]] = [
    ("active_ingredient", "有效成分（OTC 标签）", 800),
    ("purpose", "用途（OTC 标签）", 600),
    ("do_not_use", "不要使用（OTC 标签）", 1200),
    ("ask_doctor", "使用前咨询医生（OTC 标签）", 1200),
    ("ask_doctor_or_pharmacist", "咨询药师（OTC 标签）", 1200),
    ("when_using", "使用期间（OTC 标签）", 1600),
    ("stop_use", "出现以下情况停止使用并就医（OTC 标签）", 1200),
    ("pregnancy_or_breast_feeding", "孕哺期（OTC 标签）", 800),
    ("keep_out_of_reach_of_children", "儿童防护（OTC 标签）", 400),
]

SECTION_HEADINGS = {k: (t, c) for k, t, c in SECTIONS}
ALL_KEYS = [k for k, _, _ in SECTIONS] + [k for k, _, _ in OTC_SECTIONS]
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def log(msg: str) -> None:
    print(msg, flush=True)


def http_json(url: str, tries: int = 3, timeout: int = 30) -> Optional[Any]:
    """GET JSON with retries. Returns None on 404, raises on repeated hard errors."""
    last: Optional[Exception] = None
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code == 429 or 500 <= exc.code < 600:
                last = exc
                time.sleep(2.0 * attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.5 * attempt)
    if last:
        raise last
    return None


def label_score(label: Dict[str, Any]) -> int:
    """Prefer the richest matching label: more of our target sections, more text."""
    score = 0
    for key in ALL_KEYS:
        value = label.get(key)
        if value:
            raw = " ".join(value) if isinstance(value, list) else str(value)
            score += min(len(raw), 20000)
    return score


def fetch_label(query: str) -> Optional[Dict[str, Any]]:
    """Pick the most complete label among the top matches (brand and generic)."""
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for field in ("openfda.generic_name", "openfda.brand_name"):
        term = urllib.parse.quote('"%s"' % query, safe="")
        url = "%s?search=%s:%s&limit=5" % (OPENFDA_URL, field, term)
        data = http_json(url)
        for label in (data or {}).get("results") or []:
            score = label_score(label)
            if score > best_score:
                best, best_score = label, score
        if best_score > 0:
            return best
    return best


def fetch_pubchem(name: str) -> Optional[Dict[str, Any]]:
    props = "MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,XLogP,HBondDonorCount,HBondAcceptorCount,TPSA"
    url = "%s/compound/name/%s/property/%s/JSON" % (
        PUBCHEM_URL, urllib.parse.quote(name, safe=""), props)
    data = http_json(url, tries=2, timeout=20)
    if not data:
        return None
    table = data.get("PropertyTable", {}).get("Properties") or []
    return table[0] if table else None


def clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def trim(text: str, cap: int) -> str:
    text = clean(text)
    if len(text) <= cap:
        return text
    cut = text[:cap]
    idx = max(cut.rfind(p) for p in (". ", "。", "! ", "? ", "！", "？"))
    if idx > cap * 0.6:
        cut = cut[: idx + 1]
    return cut.rstrip() + " …（节选，完整文本见来源链接）"


def get_sections(label: Dict[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for key, title, cap in SECTIONS + OTC_SECTIONS:
        value = label.get(key)
        if not value:
            continue
        if isinstance(value, list):
            raw = " ".join(str(v) for v in value)
        else:
            raw = str(value)
        body = trim(raw, cap)
        if body:
            out.append((title, body))
    return out


def build_shard(entry: Dict[str, str], label: Optional[Dict[str, Any]],
                chem: Optional[Dict[str, Any]], stamp: str) -> Tuple[str, int]:
    lines: List[str] = []
    lines.append("# %s · %s" % (entry["inn"], entry["cn"]))
    lines.append("")
    lines.append("> 数据来源：OpenFDA Drug Labeling API + PubChem PUG-REST ｜ 拉取时间：%s" % stamp)
    lines.append("> 用途：症状-药物机制核对、副作用溯源、门诊沟通准备。**不得**作为自行调量、停药或超剂量使用的依据。")
    lines.append("")
    lines.append("## 速览")
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("|---|---|")
    lines.append("| 通用名 (INN) | %s |" % entry["inn"])
    lines.append("| 中文名 | %s |" % entry["cn"])
    lines.append("| 类别 / 机制 | %s |" % entry["cls"])
    lines.append("| 关键靶点 | %s |" % entry["targets"])
    lines.append("| 消除半衰期 | %s |" % entry["half_life"])
    lines.append("| CYP450 / 代谢 | %s |" % entry["cyp"])
    lines.append("")
    lines.append("## 数值来源与口径")
    lines.append("")
    lines.append("| 项目 | 来源 | 口径 |")
    lines.append("|---|---|---|")
    lines.append("| 适应症 / 剂量 / 禁忌 / 警告 / 不良反应 / 相互作用 | 本文下方 FDA 标签原样节选 | 美国标签；地区剂型与获批适应症可能不同，需查 NMPA |")
    lines.append("| 消除半衰期 / CYP 通路 | FDA 标签 Clinical Pharmacology、Drug Interactions 章节 | 群体均值，个体差异可达数倍 |")
    lines.append("| Ki（受体亲和力） | 文献近似值（PDSP / BindingDB 类数据集整理） | 仅作量级参考，非本药实测值 |")
    lines.append("| 化学标识 | PubChem PUG-REST | 查询时点快照 |")
    lines.append("")
    lines.append("> 任何数值都不构成剂量依据；调量必须由处方医师决定。")
    lines.append("")
    lines.append("## 精选临床要点（人工精编，非说明书原文）")
    lines.append("")
    lines.append(entry["note"])
    lines.append("")

    if chem:
        lines.append("## 化学标识（PubChem）")
        lines.append("")
        lines.append("| 属性 | 值 |")
        lines.append("|---|---|")
        for label_cn, key in (
            ("PubChem CID", "CID"),
            ("分子式", "MolecularFormula"),
            ("分子量", "MolecularWeight"),
            ("IUPAC 名", "IUPACName"),
            ("Canonical SMILES", "CanonicalSMILES"),
            ("XLogP", "XLogP"),
            ("氢键供体", "HBondDonorCount"),
            ("氢键受体", "HBondAcceptorCount"),
            ("拓扑极性表面积", "TPSA"),
        ):
            if key in chem:
                lines.append("| %s | %s |" % (label_cn, str(chem[key]).replace("|", "/")))
        lines.append("")
        lines.append("SMILES 可用于结构核对与教学演示；不用于任何合成或改造目的。")
        lines.append("")

    if label:
        sections = get_sections(label)
        for title, body in sections:
            lines.append("## %s" % title)
            lines.append("")
            lines.append(body)
            lines.append("")
        if not sections:
            lines.append("## 说明书")
            lines.append("")
            lines.append("（该标签未包含本脚本采集的常规章节。）")
            lines.append("")
    else:
        lines.append("## 说明书")
        lines.append("")
        lines.append("未在 OpenFDA 检索到该通用名的美国药品标签（可能仅在中国/欧盟上市，或为复方/非处方成分）。")
        lines.append("本分片仅含人工精编要点与 PubChem 化学标识；具体说明书请查 NMPA 或当地药监数据库。")
        lines.append("")

    lines.append("## 检索提示")
    lines.append("")
    lines.append("- 需要原始标签全文：https://api.fda.gov/drug/label.json?search=openfda.generic_name:%s" % urllib.parse.quote('"%s"' % entry["inn"], safe=""))
    lines.append("- 需要化学数据：https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/%s/property/MolecularFormula/JSON" % urllib.parse.quote(entry["inn"], safe=""))
    lines.append("- 相互作用与剂量务必以当地说明书与医师判断为准。")
    lines.append("")

    text = "\n".join(lines) + "\n"
    return text, len(text.encode("utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the sharded OpenFDA/PubChem knowledge base.")
    parser.add_argument("--out", default="references", help="output directory (default: references)")
    parser.add_argument("--delay", type=float, default=0.35, help="delay between compounds in seconds")
    parser.add_argument("--only", default="", help="comma-separated slugs to build")
    parser.add_argument("--limit", type=int, default=0, help="build at most N compounds")
    parser.add_argument("--force", action="store_true", help="rebuild shards that already exist")
    parser.add_argument("--no-pubchem", action="store_true", help="skip PubChem lookups")
    parser.add_argument("--min-bytes", type=int, default=1_500_000, help="warn below this total size")
    parser.add_argument("--check", action="store_true", help="only verify existing output size")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    out_dir = Path(args.out).resolve()
    drug_dir = out_dir / "openfda-drugs"
    index_path = out_dir / "kb-index.json"
    drug_dir.mkdir(parents=True, exist_ok=True)

    if args.check:
        total = sum(p.stat().st_size for p in drug_dir.glob("*.md"))
        log("existing shards: %d, total %.2f MB" % (len(list(drug_dir.glob("*.md"))), total / 1_048_576))
        if not index_path.exists():
            log("missing kb-index.json")
        return 0 if total >= args.min_bytes else 2

    selected = [d for d in REGISTRY if not args.only or d["slug"] in {s.strip() for s in args.only.split(",") if s.strip()}]
    if args.limit:
        selected = selected[: args.limit]

    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    index: List[Dict[str, Any]] = []
    failures: List[str] = []
    total_bytes = 0
    started = time.time()

    for i, entry in enumerate(selected, 1):
        slug = entry["slug"]
        target = drug_dir / ("%s.md" % slug)
        status = "ok"
        label = None
        chem = None

        if target.exists() and not args.force:
            text = target.read_text(encoding="utf-8")
            total_bytes += len(text.encode("utf-8"))
            status = "cached"
        else:
            try:
                label = fetch_label(entry.get("query") or entry["inn"])
            except Exception as exc:  # network / API failure is non-fatal per compound
                log("  ! OpenFDA failed for %s: %s" % (slug, exc))
                label = None
            if not args.no_pubchem:
                try:
                    chem = fetch_pubchem(entry["inn"])
                except Exception as exc:
                    log("  ! PubChem failed for %s: %s" % (slug, exc))
                    chem = None
            text, size = build_shard(entry, label, chem, stamp)
            target.write_text(text, encoding="utf-8", newline="\n")
            total_bytes += size
            if not label:
                status = "pubchem-only"

        index.append({
            "slug": slug,
            "inn": entry["inn"],
            "cn": entry["cn"],
            "class": entry["cls"],
            "half_life": entry["half_life"],
            "file": "openfda-drugs/%s.md" % slug,
            "bytes": target.stat().st_size,
            "status": status,
            "sources": ["openfda:label", "pubchem:property", "literature:ki-approx"],
        })
        if status == "pubchem-only":
            failures.append(slug)
        log("[%2d/%2d] %-22s %7d B  %s" % (i, len(selected), slug, target.stat().st_size, status))
        if i < len(selected):
            time.sleep(max(args.delay, 0.0))

    index.sort(key=lambda row: row["slug"])
    index_path.write_text(json.dumps({
        "generated_at": stamp,
        "count": len(index),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1_048_576, 2),
        "source": ["https://api.fda.gov/drug/label.json", "https://pubchem.ncbi.nlm.nih.gov/rest/pug"],
        "usage": "按 slug / 中文名 / 类别检索，只读命中分片；不要一次性读入全部文件。",
        "drugs": index,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    elapsed = time.time() - started
    log("")
    log("done in %.1fs: %d shards, %.2f MB" % (elapsed, len(index), total_bytes / 1_048_576))
    if failures:
        log("no US label (shard built from PubChem + curated notes): %s" % ", ".join(failures))
    if total_bytes < args.min_bytes:
        log("WARNING: total %.2f MB is below --min-bytes %.2f MB" % (total_bytes / 1_048_576, args.min_bytes / 1_048_576))
        return 2
    log("index: %s" % index_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("interrupted")
        raise SystemExit(130)

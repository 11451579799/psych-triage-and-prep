# agomelatine · 阿戈美拉汀

> 数据来源：OpenFDA Drug Labeling API + PubChem PUG-REST ｜ 拉取时间：2026-11-22T12:11:05+08:00
> 用途：症状-药物机制核对、副作用溯源、门诊沟通准备。**不得**作为自行调量、停药或超剂量使用的依据。

## 速览

| 项 | 值 |
|---|---|
| 通用名 (INN) | agomelatine |
| 中文名 | 阿戈美拉汀 |
| 类别 / 机制 | MT1/MT2 激动 + 5-HT2C 拮抗 |
| 关键靶点 | 褪黑素受体 |
| 消除半衰期 | 1–2 h |
| CYP450 / 代谢 | 1A2（强抑者禁用） |

## 数值来源与口径

| 项目 | 来源 | 口径 |
|---|---|---|
| 适应症 / 剂量 / 禁忌 / 警告 / 不良反应 / 相互作用 | 本文下方 FDA 标签原样节选 | 美国标签；地区剂型与获批适应症可能不同，需查 NMPA |
| 消除半衰期 / CYP 通路 | FDA 标签 Clinical Pharmacology、Drug Interactions 章节 | 群体均值，个体差异可达数倍 |
| Ki（受体亲和力） | 文献近似值（PDSP / BindingDB 类数据集整理） | 仅作量级参考，非本药实测值 |
| 化学标识 | PubChem PUG-REST | 查询时点快照 |

> 任何数值都不构成剂量依据；调量必须由处方医师决定。

## 精选临床要点（人工精编，非说明书原文）

需监测肝功；对睡眠节律紊乱型抑郁有优势。

## 化学标识（PubChem）

| 属性 | 值 |
|---|---|
| PubChem CID | 82148 |
| 分子式 | C15H17NO2 |
| 分子量 | 243.30 |
| IUPAC 名 | N-[2-(7-methoxynaphthalen-1-yl)ethyl]acetamide |
| XLogP | 2.7 |
| 氢键供体 | 1 |
| 氢键受体 | 2 |
| 拓扑极性表面积 | 38.3 |

SMILES 可用于结构核对与教学演示；不用于任何合成或改造目的。

## 说明书

未在 OpenFDA 检索到该通用名的美国药品标签（可能仅在中国/欧盟上市，或为复方/非处方成分）。
本分片仅含人工精编要点与 PubChem 化学标识；具体说明书请查 NMPA 或当地药监数据库。

## 检索提示

- 需要原始标签全文：https://api.fda.gov/drug/label.json?search=openfda.generic_name:%22agomelatine%22
- 需要化学数据：https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/agomelatine/property/MolecularFormula/JSON
- 相互作用与剂量务必以当地说明书与医师判断为准。


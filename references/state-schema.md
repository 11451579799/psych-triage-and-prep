# PatientIntakeState（跨轮次状态对象）

> 状态是这份技能唯一的「记忆」。每轮结束更新一次；会话结束时可让用户复制保存，下次粘贴回来即恢复。

## 6. PatientIntakeState（跨轮次状态对象）

各框架可用任意方式持久化（会话变量 / 临时 JSON / 内存对象），字段保持一致即可：

    {
      "meta": { "started_at": "", "round": 1, "risk": "green|yellow|red", "locale": "zh-CN" },
      "stage": "first_visit|follow_up|titration|taper|pre_med_research",
      "top_complaints": ["", ""],
      "safety": { "si_ideation": "none|passive|frequent|plan", "self_harm": false, "vitals": "", "notes": "" },
      "phenomenology": {
        "mood": { "anhedonia_anticipatory": null, "anhedonia_consummatory": null, "avolition": null, "blunting": null },
        "sensory": { "hyperacusis": null, "photophobia": null, "visual_snow": null, "paresthesia": [], "pain_quality": [] },
        "autonomic": [], "cognitive": { "brain_fog": null, "memory": null },
        "consciousness": "clear|speech_block|dissociation|blackout|unknown"
      },
      "course": { "duration": "", "rhythm": "", "sleep": { "onset": null, "maintenance": null, "early": null, "hours": null }, "cyclic_windows": null, "hypomanic_screen": "no|possible|yes|unknown" },
      "function_anchors": { "wash": [0,0,0], "leave_home": [0,0,0], "read": [0,0,0], "leisure": [0,0,0], "talk": [0,0,0] },
      "meds": [ { "name": "", "cn": "", "brand": "", "mg": null, "per_dose": null, "form": "IR|ER|XR|CR|ODT|EC|OROS|patch|spray|liquid|unknown",
                  "times": [], "since": "", "last_change": "", "prn_extra": "", "broken": false, "with_food": null,
                  "confirmed": true, "source": "box|prescription|record|recall|inferred",
                  "adherence": { "missed_per_week": "", "extra_dose_per_week": "", "double_dose": null, "managed_by": "self|family|pillbox|unknown" },
                  "notes": "" } ],
      "med_history": [ { "name": "", "dose": "", "duration": "", "effect": null, "stopped_why": "", "taper": "abrupt|gradual|unknown" } ],
      "exposures": { "caffeine": "", "tobacco": "", "alcohol": "", "grapefruit": false, "otc": [], "supplements": [] },
      "labs": { "done": [], "missing": [], "notes": "" },
      "psychosocial": { "stressors": [], "support": "", "can_bring_someone": null },
      "kb_refs": []
    }

**写入纪律**：只写用户说过的；推测值必须带 inferred: true；不得为了「报告好看」补全字段。

---

## JSON Schema（机器校验用）

用于校验会话结束时的状态转储是否完整、类型是否正确。只校验结构，不校验临床合理性。

    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "title": "PatientIntakeState",
      "type": "object",
      "required": ["meta", "stage", "top_complaints", "safety"],
      "properties": {
        "meta": {
          "type": "object",
          "required": ["round", "risk"],
          "properties": {
            "started_at": { "type": "string" },
            "round": { "type": "integer", "minimum": 1, "maximum": 8 },
            "risk": { "enum": ["green", "yellow", "red"] },
            "locale": { "type": "string" }
          }
        },
        "stage": { "enum": ["first_visit", "follow_up", "titration", "taper", "pre_med_research", "unknown"] },
        "top_complaints": { "type": "array", "maxItems": 3, "items": { "type": "string" } },
        "safety": {
          "type": "object",
          "required": ["si_ideation"],
          "properties": {
            "si_ideation": { "enum": ["none", "passive", "frequent", "plan", "unknown"] },
            "self_harm": { "type": "boolean" },
            "vitals": { "type": "string" },
            "notes": { "type": "string" }
          }
        },
        "phenomenology": {
          "type": "object",
          "properties": {
            "mood": {
              "type": "object",
              "properties": {
                "anhedonia_anticipatory": { "type": ["boolean", "null"] },
                "anhedonia_consummatory": { "type": ["boolean", "null"] },
                "avolition": { "type": ["boolean", "null"] },
                "blunting": { "type": ["boolean", "null"] }
              }
            },
            "sensory": {
              "type": "object",
              "properties": {
                "hyperacusis": { "type": ["boolean", "null"] },
                "photophobia": { "type": ["boolean", "null"] },
                "visual_snow": { "type": ["boolean", "null"] },
                "paresthesia": { "type": "array", "items": { "type": "string" } },
                "pain_quality": { "type": "array", "items": { "type": "string" } }
              }
            },
            "autonomic": { "type": "array", "items": { "type": "string" } },
            "cognitive": {
              "type": "object",
              "properties": {
                "brain_fog": { "type": ["boolean", "null"] },
                "memory": { "type": ["string", "null"] }
              }
            },
            "consciousness": { "enum": ["clear", "speech_block", "dissociation", "blackout", "unknown"] }
          }
        },
        "course": {
          "type": "object",
          "properties": {
            "duration": { "type": "string" },
            "rhythm": { "type": "string" },
            "sleep": {
              "type": "object",
              "properties": {
                "onset": { "type": ["integer", "null"], "minimum": 0, "maximum": 10 },
                "maintenance": { "type": ["integer", "null"], "minimum": 0, "maximum": 10 },
                "early": { "type": ["integer", "null"], "minimum": 0, "maximum": 10 },
                "hours": { "type": ["number", "null"], "minimum": 0, "maximum": 24 }
              }
            },
            "cyclic_windows": { "type": ["string", "null"] },
            "hypomanic_screen": { "enum": ["no", "possible", "yes", "unknown"] }
          }
        },
        "function_anchors": {
          "type": "object",
          "additionalProperties": { "type": "array", "items": { "type": "integer", "minimum": 0, "maximum": 10 } }
        },
        "meds": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name"],
            "properties": {
              "name": { "type": "string" },
              "cn": { "type": "string" },
              "mg": { "type": ["number", "null"] },
              "form": { "enum": ["IR", "ER", "XR", "CR", "ODT", "EC", "OROS", "patch", "spray", "liquid", "unknown"] },
              "times": { "type": "array", "items": { "type": "string" } },
              "since": { "type": "string" },
              "prn_extra": { "type": "string" },
              "broken": { "type": "boolean" },
              "with_food": { "type": ["boolean", "null"] },
              "inferred": { "type": "boolean" },
              "brand": { "type": "string" },
              "per_dose": { "type": ["number", "null"] },
              "last_change": { "type": "string" },
              "confirmed": { "type": "boolean" },
              "source": { "enum": ["box", "prescription", "record", "recall", "inferred", "unknown"] },
              "adherence": {
                "type": "object",
                "properties": {
                  "missed_per_week": { "type": "string" },
                  "extra_dose_per_week": { "type": "string" },
                  "double_dose": { "type": ["boolean", "null"] },
                  "managed_by": { "enum": ["self", "family", "pillbox", "unknown"] }
                }
              },
              "notes": { "type": "string" }
            }
          }
        },
        "med_history": { "type": "array", "items": { "type": "object", "properties": {
          "name": { "type": "string" }, "dose": { "type": "string" }, "duration": { "type": "string" },
          "effect": { "type": ["integer", "null"], "minimum": 0, "maximum": 10 },
          "stopped_why": { "type": "string" }, "taper": { "enum": ["abrupt", "gradual", "unknown"] } } } },
        "exposures": { "type": "object", "properties": {
          "caffeine": { "type": "string" }, "tobacco": { "type": "string" }, "alcohol": { "type": "string" },
          "grapefruit": { "type": "boolean" },
          "otc": { "type": "array", "items": { "type": "string" } },
          "supplements": { "type": "array", "items": { "type": "string" } } } },
        "labs": { "type": "object", "properties": {
          "done": { "type": "array", "items": { "type": "string" } },
          "missing": { "type": "array", "items": { "type": "string" } },
          "notes": { "type": "string" } } },
        "psychosocial": { "type": "object", "properties": {
          "stressors": { "type": "array", "items": { "type": "string" } },
          "support": { "type": "string" },
          "can_bring_someone": { "type": ["boolean", "null"] } } },
        "kb_refs": { "type": "array", "items": { "type": "string" } }
      }
    }

## 写入与校验纪律

1. 只写用户说过的；推测值加 inferred 标记，不得为了「报告好看」补字段。
2. 枚举值只能取 schema 列出的值；拿不准用 unknown，不要自造。
3. 生成报告前跑一遍结构校验（任何 JSON Schema 校验器即可）；失败就补 unknown，不要删字段。
4. 状态里不写真实姓名、手机号、住址、单位；需要指代时用「用户」「伴侣」等角色词。

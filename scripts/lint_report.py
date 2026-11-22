#!/usr/bin/env python3
"""单文件报告 HTML 合规检查器（Round 8 交付前自检）。

用法: python scripts/lint_report.py <report.html> [--json]
退出码：0 只有 WARN；1 至少一个 ERROR；2 参数错误或文件读不了。

检查项（来源 references/frontend-ui-architecture.md 第三、四、五节与 SKILL.md
第 6 节；E4、E7-E10 为启发式 WARN）::

    E1  ERROR  src/href 出现 http(s)://；rel="noopener" 纯文本链接降 WARN
    E2  ERROR  <script src=>、<link rel=stylesheet>、@import、url(http
    E3  ERROR  alert( / confirm( / prompt( / autoplay
    E4  WARN   双语、主题、A+ 字号、静止护眼四项顶栏控制
    E5  ERROR  img 缺 alt、按钮无名称、html 缺 lang、缺 viewport（outline:none 无替代降 WARN）
    E6  ERROR  缺 @media print
    E7  WARN   纯黑/纯白精确色值、font-size < 14px（打印区块内豁免）
    E8  WARN   有 animation/transition 但无 prefers-reduced-motion
    E9  WARN   文件 > 2 MB
    E10 WARN   「推测」附近 200 字符内无 来源/说明书/文献/假设

实现：只用标准库，纯正则 + 简单状态机，不解析 DOM；行号用 text.splitlines() 的 1-based 索引（行首偏移 + bisect）。启发式宁漏勿误。
"""

import bisect
import json
import re
import sys
from pathlib import Path

USAGE = "用法: python scripts/lint_report.py <report.html> [--json]"
MAX_BYTES = 2 * 1024 * 1024

# --- 正则表：按检查项分组维护，规范改版时逐条对照 -------------------------
URL_ATTR_RE = re.compile(
    r"""\b(?:src|href)\s*=\s*(?:"(https?://[^"]*)"|'(https?://[^']*)'|(https?://[^\s>]+))""", re.I)
REL_RE = re.compile(r"""\brel\s*=\s*["'][^"']*\bnoopener\b""", re.I)
RESOURCE_RE = (
    (re.compile(r"<script\b[^>]*\bsrc\s*=", re.I), "外部脚本 <script src=>，应内联"),
    (re.compile(r"""<link\b[^>]*\brel\s*=\s*["'][^"']*stylesheet""", re.I), "外部样式 <link rel=stylesheet>"),
    (re.compile(r"@import\b", re.I), "@import 引入外部样式"),
    (re.compile(r"""url\(\s*["']?https?:""", re.I), "CSS url(http...) 发起外部请求"))
BLOCKED_RE = re.compile(r"\b(alert|confirm|prompt)\s*\(", re.I)
AUTOPLAY_RE = re.compile(r"\bautoplay\b", re.I)
CONTROL_RE = (
    ("双语切换（医生版/患者版）", re.compile(
        r"""(?:id|data-layer)\s*=\s*["'][^"']*(?:医生|患者|doctor|patient)|>\s*(?:医生版|患者版)\s*<""", re.I)),
    ("主题切换（data-theme）", re.compile(r"data-theme\s*=", re.I)),
    ("A+ 大字号（font-large 或「字号」）", re.compile(r"font-large|字号", re.I)),
    ("静止护眼（data-motion 或「护眼」）", re.compile(r"data-motion|护眼", re.I)))
HTML_RE = re.compile(r"<html\b[^>]*>", re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
BUTTON_RE = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.I | re.S)
VIEWPORT_RE = re.compile(r"""<meta\b[^>]*\bname\s*=\s*["']viewport["']""", re.I)
ALT_RE = re.compile(r"\balt\s*=", re.I)
ARIA_RE = re.compile(r"\b(?:aria-label|aria-labelledby|title)\s*=", re.I)
OUTLINE_NONE_RE = re.compile(r"outline\s*:\s*(?:none|0)\b", re.I)
FOCUS_OUTLINE_RE = re.compile(r":focus(?:-visible)?[^{}]*\{[^{}]*outline\s*:", re.I)
PRINT_RE = re.compile(r"@media\s+print\b", re.I)
PURE_COLOR_RE = re.compile(r"#(?:000000|000|ffffff|fff)\b", re.I)
FONT_PX_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
MOTION_RE = re.compile(r"\b(?:animation|transition)\s*:", re.I)
REDUCED_MOTION_RE = re.compile(r"prefers-reduced-motion", re.I)
GUESS_RE = re.compile("推测")
SOURCE_WORDS = ("来源", "说明书", "文献", "假设")

# --- 文档模型：原文 / 去注释副本 / 行号索引 / @media print 区块 ------------
class Document:
    """把报告读成可定位的结构，所有检查共用，避免重复扫描。"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.splitlines()
        self.masked = _mask_comments(text)
        self.starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]
        self.print_spans = _print_spans(text)

    def line_of(self, offset: int) -> int:
        """字符偏移 -> 1-based 行号。"""
        return bisect.bisect_right(self.starts, offset)

    def in_print(self, offset: int) -> bool:
        return any(start <= offset < end for start, end in self.print_spans)

def _mask_comments(text: str) -> str:
    """把 <!-- ... --> 换成等长空格：注释里的示例不参与检查，行号不变。"""
    chars = list(text)
    cursor = 0
    while (start := text.find("<!--", cursor)) >= 0:
        end = text.find("-->", start + 4)
        end = len(text) if end < 0 else end + 3
        chars[start:end] = [ch if ch in "\r\n" else " " for ch in chars[start:end]]
        cursor = end
    return "".join(chars)

def _print_spans(text: str) -> list[tuple[int, int]]:
    """返回 @media print { ... } 区间；花括号配平用简单状态机。"""
    spans = []
    for match in PRINT_RE.finditer(text):
        brace = text.find("{", match.end())
        if brace < 0:
            continue
        depth, index = 0, brace
        while index < len(text):
            depth += text[index] == "{"
            depth -= text[index] == "}"
            if depth == 0:
                spans.append((match.start(), index + 1))
                break
            index += 1
    return spans

# --- 小工具 ---------------------------------------------------------------
def _finding(rule: str, level: str, line: int, message: str, evidence: str = "") -> dict:
    return {"rule": rule, "level": level, "line": line, "message": message, "evidence": evidence}

def _hit(out: list, rule: str, level: str, doc: Document, offset: int,
         message: str, evidence: str = "") -> None:
    out.append(_finding(rule, level, doc.line_of(offset), message, evidence or _snippet(doc.text, offset)))

def _snippet(text: str, offset: int, width: int = 70) -> str:
    return re.sub(r"\s+", " ", text[max(0, offset - 20): offset + width]).strip()

def _tag_context(masked: str, offset: int) -> tuple[str, str]:
    """找到命中位置所在的标签，返回 (标签名, 标签原文)。"""
    start = masked.rfind("<", 0, offset)
    if start < 0:
        return "", ""
    end = masked.find(">", offset)
    tag = masked[start: (len(masked) - 1 if end < 0 else end) + 1]
    name = re.match(r"<\s*([A-Za-z][\w:-]*)", tag)
    return (name.group(1).lower() if name else ""), tag

# --- E1 / E2：单文件与外链 -------------------------------------------------
def check_urls(doc: Document) -> list[dict]:
    out: list[dict] = []
    spans: list[tuple[int, int]] = []
    for match in URL_ATTR_RE.finditer(doc.masked):
        url = next(group for group in match.groups() if group)
        name, tag = _tag_context(doc.masked, match.start())
        spans.append((match.start(), match.end()))
        level, message = ("WARN", "外链文本链接（断网打开会失效）") if name == "a" and REL_RE.search(tag) \
            else ("ERROR", f"<{name or '?'}> 引用外部地址，报告必须单文件")
        _hit(out, "E1", level, doc, match.start(), message, url)
    for pattern, message in RESOURCE_RE:
        for match in pattern.finditer(doc.masked):
            if not any(start <= match.start() < end for start, end in spans):
                _hit(out, "E2", "ERROR", doc, match.start(), message)
    return out

# --- E3：禁用 API ----------------------------------------------------------
def check_blocked_apis(doc: Document) -> list[dict]:
    out: list[dict] = []
    for pattern, template in ((BLOCKED_RE, "禁用 API {0}()（阻断、不可样式化）"),
                              (AUTOPLAY_RE, "禁用自动播放：音视频必须用户主动点播放")):
        for match in pattern.finditer(doc.masked):
            message = template.format(match.group(1)) if match.groups() else template
            _hit(out, "E3", "ERROR", doc, match.start(), message)
    return out

# --- E4：四项顶栏控制（启发式，缺则 WARN）----------------------------------
def check_controls(doc: Document) -> list[dict]:
    return [_finding("E4", "WARN", 1, f"未发现{label}", "") for label, pattern in CONTROL_RE if not pattern.search(doc.masked)]

# --- E5：无障碍 ------------------------------------------------------------
def check_a11y(doc: Document) -> list[dict]:
    out: list[dict] = []
    html = HTML_RE.search(doc.masked)
    if not html:
        out.append(_finding("E5", "ERROR", 1, "缺少 <html> 根元素", ""))
    elif not re.search(r"\blang\s*=", html.group(0), re.I):
        _hit(out, "E5", "ERROR", doc, html.start(), "<html> 缺少 lang 属性", html.group(0))
    if not VIEWPORT_RE.search(doc.masked):
        out.append(_finding("E5", "ERROR", 1, '缺少 <meta name="viewport">，手机上会被缩放', ""))
    for match in IMG_RE.finditer(doc.masked):
        if not ALT_RE.search(match.group(0)):
            _hit(out, "E5", "ERROR", doc, match.start(), "<img> 缺少 alt", match.group(0))
    for match in BUTTON_RE.finditer(doc.masked):
        text = re.sub(r"<[^>]*>|&[#A-Za-z0-9]+;", "", match.group(2)).strip()
        if not text and not ARIA_RE.search(match.group(1)):
            _hit(out, "E5", "ERROR", doc, match.start(), "按钮没有可读文字，也没有 aria-label/title")
    outline = OUTLINE_NONE_RE.search(doc.masked)
    if outline and not FOCUS_OUTLINE_RE.search(doc.masked):
        _hit(out, "E5", "WARN", doc, outline.start(),
             "outline:none 且未找到 :focus/:focus-visible 描边替代（启发式）")
    return out

# --- E6-E9：打印 / 配色 / 动效 / 体积 --------------------------------------
def check_style(doc: Document, size: int) -> list[dict]:
    out: list[dict] = []
    if not PRINT_RE.search(doc.masked):
        out.append(_finding("E6", "ERROR", 1, "缺少 @media print，打印/PDF 交接会排版失控", ""))
    seen: set[tuple[int, str]] = set()
    for match in PURE_COLOR_RE.finditer(doc.masked):
        key = (doc.line_of(match.start()), match.group(0).lower())
        if not doc.in_print(match.start()) and key not in seen:
            seen.add(key)
            _hit(out, "E7", "WARN", doc, match.start(),
                 f"纯黑/纯白精确色值 {match.group(0)}，规范要求墨纸/棉纸色")
    for match in FONT_PX_RE.finditer(doc.masked):
        if not doc.in_print(match.start()) and float(match.group(1)) < 14:
            _hit(out, "E7", "WARN", doc, match.start(),
                 f"font-size {match.group(1)}px < 14px，脑雾/视疲劳患者阅读吃力")
    motion = MOTION_RE.search(doc.masked)
    if motion and not REDUCED_MOTION_RE.search(doc.masked):
        _hit(out, "E8", "WARN", doc, motion.start(), "有 animation/transition 但没有 prefers-reduced-motion 兜底")
    if size > MAX_BYTES:
        out.append(_finding("E9", "WARN", 1, f"文件 {size / 1048576:.1f} MB > 2 MB，弱设备打开会卡", ""))
    return out

# --- E10：数据诚实 ---------------------------------------------------------
def check_honesty(doc: Document) -> list[dict]:
    out: list[dict] = []
    seen_lines: set[int] = set()
    for match in GUESS_RE.finditer(doc.masked):
        line = doc.line_of(match.start())
        window = doc.masked[max(0, match.start() - 200): match.start() + 200]
        if line not in seen_lines and not any(word in window for word in SOURCE_WORDS):
            seen_lines.add(line)
            _hit(out, "E10", "WARN", doc, match.start(),
                 "出现「推测」，同段 200 字符内没有 来源/说明书/文献/假设 标注")
    return out

# --- 汇总与输出 ------------------------------------------------------------
def lint(path: Path) -> tuple[Document, list[dict], list[dict], int]:
    raw = path.read_bytes()
    doc = Document(raw.decode("utf-8", errors="replace"))
    findings = (check_urls(doc) + check_blocked_apis(doc) + check_controls(doc)
                + check_a11y(doc) + check_style(doc, len(raw)) + check_honesty(doc))
    unique = {(f["rule"], f["line"], f["message"], f["evidence"]): f for f in findings}
    ordered = sorted(unique.values(), key=lambda f: (f["line"], f["rule"]))
    errors = [f for f in ordered if f["level"] == "ERROR"]
    warns = [f for f in ordered if f["level"] == "WARN"]
    return doc, errors, warns, len(raw)

def print_human(name: str, doc: Document, errors: list[dict], warns: list[dict], size: int) -> None:
    print(f"报告合规检查：{name}（{size / 1024:.1f} KB，{len(doc.lines)} 行）；{len(errors)} 个 ERROR，{len(warns)} 个 WARN；检查项 E1-E10")
    for title, items in (("ERROR", errors), ("WARN", warns)):
        if not items:
            continue
        print(f"\n[{title}] " + ("必须修复" if title == "ERROR" else "建议修复"))
        for item in items:
            print(f"  第 {item['line']} 行 {item['rule']}：{item['message']}")
            if item["evidence"]:
                print(f"      样例 {item['evidence']}")
    print("\n结论：" + ("未通过，先修 ERROR 再交付" if errors else "可交付，WARN 请人工复核"))

def main(argv: list[str]) -> int:
    positional, json_mode = [], False
    for arg in argv:
        if arg == "--json":
            json_mode = True
        elif arg in ("-h", "--help"):
            print(USAGE)
            return 0
        elif arg.startswith("-"):
            print(f"未知参数：{arg}\n{USAGE}", file=sys.stderr)
            return 2
        else:
            positional.append(arg)
    if len(positional) != 1:
        print(USAGE, file=sys.stderr); return 2
    path = Path(positional[0])
    if not path.is_file():
        print(f"找不到文件：{path}", file=sys.stderr); return 2
    try:
        doc, errors, warns, size = lint(path)
    except OSError as exc:
        print(f"读取失败：{exc}", file=sys.stderr); return 2
    if json_mode:
        summary = {"file": str(path), "bytes": size, "lines": len(doc.lines), "error_count": len(errors),
                   "warn_count": len(warns), "status": "fail" if errors else "pass",
                   "checked_rules": [f"E{i}" for i in range(1, 11)]}
        print(json.dumps({"errors": errors, "warns": warns, "summary": summary},
                         ensure_ascii=False, indent=2))
    else:
        print_human(path.name, doc, errors, warns, size)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

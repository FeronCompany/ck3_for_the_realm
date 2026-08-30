#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
For The Realm (朝野纷争) —— P 语言语法快速校验脚本

功能：
  1. 编码校验：.txt / .yml 必须为 UTF-8 with BOM
  2. 括号配对：{} 配对（跳过字符串 "..." 与行注释 # ... 内的花括号）
  3. 本地化格式：.yml 语言头(l_english/l_simp_chinese)、key:0 "value" 键值
  4. 缩进规范：common/*.txt 用 Tab；localization/*.yml 用空格
  5. 命名规范：新增对象须带 ftr_ 前缀（启发式，仅提示）
  6. 覆盖标记：覆盖原版对象处须有 ###### OVERRIDE ######（启发式，仅提示）
  7. 事件文件须声明 namespace
  8. 决议须写 ai_check_interval 或 ai_goal
  9. 双语本地化键名一致性（english 与 simp_chinese 成对）

用法：
    python tools/validate_scripts.py                 # 校验整个 mod
    python tools/validate_scripts.py common/events   # 校验指定目录/文件
    python tools/validate_scripts.py --fix-bom       # 自动为缺失 BOM 的文件补上 BOM

退出码：0 = 通过，1 = 有错误（Error 级），2 = 仅有警告（Warning 级）
"""

import os
import re
import sys
import argparse

# 强制 stdout/stderr 用 UTF-8，避免 Windows 控制台 GBK 乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 项目根目录（本脚本位于 <根>/tools/validate_scripts.py）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 需要 BOM 的文件扩展名
BOM_REQUIRED_EXT = {".txt", ".yml"}

# 应使用 Tab 缩进的脚本目录（common 下的 .txt）
# 应使用空格缩进的本地化 .yml
TXT_EXT = {".txt"}

# 覆盖标记（必须出现的注释）
OVERRIDE_BLOCK_MARK = "###### OVERRIDE ######"
OVERRIDE_LINE_MARK = "### OVERRIDE"

# 事件文件 namespace 声明
NS_RE = re.compile(r"^\s*namespace\s*=\s*([\w]+)\s*$")

# 对象定义行：`some_id = {`（顶格或缩进）
#   排除：脚本效果/触发器调用 `xxx = { PARAM = 1 }`、块内普通键值
#   用于覆盖标记启发式时只取"看起来像顶层对象定义"的行
TOP_OBJ_RE = re.compile(r"^(?P<indent>\t*)(?P<name>[\w.]+)\s*=\s*\{\s*$")

# 允许不加 ftr_ 前缀的顶层对象（原版系统专用块 / 定义键）
ALLOW_NO_PREFIX_KEYS = {
    "namespace", "l_english", "l_simp_chinese", "header",
}

# 本地化键格式：`key:0 "text"` 或 ` key:0 "text"`
LOC_KEY_RE = re.compile(r"^\s*([\w_.\-\u4e00-\u9fff]+):(\d+)\s+\"(.*)\"\s*$")
LOC_LANG_RE = re.compile(r"^l_([a-z_]+):\s*$")

# ---- 结果收集 ----
errors = []      # 错误（建议修复，通常是加载会失败的硬伤）
warnings = []    # 警告（规范性问题）


def err(file, line, msg):
    errors.append(f"{rel(file)}:{line}  [错误] {msg}")


def warn(file, line, msg):
    warnings.append(f"{rel(file)}:{line}  [警告] {msg}")


def rel(p):
    return os.path.relpath(p, ROOT)


# ---------- 1. 编码 / BOM ----------
def check_bom(path):
    """校验文件头是否为 EF BB BF。"""
    try:
        with open(path, "rb") as f:
            head = f.read(3)
    except OSError as e:
        err(path, 1, f"无法读取文件: {e}")
        return False
    if head == b"\xef\xbb\xbf":
        return True
    err(path, 1, "缺少 UTF-8 BOM（应包含 EF BB BF 头）。中文会乱码、本地化不加载。")
    return False


def fix_bom(path):
    """为缺失 BOM 的文件补上 BOM。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        err(path, 1, f"无法读取文件: {e}")
        return
    if data[:3] == b"\xef\xbb\xbf":
        return  # 已有
    with open(path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(data)
    # 修复后重新校验编码
    warnings.append(f"{rel(path)}:1  [已自动补 BOM]")


# ---------- 2. 括号配对 ----------
def check_braces(path, text):
    """检查 {} 配对。跳过字符串 "..." 与 # 注释。"""
    # 预处理：去除行注释（# 到行尾），但要保留字符串内部的 # 不受影响。
    lines = text.splitlines()
    stack = []  # 存 (行号, 括号类型)
    for i, raw in enumerate(lines, start=1):
        line = raw
        # 去除行内注释：找到未被引号包围的 #
        in_str = False
        cleaned = []
        j = 0
        while j < len(line):
            ch = line[j]
            if in_str:
                cleaned.append(ch)
                if ch == "\\":
                    cleaned.append(line[j + 1]) if j + 1 < len(line) else None
                    j += 2
                    continue
                if ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                    cleaned.append(ch)
                elif ch == "#":
                    break  # 注释，截断
                else:
                    cleaned.append(ch)
            j += 1
        line = "".join(cleaned)

        for ch in line:
            if ch == "{":
                stack.append((i, "{"))
            elif ch == "}":
                if not stack:
                    err(path, i, "多余的右花括号 }")
                    continue
                stack.pop()
    for ln, brace in stack:
        err(path, ln, f"未闭合的 {{（缺少对应 }}）")


# ---------- 3. 本地化格式 ----------
def check_localization(path, text):
    lines = text.splitlines()
    lang_header_found = False
    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if LOC_LANG_RE.match(line):
            lang_header_found = True
            continue
        # 键值行
        m = LOC_KEY_RE.match(raw)
        if m:
            key, _idx, val = m.groups()
            # 检查左引号开头的翻译是否配对（跳过转义）
            # 这里已通过正则捕获，基本格式正确
            continue
        # 非注释、非键值、非语言头 → 格式可疑
        # 可能是空行或括号，不做过度报错
        if line in ("{", "}", "} {"):
            continue
        # 否则提示（本地化通常每行一个键值）
        # 仅当看起来像"key: idx"却缺引号时报警
        if re.match(r"^\s*[\w_.\-\u4e00-\u9fff]+:\d+\s+[^\"]", raw):
            err(path, i, f"本地化键值缺少双引号包裹: {line}")
        elif ":" in line and '"' not in line and not line.startswith("("):
            # 可能是遗漏格式，给警告
            pass
    if not lang_header_found:
        err(path, 1, "本地化文件缺少语言头（l_english: / l_simp_chinese:）")


# ---------- 4. 缩进规范 ----------
# 这些目录有原版特定格式，跳过缩进规范检查
INDENT_SKIP_DIRS = {"dna_data"}


def check_indent(path, text, is_txt):
    if any(f"/{d}/" in path.replace("\\", "/") for d in INDENT_SKIP_DIRS):
        return
    lines = text.splitlines()
    for i, raw in enumerate(lines, start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lead = raw[: len(raw) - len(raw.lstrip())]
        if is_txt:
            # common 脚本用 Tab；缩进不能出现空格
            if " " in lead:
                warn(path, i, "脚本文件缩进使用了空格（应使用 Tab）")
        else:
            # 本地化 .yml 用空格（1 空格缩进）；出现 Tab 则警告
            if "\t" in lead:
                warn(path, i, "本地化文件缩进使用了 Tab（应使用空格）")


# ---------- 5/6. 命名规范 & 覆盖标记（启发式） ----------
# 这些目录的顶层键名有原版约定，不做 ftr_ 前缀强制检查
NAMING_SKIP_DIRS = {
    "defines",                      # 大写常量块，如 NCharacterOpinion
    "customizable_localization",    # 键名与 custom loc 块名对应
    "trigger_localization",         # 键名须与 trigger 名一致
    "effect_localization",          # 键名须与 effect 名一致
    "dna_data", "dynasties", "dynasty_houses", "culture", "lifestyle_perks",
}


def check_naming_and_override(path, text):
    """对 common 脚本做启发式检查：顶层对象是否 ftr_ 前缀，覆盖块是否有 OVERRIDE 标记。"""
    rel_path = path.replace("\\", "/")
    # 跳过有原版键约定的目录
    if any(f"/{d}/" in rel_path for d in NAMING_SKIP_DIRS):
        return

    # 收集所有顶层对象定义行
    top_objs = []
    for i, raw in enumerate(text.splitlines(), start=1):
        m = TOP_OBJ_RE.match(raw)
        if m and m.group("indent") == "":
            name = m.group("name")
            top_objs.append((i, name))

    # 文件内任意位置有 OVERRIDE 标记 → 视为覆盖文件，整体跳过命名检查
    is_override_file = (
        OVERRIDE_BLOCK_MARK in text or OVERRIDE_LINE_MARK in text
    )
    # 事件文件（含 namespace 声明）跳过命名前缀检查
    is_events_file = bool(NS_RE.match(text.splitlines()[0])) if text.splitlines() else False

    for ln, name in top_objs:
        if name in ALLOW_NO_PREFIX_KEYS:
            continue
        if is_override_file or is_events_file:
            continue
        # 大写 FTR_ 前缀视为合法；小写 ftr_ 前缀合法
        if name.lower().startswith("ftr_"):
            continue
        # 无前缀 → 提示
        warn(
            path, ln,
            f"顶层对象 '{name}' 无 ftr_ 前缀。新增内容应加 ftr_ 前缀；"
            "覆盖原版请用 ###### OVERRIDE ###### 标记包裹。",
        )


# ---------- 7. 事件 namespace ----------
def check_namespace(path, text):
    if not path.endswith("_events.txt"):
        return
    first = text.splitlines()
    # namespace 必须在文件较前位置（前 20 行内）
    for i, raw in enumerate(first[:20], start=1):
        m = NS_RE.match(raw)
        if m:
            return
    # 找不到 namespace → 检查是否定义了事件
    if re.search(r"^\s*[\w]+\.\d+\s*=\s*\{", text, re.M):
        err(path, 1, "事件文件未声明 namespace（应在文件顶部写 namespace = xxx）")


# ---------- 8. 决议 ai_check_interval / ai_goal ----------
def check_decision(path, text):
    if not path.endswith(".txt") or "decisions" not in path.replace("\\", "/"):
        return
    # 解析顶层决议块，检查每个块是否含 ai_check_interval 或 ai_goal
    lines = text.splitlines()
    in_block = None       # 当前块名
    block_start = 0
    depth = 0
    has_ai = False
    for i, raw in enumerate(lines, start=1):
        stripped = raw.lstrip()
        m = TOP_OBJ_RE.match(raw)
        if m and m.group("indent") == "" and depth == 0:
            # 新顶层对象开始
            if in_block and not has_ai:
                warn(path, block_start, f"决议/对象 '{in_block}' 未写 ai_check_interval 或 ai_goal")
            in_block = m.group("name")
            block_start = i
            depth = 1
            has_ai = False
            continue
        if depth > 0:
            depth += raw.count("{") - raw.count("}")
            if "ai_check_interval" in raw or "ai_goal" in raw:
                has_ai = True
            if depth == 0:
                if in_block and not has_ai:
                    warn(path, block_start, f"决议/对象 '{in_block}' 未写 ai_check_interval 或 ai_goal")
                in_block = None
                depth = 0


# ---------- 9. 双语本地化键名一致性 ----------
def _normalize_loc_path(p):
    """把 _l_english / _l_simp_chinese 后缀归一化为公共键。"""
    return p.replace("_l_english", "").replace("_l_simp_chinese", "")


def collect_localization_keys(root):
    """收集每个语言目录下所有 yml 的键集合，返回归一化路径 -> {键}。"""
    eng_dir = os.path.join(root, "localization", "english")
    chi_dir = os.path.join(root, "localization", "simp_chinese")
    eng_files = {}
    chi_files = {}
    for base, store in ((eng_dir, eng_files), (chi_dir, chi_files)):
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                full = os.path.join(dirpath, fn)
                keys = set()
                try:
                    with open(full, encoding="utf-8-sig", errors="replace") as f:
                        for line in f:
                            m = LOC_KEY_RE.match(line)
                            if m:
                                keys.add(m.group(1))
                except OSError:
                    continue
                rel_fn = os.path.relpath(full, base)
                store[_normalize_loc_path(rel_fn)] = keys
    return eng_files, chi_files


def check_bilingual(root):
    eng, chi = collect_localization_keys(root)
    all_keys = sorted(set(eng) | set(chi))
    for fn in all_keys:
        if fn not in eng or fn not in chi:
            warn("localization", 1, f"本地化文件不成对: {fn}（english/ 与 simp_chinese/ 应对应存在）")
            continue
        # 键名一致性
        missing = eng[fn] - chi[fn]
        for k in sorted(missing):
            warn(f"localization/{fn}", 1, f"简体中文缺少键: {k}（english 中有）")
        extra = chi[fn] - eng[fn]
        for k in sorted(extra):
            warn(f"localization/{fn}", 1, f"简体中文多出键: {k}（english 中无）")


# ---------- 主流程 ----------
def scan_files(targets):
    """收集待校验文件列表。targets 为空则扫描整个 mod。"""
    files = []
    if targets:
        for t in targets:
            p = os.path.join(ROOT, t) if not os.path.isabs(t) else t
            if os.path.isfile(p):
                files.append(p)
            elif os.path.isdir(p):
                for dirpath, _, fns in os.walk(p):
                    for fn in fns:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in BOM_REQUIRED_EXT:
                            files.append(os.path.join(dirpath, fn))
    else:
        for sub in ("common", "events", "localization", "gui", "descriptor.mod"):
            p = os.path.join(ROOT, sub)
            if os.path.isfile(p):
                files.append(p)
                continue
            if not os.path.isdir(p):
                continue
            for dirpath, _, fns in os.walk(p):
                for fn in fns:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in BOM_REQUIRED_EXT or ext in {".mod"}:
                        files.append(os.path.join(dirpath, fn))
    # 去重
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="For The Realm P 语言语法校验")
    parser.add_argument("targets", nargs="*", help="指定目录或文件；默认校验整个 mod")
    parser.add_argument("--fix-bom", action="store_true", help="自动为缺失 BOM 的文件补上 BOM")
    parser.add_argument("--no-naming", action="store_true", help="跳过命名/覆盖标记启发式检查")
    args = parser.parse_args()

    files = scan_files(args.targets)

    for path in files:
        ext = os.path.splitext(path)[1].lower()
        # .mod 清单文件不强制 BOM（无中文时可不带）；.txt/.yml 必须带
        if ext != ".mod":
            if args.fix_bom:
                # --fix-bom：缺则补，不当作 error
                if not check_bom(path):
                    # 移除已记录的缺 BOM error，改记 warning
                    prefix = rel(path) + ":1"
                    errors[:] = [e for e in errors if not e.startswith(prefix)]
                    fix_bom(path)
            else:
                check_bom(path)
        # 重新读取（fix 后）
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                text = f.read()
        except OSError:
            continue

        if ext == ".yml":
            check_localization(path, text)
            check_indent(path, text, is_txt=False)
        elif ext == ".txt":
            check_braces(path, text)
            check_indent(path, text, is_txt=True)
            check_namespace(path, text)
            check_decision(path, text)
            if not args.no_naming:
                check_naming_and_override(path, text)
        elif ext == ".mod":
            check_braces(path, text)

    # 双语校验（全局，只在校验整个 mod 时跑）
    if not args.targets:
        check_bilingual(ROOT)

    # 输出
    print("=" * 60)
    print(f"共扫描 {len(files)} 个文件")
    print(f"错误(Error): {len(errors)}    警告(Warning): {len(warnings)}")
    print("=" * 60)
    for e in errors:
        print(e)
    for w in warnings:
        print(w)
    print("=" * 60)

    if errors:
        print("校验未通过：存在 Error 级问题，请修复后再进入游戏验证。")
        return 1
    if warnings:
        print("校验通过（但有 Warning 级规范提示，建议处理）。")
        return 2
    print("校验通过：无语法/规范问题。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

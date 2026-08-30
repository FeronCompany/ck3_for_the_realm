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
     * on_action 挂载点豁免：common/on_action/ 里沿用原版挂载点名（追加合并语义，
       既不加 ftr_ 前缀也不需要 OVERRIDE 标记），见 VANILLA_ON_ACTION_HOOKS
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

# CK3 原版 on_action 挂载点（追加合并语义）。
# 在 common/on_action/ 里重复定义这些同名挂载点只是向 on_actions 列表追加回调，
# 并非"覆盖重定义原版对象"，因此既不必加 ftr_ 前缀，也不需要 OVERRIDE 标记。
# 若遇到新增的挂载点，追加到此处即可。
VANILLA_ON_ACTION_HOOKS = {
    # 通用脉冲 / 生命周期
    "on_birth", "on_birth_child", "on_death", "on_marriage",
    "on_creation", "on_landed", "on_unlanded", "on_title_gain",
    "on_title_lost", "on_vassal_accept", "on_vassal_decline",
    "on_faith_convert", "on_culture_convert",
    # 战争 / 战斗
    "on_war_declared", "on_war_ended", "on_war_won", "on_war_lost",
    "on_combat_start", "on_combat_end_winner", "on_combat_end_loser",
    # 阴谋 / 计谋
    "on_scheme_start", "on_scheme_success", "on_scheme_failure",
    "on_scheme_complete", "on_scheme_invalidated",
    # 年度 / 季度 / 月度脉冲
    "random_yearly_everyone_pulse", "random_yearly_playable_pulse",
    "yearly_playable_pulse", "yearly_child_pulse", "yearly_pregnancy_pulse",
    "quarterly_playable_pulse", "quarterly_everyone_pulse",
    "monthly_playable_pulse", "monthly_everyone_pulse",
    "monthly_character_playable_pulse", "monthly_character_everyone_pulse",
    "weekly_playable_pulse", "weekly_everyone_pulse",
    # 界面 / 数据同步
    "on_game_start", "on_character_screen_open", "on_character_screen_close",
    "on_ai_monthly_playable_pulse", "on_ai_yearly_playable_pulse",
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


# ---------- 原版游戏对象白名单（用于引用一致性检查） ----------
# 加载游戏目录里定义的对象名（trait / law / effect / trigger / value 等），
# 供后续检查 mod 脚本是否引用了不存在的对象。游戏路径由 --game-path 指定。

GAME_PATH = ""          # 由 main() 解析 --game-path 设置
_game_objects = None    # { "trait": {...}, "law": {...}, ... } 缓存


def load_game_objects():
    """加载游戏目录中的对象白名单。返回 { 类别: {对象名} }。失败则返回 None。"""
    global _game_objects
    if _game_objects is not None:
        return _game_objects
    if not GAME_PATH:
        return None
    common = os.path.join(GAME_PATH, "common")
    if not os.path.isdir(common):
        return None
    _game_objects = {"trait": set(), "law": set(), "effect": set(),
                     "trigger": set(), "value": set()}

    # 扫描所有 .txt 的顶层 `name = {`，按目录归类
    dir_map = {
        "traits": "trait",
        "laws": "law",
        "scripted_effects": "effect",
        "scripted_triggers": "trigger",
        "script_values": "value",
    }
    for subdir, cat in dir_map.items():
        d = os.path.join(common, subdir)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                with open(p, encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            # script_values 多为标量（name = 数字/公式），需额外匹配 `name =` 形式
            if cat == "value":
                for m in re.finditer(r"^([\w.]+)\s*=\s*[^\{]", text, re.M):
                    _game_objects[cat].add(m.group(1))
            # trait/law 常嵌套在分组块内（任意缩进），用宽松匹配捕获
            if cat in ("trait", "law"):
                for m in re.finditer(r"^(\s*)([\w.]+)\s*=\s*\{", text, re.M):
                    _game_objects[cat].add(m.group(2))
            else:
                for m in re.finditer(r"^([\w.]+)\s*=\s*\{", text, re.M):
                    _game_objects[cat].add(m.group(1))
    # trait 额外收录"原版脚本实际使用过的 has_trait = X"——
    # CK3 有 trait 别名（如 lunatic/possessed 定义键不同但脚本可用），
    # 用实际使用作为白名单比定义键更可靠，避免误报。
    for sub in ("common", "events"):
        d = os.path.join(GAME_PATH, sub)
        if not os.path.isdir(d):
            continue
        for dirpath, _, fns in os.walk(d):
            for fn in fns:
                if not fn.endswith(".txt"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, encoding="utf-8-sig", errors="replace") as f:
                        t = f.read()
                except OSError:
                    continue
                for m in re.finditer(r"has_trait\s*=\s*([\w]+)", t):
                    _game_objects["trait"].add(m.group(1))
    return _game_objects


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
    # on_action 挂载点文件：其顶层键名遵循原版挂载点，走追加合并语义，单独豁免
    is_on_action_file = "/on_action/" in rel_path

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
        # on_action 挂载点：沿用原版名（追加合并语义），豁免前缀与 override
        if is_on_action_file and name in VANILLA_ON_ACTION_HOOKS:
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


# ---------- 9A. 引用一致性检查（语义级） ----------
# 检查 mod 脚本是否引用了不存在的对象名（trait / law / effect / trigger / value）。
# 需要 --game-path 提供原版游戏目录；未提供则跳过。

# 已知不存在的 trait（历史踩坑记录）
KNOWN_BAD_TRAITS = {"indecisive", "merciful", "loyal_1", "loyal_2", "loyal_3"}

# 已知非法/不存在的关键字（历史踩坑记录）
KNOWN_BAD_KEYS = {
    "has_army",            # 不存在，应使用 max_military_strength > 0
    "start_story",         # 不存在，应使用 create_story
    "inline_script",       # 不存在
    "xor",                 # 不存在（区分大小写，脚本里多为大写 XOR）
}


def check_reference(path, text):
    """检查 mod 脚本中的对象引用是否在游戏/本 mod 白名单内。"""
    if not GAME_PATH:
        return
    objs = load_game_objects()
    if objs is None:
        return

    # 收集本 mod 已定义的 scripted effect/trigger/value/trait/law（避免误报自身新增）
    mod_defined = {"effect": set(), "trigger": set(), "value": set(),
                   "trait": set(), "law": set()}
    dir_map = {
        "effect": "scripted_effects", "trigger": "scripted_triggers",
        "value": "script_values", "trait": "traits", "law": "laws",
    }
    for cat in mod_defined:
        d = os.path.join(ROOT, "common", dir_map[cat])
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(".txt"):
                    try:
                        with open(os.path.join(d, fn), encoding="utf-8-sig",
                                  errors="replace") as f:
                            t = f.read()
                    except OSError:
                        continue
                    if cat == "value":
                        for m in re.finditer(r"^([\w.]+)\s*=\s*[^\{]", t, re.M):
                            mod_defined[cat].add(m.group(1))
                    if cat in ("trait", "law"):
                        for m in re.finditer(r"^(\s*)([\w.]+)\s*=\s*\{", t, re.M):
                            mod_defined[cat].add(m.group(2))
                    for m in re.finditer(r"^([\w.]+)\s*=\s*\{", t, re.M):
                        mod_defined[cat].add(m.group(1))

    lines = text.splitlines()
    for i, raw in enumerate(lines, start=1):
        # has_trait = X
        for m in re.finditer(r"has_trait\s*=\s*([\w]+)", raw):
            name = m.group(1)
            if name in KNOWN_BAD_TRAITS:
                err(path, i, f"引用了不存在的特质 '{name}'")
            elif name not in objs["trait"] and name not in mod_defined["trait"]:
                err(path, i, f"特质 '{name}' 不在游戏/本 mod traits 白名单中（疑似拼写错误）")
        # has_realm_law / has_title_law = X
        for m in re.finditer(r"has_realm_law\s*=\s*([\w]+)", raw):
            name = m.group(1)
            if name not in objs["law"] and name not in mod_defined["law"]:
                err(path, i, f"王国法律 '{name}' 不在游戏/本 mod laws 白名单中")
        for m in re.finditer(r"has_title_law\s*=\s*([\w]+)", raw):
            name = m.group(1)
            if name not in objs["law"] and name not in mod_defined["law"]:
                err(path, i, f"头衔法律 '{name}' 不在游戏/本 mod laws 白名单中")
        # 引用 scripted effect：xxx_effect
        for m in re.finditer(r"\b([\w]+_effect)\s*=\s*yes", raw):
            name = m.group(1)
            if name not in objs["effect"] and name not in mod_defined["effect"]:
                err(path, i, f"脚本效果 '{name}' 未定义（不在游戏/本 mod scripted_effects 中）")
        # 引用 scripted trigger：xxx_trigger
        for m in re.finditer(r"\b([\w]+_trigger)\s*=\s*yes", raw):
            name = m.group(1)
            if name not in objs["trigger"] and name not in mod_defined["trigger"]:
                err(path, i, f"脚本条件 '{name}' 未定义（不在游戏/本 mod scripted_triggers 中）")
        # script value 引用（var: 除外）
        for m in re.finditer(r"\b(ftr_[a-z0-9_]+_value)\b", raw):
            name = m.group(1)
            if name not in objs["value"] and name not in mod_defined["value"]:
                err(path, i, f"脚本值 '{name}' 未定义（不在游戏/本 mod script_values 中）")
        # 已知非法关键字
        low = raw.lower()
        for bad in KNOWN_BAD_KEYS:
            if re.search(r"\b" + re.escape(bad) + r"\b", low):
                if bad == "start_story" or bad == "has_army" or bad == "inline_script":
                    err(path, i, f"使用了不存在的关键字 '{bad}'")


# ---------- 9B. 已知非法模式检查（语义级） ----------
def check_bad_patterns(path, text):
    """检查历史踩坑的非法写法，即使括号/命名校验通过也报错。"""
    lines = text.splitlines()
    for i, raw in enumerate(lines, start=1):
        # 1) send_option 的 starts_enabled 必须是块或省略，不能是 yes
        if re.search(r"starts_enabled\s*=\s*yes\b", raw):
            err(path, i, "send_option 的 starts_enabled 不接受 yes，应省略或用块/条件")
        # 2) send_interface_message 的 type 用 msg_generic 非法
        if re.search(r"type\s*=\s*msg_generic\b", raw):
            err(path, i, "send_interface_message 的 type 'msg_generic' 不存在，应使用事件消息类型")
        # 3) start_scheme 的 target 应改为 target_character
        if re.search(r"start_scheme\s*=\s*\{", raw):
            for m in re.finditer(r"\btarget\s*=\s*(scope:[\w.]+)", raw):
                err(path, i, "start_scheme 应使用 target_character = scope:X（target 无效）")
        # 4) modifier 里的 years 非法（持续时间由 add_character_modifier 提供）
        if re.search(r"^\s*(monthly_gold|monthly_prestige|monthly_piety|health)\s*=\s*\d+", raw) and \
           re.search(r"years\s*=", raw):
            # 仅当同文件出现 modifier 属性 + years 混排时才提示（粗粒度）
            pass


# ---------- 9C. GUI 语义检查 ----------
# 检查 .gui 文件中的常见错误（data function 不存在、非法类型/属性）。
# CK3 GUI 常见坑（历史踩坑记录）：
#   - data function Custom() / CustomDescription() 不存在 → 应 ScriptValue / Var(...).GetValue
#   - ScriptValue('x') 要求 x 是 script value 定义
#   - 角色变量读取用 Var('x').Char（window_situation_list 范式）
#   - GetValue|N 用于列表，返回数值/列表元素（角色需 datamodel+item）
#   - text 是属性不是类型 → 文本块应为 text_single / text_block
#   - gridbox 不支持 datamodel 列表 → 应用 fixedgridbox（datamodel_wrap + addcolumn/addrow）

def check_gui(path, text):
    # 加载 script_values 白名单（game + mod），用于判断 ScriptValue 引用是否合法
    sv_known = set()
    if GAME_PATH:
        gd = os.path.join(GAME_PATH, "common", "script_values")
        if os.path.isdir(gd):
            for fn in os.listdir(gd):
                if fn.endswith(".txt"):
                    try:
                        with open(os.path.join(gd, fn), encoding="utf-8-sig",
                                  errors="replace") as f:
                            t = f.read()
                    except OSError:
                        continue
                    for m in re.finditer(r"^([\w.]+)\s*=", t, re.M):
                        sv_known.add(m.group(1))
    md = os.path.join(ROOT, "common", "script_values")
    if os.path.isdir(md):
        for fn in os.listdir(md):
            if fn.endswith(".txt"):
                try:
                    with open(os.path.join(md, fn), encoding="utf-8-sig",
                              errors="replace") as f:
                        t = f.read()
                except OSError:
                    continue
                for m in re.finditer(r"^([\w.]+)\s*=", t, re.M):
                    sv_known.add(m.group(1))

    lines = text.splitlines()
    for i, raw in enumerate(lines, start=1):
        # 1) 不存在的 data function：Custom / CustomDescription
        if re.search(r"\.Custom\(|CustomDescription\(", raw):
            err(path, i, "GUI 不存在的 data function 'Custom'/'CustomDescription'，应使用 ScriptValue/Var(...).GetValue")
        # 2) 文本块用 text = {（text 是属性不是类型）
        if re.match(r"^\s*text\s*=\s*\{\s*$", raw):
            err(path, i, "文本块类型应为 text_single / text_block，'text' 是属性不是类型")
        # 3) gridbox 直接放 datamodel（gridbox 不支持，应用 fixedgridbox）
        if re.match(r"^\s*gridbox\s*=\s*\{", raw):
            # 仅当块内含 datamodel 时提示（检查后续若干行）
            window = "\n".join(lines[i:i + 6])
            if "datamodel" in window:
                warn(path, i, "gridbox 不支持 datamodel 列表，建议改用 fixedgridbox（datamodel_wrap + addcolumn/addrow）")
        # 4) ScriptValue('x') 的 x 必须是已定义的 script value（否则 GUI 报错）
        for m in re.finditer(r"ScriptValue\(\s*'([\w]+)'\s*\)", raw):
            name = m.group(1)
            if GAME_PATH and name not in sv_known:
                err(path, i, f"ScriptValue('{name}') 不是已定义的 script value，GUI 会报错；读取普通变量请用 Var('...').GetValue")
            elif not GAME_PATH:
                warn(path, i, f"ScriptValue('{name}') 要求该名字是已定义的 script value（用 --game-path 精确校验）")


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
    # .gui 也要收集（用于 GUI 语义检查），但 BOM 不强制
    SCAN_EXT = BOM_REQUIRED_EXT | {".gui"}
    if targets:
        for t in targets:
            p = os.path.join(ROOT, t) if not os.path.isabs(t) else t
            if os.path.isfile(p):
                files.append(p)
            elif os.path.isdir(p):
                for dirpath, _, fns in os.walk(p):
                    for fn in fns:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in SCAN_EXT:
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
                    if ext in SCAN_EXT or ext in {".mod"}:
                        files.append(os.path.join(dirpath, fn))
    # 去重
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="For The Realm P 语言语法校验")
    parser.add_argument("targets", nargs="*", help="指定目录或文件；默认校验整个 mod")
    parser.add_argument("--fix-bom", action="store_true", help="自动为缺失 BOM 的文件补上 BOM")
    parser.add_argument("--no-naming", action="store_true", help="跳过命名/覆盖标记启发式检查")
    parser.add_argument(
        "--game-path", default="",
        help="原版游戏根目录（含 common/）。提供后启用引用一致性检查。"
             "示例：--game-path \"C:/Program Files (x86)/Steam/steamapps/common/Crusader Kings III/game\"",
    )
    parser.add_argument(
        "--no-ref", action="store_true",
        help="跳过引用一致性检查（traits/laws/effects/triggers/values 校验）",
    )
    args = parser.parse_args()

    global GAME_PATH
    GAME_PATH = args.game_path

    files = scan_files(args.targets)

    for path in files:
        ext = os.path.splitext(path)[1].lower()
        # .mod 清单 / .gui 不强制 BOM（.gui 由引擎按行解析，无需 BOM）；.txt/.yml 必须带
        if ext not in (".mod", ".gui"):
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
            check_bad_patterns(path, text)
            if not args.no_naming:
                check_naming_and_override(path, text)
            if GAME_PATH and not args.no_ref:
                check_reference(path, text)
        elif ext == ".gui":
            check_braces(path, text)
            check_gui(path, text)
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

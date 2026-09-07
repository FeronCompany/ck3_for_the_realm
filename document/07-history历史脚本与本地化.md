# 07 history 历史脚本与本地化

> 两个"非典型"子系统：`history/` 是唯一使用**时间轴范式**的目录；`localization/` 是**独立于脚本之外**的文本层。

## 本篇导读

- **第一部 history 历史脚本** —— 基线 + 日期覆盖块的范式、`characters` / `titles` / `provinces` / `cultures` 四类语法、组织约定、常见错误。
- **第二部 本地化与可定制文本** —— `.yml` 文件格式（**UTF-8 with BOM**）、键值语法、方括号动态取值系统、`Custom()` 与 `customizable_localization`、effect / trigger 本地化。

**两者的共同点**：都大量依赖"键名约定"而非"显式声明"，是 P 语言"约定优于配置"的典型体现。

## 文档关联

- **前置**：[01 词法、数据类型与值系统](01-词法、数据类型与值系统.md)
- **被引用于**：[06 事件系统与 on_action](06-事件系统与on_action.md)（事件的 title / desc / option 全部指向本地化键）
- **系统落地**：[15 common 目录清单与速查表](15-common目录清单与速查表.md)

## 目录

| 部 | 章节 |
|---|---|
| 第一部 history | 核心范式 · 与 common 的差异 · characters · titles · provinces · cultures · 其他子目录 · 组织约定 · 常见错误 · 模板 |
| 第二部 本地化 | 目录结构 · 文件格式 · 条目语法 · 转义 · 方括号取值 · customizable_localization · effect/trigger 本地化 · key 约定 · Mod 组织 · 常见错误 |

---

# 第一部 History 历史脚本

> `history/` 目录是 P 语言里**唯一使用"时间轴"范式**的地方：不是定义对象，而是**按日期回放初始化指令**。

---

## 1. 核心范式：基线 + 日期覆盖块

官方原文（`history/_history.info` 全文）：

```paradox
=== Structure ===

All history files have the same format:

<basic key-value pairs that denote the beginning of time>

date = {
	<overriding key-value pairs>
}

date = {
	<overriding key-value pairs>
}

...

Which key-value pairs are available depends on the type of history.
```

```mermaid
graph TD
    F["history 文件"] --> B["基线块<br/>对象 ID = { 起始时间的属性 }"]
    B --> D1["date = { 覆盖属性 }<br/>867.1.1"]
    D1 --> D2["date = { 覆盖属性 }<br/>1066.1.1"]
    D2 --> D3["date = { 覆盖属性 }<br/>1178.1.1"]
    D3 --> D4["..."]

    D4 --> R["引擎按所选开局日期<br/>依次执行所有 &lt;= 该日期的块"]

    style F fill:#2d3f52,stroke:#5b7fa6,color:#fff
    style R fill:#3c4a3c,stroke:#6b8f6b,color:#fff
```

**执行语义**：玩家选择一个开局日期（如 1066.9.15），引擎**从头到尾**执行所有 `日期 <= 开局日期` 的块。选择较早的开局日期时，后面的块不会执行。

---

## 2. 与 `common/` 的语法差异

| 维度 | `common/` | `history/` |
|---|---|---|
| 范式 | 定义数据库对象 | 时间轴指令序列 |
| 顶层结构 | `object_id = { 属性 }` | `object_id = { 属性 + date = { } ... }` |
| 顺序 | 基本无关（后覆盖前） | **严格按日期递增** |
| 内容 | 静态属性 | 属性 + 效果 + 生命周期事件 |
| 加载时机 | 启动时建库 | 开局时回放 |

---

## 3. `history/characters/` —— 角色历史

### 3.1 官方语法说明

`history/_characters.info` 全文：

```paradox
=== Structure ===

1001 = {	# character id
	name = ...
	dna = ...
	female = ...
	martial = ...
	prowess = ...
	diplomacy = ...
	intrigue = ...
	stewardship = ...
	learning = ...
	trait = ...
	father = ...
	mother = ...
	disallow_random_traits = ...

	faith = ...
	culture = ...
	dynasty = ...
	dynasty_house = ...
	give_nickname = ...
	sexuality = ...
	health = ...
	fertility = ...
	set_house = ...
	set_culture = ...
	set_character_faith_no_effect = ...
	add_spouse/add_matrilineal_spouse/add_same_sex_spouse = ...

	portrait_override = {	# Will override the character's appearance
		portrait_modifier_overrides={
			modifier_category_1 = modifier_1 # E.g. clothes=western_low_nobles
			modifier_category_1 = modifier_2
			...
		}
		hair={ R G B }	# hair color, e.g. hair={ 0.592 0.314 0.176 }
	}
}

1002 = ....
```

### 3.2 真实示例

`history/characters/albanian.txt`（全文）：

```paradox
komiskortes_of_dyrrachion = {
	# Komiskortes, a native of Dyrrachion, attested in Anna Comnene's writings as active in 1081
	name = "Komiskortes"
	dynasty = durres_dynasty
	religion = orthodox
	culture = albanian
	trait = education_martial_2
	1033.1.1 = {
		birth = yes
	}
	1066.1.1 = {
		learn_language_of_culture = culture:greek
	}
	1082.1.1 = {
		death = yes
	}
}
```

```mermaid
graph LR
    A["基线属性<br/>name / dynasty<br/>religion / culture / trait"] --> B["1033.1.1<br/>birth = yes"]
    B --> C["1066.1.1<br/>learn_language_of_culture<br/>= culture:greek"]
    C --> D["1082.1.1<br/>death = yes"]

    style A fill:#2d3f52,stroke:#5b7fa6,color:#fff
    style B fill:#3c4a3c,stroke:#6b8f6b,color:#fff
    style D fill:#4a3c3c,stroke:#a6705b,color:#fff
```

### 3.3 关键语法要点

| 要点 | 说明 |
|---|---|
| **顶层键是角色 ID 字符串** | 不是数字 ID（引擎会自动分配数字 ID） |
| `birth = yes` | 在日期块里标记出生 |
| `death = yes` | 在日期块里标记死亡 |
| `trait` / `add_trait` | 添加特质 |
| `disallow_random_traits = yes` | 禁止引擎随机补特质（历史人物必备） |
| `dna = ...` | 外貌 DNA 字符串 |
| `effect = { ... }` | 可执行任意效果块 |
| `template = X` | 引用 `common/scripted_character_templates/` |
| `religion` / `faith` | 信仰（注意 `_characters.info` 里两者都列了） |

### 3.4 日期格式

```
年.月.日
1033.1.1     # 1033 年 1 月 1 日
1066.9.15    # 1066 年 9 月 15 日（黑斯廷斯战役）
```

---

## 4. `history/titles/` —— 头衔历史

### 4.1 真实示例

`history/titles/k_france.txt`（开头部分）：

```paradox
k_france = {
	867.1.1 = { change_development_level = 5 }
	1066.1.1 = { change_development_level = 8 }
	1178.1.1 = { change_development_level = 24 }

	#Merovingians
	481.1.1 = {
		holder = 168673 #Clovis Ier
		name = WEST_FRANCIA
		succession_laws = { male_only_law }
	}
	511.11.27 = {
		holder = 168681 #Clotaire Ier
	}
	561.11.29 = {
		holder = 168689 #Chilpéric Ier
	}
	...
}
```

```mermaid
graph TD
    T["k_france = { }"] --> D1["867.1.1<br/>change_development_level = 5"]
    T --> D2["1066.1.1<br/>change_development_level = 8"]
    T --> D3["481.1.1<br/>holder = 168673<br/>name = WEST_FRANCIA<br/>succession_laws = { male_only_law }"]
    T --> D4["511.11.27<br/>holder = 168681"]
    T --> D5["561.11.29<br/>holder = 168689"]

    style T fill:#2d3f52,stroke:#5b7fa6,color:#fff
    style D3 fill:#3c4a3c,stroke:#6b8f6b,color:#fff
```

> **注意**：块可以**不按日期顺序书写**，引擎会自行排序。但为了可读性，建议按日期递增。

### 4.2 常用键

| 键 | 含义 |
|---|---|
| `holder = <char_id>` | 持有者（数字 ID 或角色 ID 字符串） |
| `holder = 0` | 空置（无持有者） |
| `liege = <title>` | 直属领主 |
| `de_jure_liege = <title>` | 法理领主 |
| `name = NAME_KEY` | 覆盖头衔显示名 |
| `succession_laws = { ... }` | 继承法 |
| `government = X` | 政体 |
| `capital = c_xxx` | 首都 |
| `change_development_level = N` | 发展度 |
| `heir = <char_id>` | 指定继承人 |
| `destroy_title_if_invalid_holder = yes` | 持有者非法则销毁 |

---

## 5. `history/provinces/` —— 省份历史

### 5.1 官方语法说明

`history/_provinces.info` 全文：

```paradox
=== Structure ===

== Mapped History ==
(These entries get copied from the source province if there is a mapping in history/province_mapping.)

culture = norse
faith = norse_pagan
terrain = arctic

== Main Province History ==
(These entries will NOT get copied to mapped provinces.)

# Set which holding type to use in the province. Default = auto.
# <holding_type> can be any holding type in common/holdings.
# none will not auto-generate any holding in that province
# auto will select a holding for the province automatically to fill the county with different holdings. See required_county_holdings in common/governments.
holding = <holding type> / none / auto

# To script Special Buildings, use 'special_building_slot = building_type' for just the slot, and 'special_building = building_type' for actually building the building.

# Set buildings in the holding (requires an explicit holding to be present - auto doesn't work).
# In a later history entry, this overrides all previous buildings.
buildings = { ... }

special_building_slot = X		# Enables and sets the special building slot for building X
special_building = X			# Same as special_building_slot, but also builds the actual building in the slot
duchy_capital_building = X		# Builds the capital duchy building X (only for duchy capitals)
```

### 5.2 真实示例

`history/provinces/k_brittany.txt`（开头部分）：

```paradox
#k_brittany
##d_brittany ###################################
###c_vannes
2154 = {	#VANNES
	culture = breton
	religion = catholic
	holding = castle_holding
}
2163 = {	#PORHOET
	holding = church_holding
}
2160 = {	#ROHAN
	holding = none
	1104.1.1 = {
		holding = city_holding
	}
}

###c_nantes
2152 = {	#NANTES
	culture = breton
	religion = catholic
	holding = castle_holding
}
2151 = {	#RAIS
	holding = city_holding
}
2153 = {	#GUERANDE
	holding = church_holding
}
2166 = {	#CHATEAUBRIANT
	holding = none
	1100.1.1 = {
		holding = castle_holding
	}
}
```

**要点**：

- 顶层键是**省份数字 ID**（如 `2154`），不是字符串
- 文件按王国/帝国组织（一个文件含多个省份）
- `holding = none` + 后续日期块 → 表示该地块**开局时无建筑，到某年才建**
- 注释里的行尾标注（`#VANNES`）帮助定位

### 5.3 常用键

| 键 | 含义 |
|---|---|
| `culture = X` | 文化 |
| `religion = X` / `faith = X` | 信仰 |
| `terrain = X` | 地形 |
| `holding = <type> / none / auto` | 地产类型 |
| `buildings = { ... }` | 建筑列表 |
| `special_building_slot = X` | 特殊建筑槽位 |
| `special_building = X` | 特殊建筑（含实际建造） |
| `duchy_capital_building = X` | 公国首府建筑 |
| `change_development_level = N` | 发展度 |
| `title = c_xxx` | 关联头衔 |

---

## 6. `history/cultures/` —— 文化历史

### 6.1 官方语法说明

`history/cultures/_culture.info` 全文：

```paradox
Name of the file is the culture key that should get the history.
Culture groups can be used too; if a file exists for an individual culture that'll be used rather than the group.
E.G., if "north_germanic_group.txt" and "norwegian.txt" both exist, Norwegian culture will use "norwegian.txt" while Swedish culture will use "north_germanic_group.txt".

date = {									# When is executed
	discover_innovation = innovation_key	# Discovers this innovations. There can be multiple per date.
	add_innovation_progress = {				# Advances a % defined on the defined innovation. There can be multiple per date.
		culture_innovation = innovation_key # Innovation
		progress = 50						# How much progress dos it gains
	}
	join_era = culture_era_key				# Joins the defined era. Only one per date.
	progress_era = 50						# Progress inthe current era. Only one per date.
}

##################################
Everything is executed in the order specified before
```

### 6.2 示例

```paradox
# history/cultures/norwegian.txt
800.1.1 = {
	discover_innovation = innovation_mustering_1
}
1000.1.1 = {
	add_innovation_progress = {
		culture_innovation = innovation_shipbuilding_2
		progress = 50
	}
}
1100.1.1 = {
	join_era = culture_era_2
}
```

> **文件粒度规则**：文件名即文化 key。可为文化组写一份（如 `north_germanic_group.txt`），也可为单个文化写一份；**单个文化的文件优先**于文化组文件。

---

## 7. 其他 history 子目录

| 目录 | 内容 | 说明 |
|---|---|---|
| `history/wars/` | 开局时已在进行/已结束的战争 | 时间轴定义宣战与停战 |
| `history/artifacts/` | 历史宝物 | 定义宝物及其持有者沿革 |
| `history/situations/` | 开局情境 | 见 `_situations.info` |
| `history/struggles/` | 开局局势 | 定义局势状态 |
| `history/province_mapping/` | 省份映射 | 用于随机世界的省份数据复用 |

---

## 8. History 文件的组织约定

```mermaid
graph TD
    H["history/"] --> C["characters/<br/>按文化分组<br/>frankish.txt / han.txt / japanese.txt"]
    H --> T["titles/<br/>按头衔分组<br/>k_france.txt / e_japan.txt"]
    H --> P["provinces/<br/>按王国分组<br/>k_brittany.txt / h_china.txt"]
    H --> CU["cultures/<br/>按文化/文化组分组"]
    H --> W["wars/"]
    H --> A["artifacts/"]
    H --> PM["province_mapping/"]

    style H fill:#2d3f52,stroke:#5b7fa6,color:#fff
```

> **Mod 建议**：新增历史内容时，**新建自己的文件**而不是修改原版文件。例如加角色就建 `history/characters/ftr_my_characters.txt`。

---

## 9. 常见错误

| 症状 | 原因 |
|---|---|
| 开局人物不存在 | 缺 `birth = yes` 或 `birth` 日期晚于开局日期 |
| 人物开局已死 | `death` 日期早于开局日期 |
| 头衔无人持有 | 缺 `holder` 或 `holder = 0` |
| 地块没有建筑 | `holding = none` 且后续日期块晚于开局 |
| 文化革新全解锁 | `discover_innovation` 日期设得太早 |
| 角色被随机加特质 | 缺 `disallow_random_traits = yes` |
| 历史文件整体失效 | 编码不是 UTF-8 with BOM |
| 覆盖无效 | 后加载的 Mod 覆盖先加载的；检查 `descriptor.mod` 的 load order |

---

## 10. 完整模板

```paradox
# ── history/characters/ftr_characters.txt ──
ftr_my_historical_char = {
	name = "My Character"
	dynasty = ftr_my_dynasty
	faith = catholic
	culture = frankish
	disallow_random_traits = yes
	trait = brave
	trait = education_martial_3
	martial = 15
	prowess = 12
	diplomacy = 10
	stewardship = 8
	intrigue = 6
	learning = 7
	female = no

	900.1.1 = { birth = yes }
	930.1.1 = { effect = { add_trait = ambitious } }
	950.1.1 = { add_spouse = ftr_my_spouse }
	980.1.1 = { death = yes }
}

# ── history/titles/ftr_titles.txt ──
k_my_kingdom = {
	867.1.1 = {
		holder = ftr_my_historical_char
		change_development_level = 10
		succession_laws = { male_only_law }
	}
	1066.1.1 = { change_development_level = 20 }
}

# ── history/provinces/ftr_provinces.txt ──
# k_my_kingdom
## d_my_duchy
### c_my_county
9001 = {	#MY_CAPITAL
	culture = frankish
	religion = catholic
	holding = castle_holding
	buildings = { barracks_01 }
}
9002 = {	#MY_SECOND
	holding = none
	1100.1.1 = { holding = city_holding }
}
```

---

# 第二部 本地化（Localization）与可定制文本

> 本文覆盖：`.yml` 文件格式、键值语法、方括号动态取值系统、customizable localization。

---

## 1. 目录结构

```
game/localization/
├── languages.yml                 # 语言总表
├── english/            (~1174 个 .yml)
├── simp_chinese/       (~1187 个 .yml)
├── french/  german/  japanese/  korean/  polish/  russian/  spanish/
├── jomini/script_system/         # 引擎级本地化
```

`localization/english/` 的子目录（用于分类组织）：

```
accolades/  activities/  artifacts/  bookmark/  contracts/  credits/
culture/    custom_localization/  diarchies/  dlc/  domiciles/
dynasties/  dynasty_legacies/  effects/  enum/  event_localization/
great_projects/  gui/  hold_court_events/  hostages/  interactions/
inventory/  ledger/  lifestyles/  load_tips/  map/  modifiers/
names/  no_translation/  opinions/  portraits/  religion/
situations/  struggles/  travel/  triggers/  tutorial/
```

> 其中 `event_localization/`（284 个文件）和 `custom_localization/`（56 个）是最大的两块。

---

## 2. 文件格式

### 2.1 语言头

每个 `.yml` 文件**第一列**写语言头：

| 语言 | 文件头 |
|---|---|
| 英语 | `l_english:` |
| 简体中文 | `l_simp_chinese:` |
| 法语 | `l_french:` |
| 德语 | `l_german:` |
| 波兰语 | `l_polish:` |
| 西班牙语 | `l_spanish:` |
| 俄语 | `l_russian:` |
| 韩语 | `l_korean:` |
| 日语 | `l_japanese:` |

### 2.2 编码：**UTF-8 with BOM**

实测（`localization/english/editor_l_english.yml` 44 字节 vs 可见文本 41 字节，差 3 字节 = `EF BB BF`）。

> **这是本地化最常见的失效原因**：不带 BOM 会导致中文全部乱码或整份本地化不加载。

### 2.3 缩进

- 语言头**顶格**写
- 之后所有条目**至少 1 个空格缩进**（YAML 语义上是 `l_english:` 的子项）
- 惯例用 **1 个空格**
- 缩进量不敏感，甚至完全不缩进引擎也接受（但不推荐）

```yaml
l_english:
 key:0 "value"
 another_key:0 "another value"
```

### 2.4 注释

`#` 开头，可顶格也可行尾：

```yaml
# 这是注释
 key:0 "value"    # 行尾注释
## 双井号只是习惯
```

---

## 3. 条目语法

### 3.1 基本形式

```yaml
l_english:
 key:0 "value"
```

### 3.2 数字后缀（版本号）

```yaml
l_english:
 key:0 "value A"
 key:1 "value B"
```

出处：`localization/languages.yml` 第 4-11 行

```yaml
l_english:
 l_english:0 "English"
 l_french:0 "Français"
 l_german:0 "Deutsch"
 l_polish:1 "Polski"           # ← 版本号是 1，其他是 0
 l_spanish:0 "Español"
 l_simp_chinese:0 "中文"
 l_russian:0 "Русский"
 l_korean:0 "한국어"
 l_japanese:0 "日本語"
```

> **结论**：版本号在不同语言间**不要求一致**。它是"同一 key 的多个变体槽位"，具体语义由使用该 key 的脚本决定（如特质描述按性别/年龄选变体）。

### 3.3 转义

| 写法 | 含义 |
|---|---|
| `\"` | 双引号 |
| `\\"` | 双反斜杠转义（用于通过校验钩子） |
| `\n` | 换行 |
| `§Y` `§G` `§R` `§!` | 颜色/格式标记 |
| `#EMP ... #!` | 强调 |
| `#HIGH ... #!` | 高亮 |
| `#font:Russian ... #!` | 字体切换 |
| `#help ... #!` | 帮助文本 |

真实示例（`localization/english/tutorial_objectives_l_english.yml:36`）：

```yaml
 hint_fabricate_claim: "Fabricate a [claim|E] using your [ROOT.Char.GetCouncillorPosition( 'councillor_court_chaplain' ).GetPositionName] [chaplain.GetFirstNamePossessive] #HIGH $task_fabricate_claim$#! [councillor_task|E].\n\n#help [ROOT.Char.GetCouncillorPosition( 'councillor_court_chaplain' ).GetPositionName] with higher [learning_skill|E] have a higher chance of getting the claim on the [title_duchy.GetName]. It will always be an [unpressed_claim|E], so your [children|E] won't inherit it, you have to act fast. $hint_claim_benefits$#!"
```

---

## 4. 方括号动态取值系统

这是本地化最强大的部分：`[ ... ]` 内可以写**域链 + 数据函数**。

```mermaid
graph TD
    BR["[...] 语法"] --> SCOPE["域链部分<br/>ROOT / name（不用 scope: 前缀）<br/>councillor / location"]
    BR --> CHAIN["链接链<br/>.Char / .GetCulture<br/>.GetFaith / .GetTitle"]
    BR --> FN["数据函数<br/>GetName / GetHerHis<br/>GetTitledFirstName"]
    BR --> ARG["带参函数<br/>Custom('X')<br/>Custom2('X', arg)<br/>GetCouncillorPosition('x')"]
    BR --> SUF["格式化后缀<br/>|U 首字母大写<br/>|V (动词变位)<br/>|E 概念链接"]

    style BR fill:#2d3f52,stroke:#5b7fa6,color:#fff
    style FN fill:#3c4a3c,stroke:#6b8f6b,color:#fff
    style ARG fill:#4a3c3c,stroke:#a6705b,color:#fff
```

### 4.1 常用数据函数（实证）

| 函数 | 返回 | 出处 |
|---|---|---|
| `GetName` | 名字 | 通用 |
| `GetFirstName` | 名 | 通用 |
| `GetFirstNameNoTooltip` | 名（无悬浮提示） | `traits_l_english.yml:94` |
| `GetFirstNamePossessive` | 名的所有格 | `tutorial_objectives_l_english.yml:36` |
| `GetTitledFirstName` | 带头衔的名字 | `traits_l_english.yml:857` |
| `GetSheHe` | 他/她 | `traits_l_english.yml:128` |
| `GetHerHis` | 他的/她的 | `traits_l_english.yml:124` |
| `GetHerHim` | 他/她（宾格） | `traits_l_english.yml:339` |
| `GetWomanMan` | 女人/男人 | `traits_l_english.yml:124` |
| `HighGodName` | 信仰的至高神名 | `war_declared_overview_window_l_english.yml:10` |
| `GetNameNoTierNoTooltip` | 名字（无层级无提示） | `oltner_travel_l_english.yml:109` |
| `GetAdjective` | 形容词形式 | `tourism_destinations_l_english.yml:344` |
| `GetCollectiveNoun` | 集体名词 | `tourism_destinations_l_english.yml:344` |
| `GetPositionName` | 职位名 | `tutorial_objectives_l_english.yml:36` |

### 4.2 域链写法

```yaml
 # 从 ROOT 出发（出处: traits_l_english.yml:94）
 trait_x_desc:0 "[ROOT.GetCharacter.GetFirstNameNoTooltip] is known as ..."

 # ROOT.Char 形式（更常见）
 trait_x_desc:0 "[ROOT.Char.GetCulture.GetName] warrior practices."

 # 跨域链（出处: war_declared_overview_window_l_english.yml:10）
 war_flavor:2 "[ROOT.Char.GetFaith.HighGodName] have mercy on you!"

 # 长链（出处: tourism_destinations_l_english.yml:344）
 desc: "... [location.GetTitle.GetHolder.Custom('ComplimentAdjective')] [location.GetCounty.GetTitle.GetAdjective] [location.GetCulture.GetCollectiveNoun] ..."
```

### 4.3 格式化后缀

| 后缀 | 作用 | 出处 |
|---|---|---|
| `\|U` | 首字母大写（Uppercase first） | `traits_l_english.yml:128` `[ROOT.Char.GetSheHe\|U]` |
| `\|E` | 概念链接（Concept link） | `tutorial_objectives_l_english.yml:36` `[claim\|E]` |
| `\|V` | 动词形式 | — |

```yaml
 # 首字母大写（出处: traits_l_english.yml:128）
 trait_august_character_desc:0 "[ROOT.Char.GetSheHe|U] is honored as a true ruler!"

 # 概念链接（出处: tutorial_objectives_l_english.yml:36）
 hint: "Fabricate a [claim|E] using your ... [councillor_task|E]."
```

### 4.4 `Custom()` 与 `Custom2()` —— 可定制文本

```yaml
 # 单参（出处: traits_l_english.yml:583）
 desc:1 "... a pleasing [ROOT.Char.Custom('FemaleMale')] physique."

 # 双参（出处: traits_l_english.yml:857）
 desc_ancestor:0 "[ROOT.Char.Custom2('RelationToMe', ROOT.Var('reincarnation_of').Char)]"

 # 定义在 customizable_localization/（出处: tutorial_objectives_l_english.yml:8）
 desc: "[councillor.Custom2('AppropriateGreetingPositive', ROOT.Char)] you've been doing a great service..."

 # 无参数形式（出处: tutorial_objectives_l_english.yml:52）
 hint: "Hire [ROOT.Char.Custom('KnightCulturePluralNoTooltip')]"
```

> `Custom('X')` 对应 `common/customizable_localization/` 里定义的 `X` 键。

### 4.5 `$KEY$` 变量替换

```yaml
 # 出处: tutorial_objectives_l_english.yml:36
 "... #HIGH $task_fabricate_claim$#! ... $hint_claim_benefits$#!"
```

---

## 5. Customizable Localization（可定制本地化）

定义目录：`common/customizable_localization/*.txt`（149 个文件）

### 5.1 官方语法

`common/customizable_localization/_custom_loc.info` 全文：

```paradox
The following scope types can be defined as the "type" in a "type = X" argument.
It should match whatever scope you use the custom loc command in.

artifact
character
landed_title
province
activity
secret
scheme
combat
combat_side
title_and_vassal_change
faith
dynasty
all # Accepts any scope type, but you can then only really check triggers that can be used on anything

== format ==
key = {
	type = scope

	text = {
		# Run before the trigger is evaluated, can save scopes which you then check
		# for in the trigger directly. These scopes can be referenced in the loc key.
		# Only interface effects are valid so the game state can not be modified
		setup_scope = {
			<interface effects>
		}

		# What triggers should be true for this to be a valid text entry
		# Interface triggers are valid such as checking if a window is open
		# The first trigger that matches returns the relevant localization_key text
		trigger = {
			<interface triggers>
		}

		# The localization key, has the scopes from setup_scope accessible
		localization_key = string

		# Optional; will cause this one to be picked if no entry is valid
		fallback = yes
	}

	...

	random_valid = yes # Optional, will randomize instead of picking first valid
}

You can also add variants:
key = {
	parent = some_custom_loc_key
	suffix = "_suffix"
}
The logic of the parent will be run, then the suffix is added to the custom loc key.
```

### 5.2 真实示例

`common/customizable_localization/00_greeting_custom_loc.txt`：

```paradox
#GREETINGS MY LOVER
GreetingToLover = {
	type = character

	text = {
		trigger = {
			scope:second = {
				object_of_importance_exist_trigger = {
					LOVER = root
				}
			}
		}
		localization_key = greeting_lover_object
	}

	text = {
		localization_key = greeting_lover_fallback
	}
}

#GREETINGS MY LIEGE
GreetingToLiege = {
	type = character

	text = {
		trigger = {
			opinion = {
				target = scope:second
				value >= 20
			}
		}
		localization_key = greeting_liege_positive
	}

	text = {
		trigger = {
			opinion = {
				target = scope:second
				value <= -40
			}
		}
		localization_key = greeting_liege_negative
	}

	text = {
		trigger = {
			scope:second = { tgp_is_ceremonial_regent_trigger = yes }
		}
		localization_key = greeting_ceremonial_liege_fallback
	}

	text = {
		localization_key = greeting_liege_fallback
	}
}
```

### 5.3 工作机制

```mermaid
sequenceDiagram
    autonumber
    participant L as 本地化字符串
    participant C as Custom('X')
    participant D as customizable_localization 定义
    participant T as trigger 链
    participant K as 最终 loc key

    L->>C: [ROOT.Char.Custom('GreetingToLiege')]
    C->>D: 查找键 GreetingToLiege
    D->>T: 依次求值 text = { trigger }
    alt 第一个通过的
        T-->>C: localization_key = greeting_liege_positive
    else 全不通
        T-->>C: 取 fallback = yes 的项<br/>或最后一项
    end
    C->>K: 返回最终本地化键
    K->>L: 渲染文本
```

> **要点**：
> 1. `text` 块按书写顺序求值，**取第一个 trigger 通过的**
> 2. 无 trigger 的 `text` 块作为兜底（等价于 `fallback = yes`）
> 3. `random_valid = yes` 时改为随机选取
> 4. `setup_scope` 只能执行**界面效果**（不改游戏状态）
> 5. `parent` + `suffix` 可复用逻辑并加后缀

---

## 6. Effect Localization

定义目录：`common/effect_localization/*.txt`（35 个文件）

官方说明（`common/effect_localization/_effect_localization.info` 全文）：

```paradox
- _category = { ... } creates a new group with name category ( lead with '_' to create a group )
- first and third indicates first person or third person, default is no or global pronoun
- past indicates past tense, default is future/present
- neg indicates that this is used for negative output values, ie "gain x gold" versus "lose x gold"
- the value given to the localization of a neg version will always be positive

# Default format
You do not need to define an effect_localization entry, the system will look at localization keys like this:

<effect_name>_first         # "I gain 123 gold"
<effect_name>_first_past    # "I gained 123 gold"
<effect_name>_third         # "King John gains 123 gold"
<effect_name>_third_past    # "King John gained 123 gold"
<effect_name>_global 		# King John: "Gains 123 gold"
<effect_name>_global_past 	# King John: "Gained 123 gold"

If you want to provide a custom negation localization, add a '_neg' postfix - primarily for Value changing effects.

<effect_name>_global_neg    # King John: "Lost 123 gold"
```

```mermaid
graph TD
    EL["Effect 本地化键"] --> P["人称<br/>_first / _third / _global"]
    EL --> T["时态<br/>_past"]
    EL --> N["否定<br/>_neg"]

    P --> K1["add_gold_first<br/>我获得 123 金币"]
    P --> K2["add_gold_third<br/>约翰国王获得 123 金币"]
    P --> K3["add_gold_global<br/>约翰国王: 获得 123 金币"]

    T --> K4["add_gold_first_past<br/>我获得了 123 金币"]

    N --> K5["add_gold_global_neg<br/>约翰国王: 失去 123 金币"]

    style EL fill:#2d3f52,stroke:#5b7fa6,color:#fff
```

> **零配置**：只要给出 `<effect_name>_first` 等键，引擎会自动识别，**无需**在 `effect_localization/` 里定义。该目录用于**分组管理**（`_category = { }`）。

---

## 7. Trigger Localization

定义目录：`common/trigger_localization/*.txt`（51 个文件）

详见 [03-触发器与效果](03-触发器与效果.md) 第 8 节。

```paradox
my_trigger = {
	global = <localization_key>    # 无人称："Is an adult"
	first  = <localization_key>    # 第一人称："I am an adult"
	third  = <localization_key>    # 第三人称："[CHARACTER.GetName] is an adult"
}
```

必需的本地化键：

```
<KEY>          # 肯定版
NOT_<KEY>      # 否定版
```

可用 `$COMPARATOR$`（比较运算符的人话）与 `$NUM$`（数值）。

---

## 8. Key 命名约定

```mermaid
graph TD
    K["本地化 Key 命名"] --> E["事件<br/>namespace.number.t / .desc<br/>namespace.number.a / .b"]
    K --> T["特质<br/>trait_XXX<br/>trait_XXX_desc"]
    K --> M["修饰符<br/>modifier_XXX"]
    K --> D["决议<br/>decision_XXX<br/>decision_XXX_desc"]
    K --> O["好感<br/>opinion_XXX"]
    K --> C["文化<br/>culture_XXX<br/>culture_XXX_collective_noun"]
    K --> F["信仰<br/>faith_XXX"]

    style K fill:#2d3f52,stroke:#5b7fa6,color:#fff
```

### 8.1 事件键命名

```
birth.1001.t              # title
birth.1001.desc           # desc
birth.1001.heir.t         # title 变体（继承人的情况）
birth.1001.first_birth_good.desc
birth.1001.a              # option a
birth.1001.b              # option b
```

### 8.2 文件命名

```
<模块名>_l_<语言>.yml
例：
  traits_l_english.yml
  traits_l_simp_chinese.yml
  event_localization/birth_events_l_english.yml
```

> **Mod 建议**：原版用 `l_simp_chinese`，中文 Mod 应同时提供 `localization/simp_chinese/` 目录。

---

## 9. Mod 本地化组织建议

```
for_the_realm/
└── localization/
    ├── english/
    │   ├── ftr_mod_l_english.yml          # Mod 主条目
    │   ├── ftr_traits_l_english.yml
    │   └── ftr_events_l_english.yml
    └── simp_chinese/
        ├── ftr_mod_l_simp_chinese.yml
        ├── ftr_traits_l_simp_chinese.yml
        └── ftr_events_l_simp_chinese.yml
```

**规则**：

1. 每个语言的**文件名可不同**但**键必须一致**
2. 用 `ftr_` 前缀避免与原版键冲突
3. 文件必须 **UTF-8 with BOM**
4. 每个文件只需一个语言头
5. 键名建议全大写 + 下划线

**最小完整示例**：

```yaml
l_simp_chinese:
 ftr_war_tax_name: "征收战争税"
 ftr_war_tax_desc: "在全国范围内征收特别战争税，以充实国库。\n\n#EMP 封臣好感将大幅下降。#!"
 ftr_war_tax_confirm: "确定征收"
 ftr_war_tax_cancel: "算了"

 ftr.0001.t: "战争税"
 ftr.0001.desc: "[ROOT.Char.GetTitledFirstName] 下令征收战争税。"
 ftr.0001.a: "[ROOT.Char.GetHerHis|U] 臣民会理解的。"
 ftr.0001.b: "还是不要冒险了。"
```

---

## 10. 常见错误

| 症状 | 原因 |
|---|---|
| 中文全部乱码 | 文件不是 UTF-8 with BOM |
| 键显示成原始 key 名 | 键拼写不一致 / 语言头写错 |
| 整份文件失效 | YAML 缩进错误（条目未缩进） |
| `|U` 之类的文本原样显示 | 用了中文竖线 `｜` 而不是英文 `\|` |
| 动态取值不生效 | 域链在当前上下文不存在 |
| 事件里 `[ROOT.Char...]` 为空 | 该事件无 root（如 `yearly_global_pulse`） |
| 引号截断 | 字符串内引号未转义 |

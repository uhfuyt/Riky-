# NovelForge v0.1 已知坑(2026-07-03)

## 已修复

1. **章节计数错位**: 原版数磁盘文件,改为 `codex.chapter_count(book)` 读JSON
2. **audit路径错位**: 原版查 `novelforge/chapters/`,改为 `novel/chapters/` (ROOT.parent)
3. **支持双路径**: audit/publish 既接受相对路径也接受绝对路径

## 仍存在(待 v0.2 修)

1. **DEEPSEEK_API_KEY未配置**: 写手Agent是空跑,需用户设环境变量
2. **发布Agent是占位**: `_publish_qidian/fanqie` 函数未实装,需 chrome-cdp-bridge
3. **数据抓取是占位**: `data_scraper.scrape()` 只打印提示,未实际抓
4. **LLM审计prompt没自动调**: `run_auditor` 调 DeepSeek,但要在环境变量有key
5. **番茄codex未初始化**: 只跑了起点migrate,番茄待用户拍板细节

## 设计层面的取舍

- **任务卡来源是 .md**: 如果 .md 改格式,正则要跟着改。**未来: 任务卡改存JSON,直接读**
- **Codex是单文件JSON**: 书多了会重复,3本内 OK,5本+需要拆。
- **审计是同步调用**: 等LLM 10-30秒,主线程卡。**未来: 改成异步队列**
- **章末摘要(200字)**: 当前只在audit里展示,没入库。**未来: 入chapters_meta.summary**

## 用户偏好固化

- **架构先行**: 用户连续两次要求"先把框架规划好"。任何多步工程,开坑前必先问"框架要不要先搭"。
- **不要反问确认**: 用户偏好"做吧/继续"=立即执行。框架本身是用户授权的,不要做之前反复问"要不要做"。

## 关键Bug预防清单(写代码时必查)

写新代码前问自己:
1. ✅ 路径是用 ROOT.parent 还是 ROOT? (novelforge/下的子模块要用 ROOT.parent.joinpath('chapters'))
2. ✅ 章节计数是从 codex JSON 读还是从磁盘数?(必须用 JSON,与 codex.chapter_count 对齐)
3. ✅ audit/publish 是接受相对路径还是绝对路径?(双支持)
4. ✅ DeepSeek API 调失败有 try/except 吗?(`agents.run_writer` 必须有)
5. ✅ state.json 修改是原子写入吗?(目前是直接写,崩溃会丢数据)

## 🩸 v0.2 必修 — 双书 codex 初始化铁律(2026-07-03 血泪,2026-07-03 第二轮)

**触发**: 用户原话"番茄Ch1逻辑漏洞多——5块钱全花光/怀表贴POS机/卡里余额跳跃(5→-495→0→900)/时间线断裂/凑字重复",然后说"整套写小说的流程你再优化下"。

**根因(单一,影响全部)**:
- 番茄 `codex.json` 是**整个从起点模板复制过来的**,只改了 `title` 字段。其他全部是起点内容:
  - `characters` 8个全是"林北辰/林秀芝/赵大海/苏晚晴/周公子/马总"
  - `rules.base_multiple = 10`(应是 200),`rules.level_curve` 全是起点档位
  - `timeline` 主角叫"林北辰",城市"魔都"
  - `world_anchors.city = "魔都"`(应是"深圳")
  - `voice_style.signature_phrases` 全是"我林北辰,穷得只剩运气了"(应是"我顾行舟,穷得只剩花钱这本事了")
  - `hooks` F003是"苏晚晴为何被家族扫地出门"(应是"程晚棠"),F004是"母亲林秀芝的真实身份"
  - `current_state.cash = 11763900.0`(应是5元起步的初始值),`multiple = 10`(应是200)
- **整本番茄书在 bible 写好之后、codex 初始化这一步,完全没有真正独立设计**——只是改了 title 然后开写,结果整本 Ch1 写到崩

**为什么之前没发现**(detector 全失效根因):
- `init_book()` 调用一次就 pass,没人核查返回值字段
- `plausibility.check('fanqie', text, n)`: 番茄 codex.json **本来存在**但跟 bible 完全不一致 → codex.load_book('fanqie') 返回非空但内容是起点版
- 番茄 Ch1 之前是 `codex.load_book('fanqie')` 返回了 None 的空状态 → 提前 return 50 分 → **所有维度不跑** → detector 全部失效 → 全靠人工目测
- 重写后 codex 真填了 → level_curve_score 从 60 升到 90,因为现在数据对得上了

**修复铁律 — 双书 codex 初始化必做 5 步**:
1. ❌ **不允许** `cp qidian/codex.json fanqie/codex.json` 然后改一两个字段
2. ❌ **不允许** `codex.init_book('fanqie', title='X')` 后不填任何字段就开始写章节
3. ✅ **必做**: 写一个独立 `init_<book>.py` 脚本,**逐字段**从 bible + 设定.md 抄入,包括 characters/rules/level_curve/timeline/hooks/voice_style/world_anchors/current_state **每个字段**
4. ✅ **必做**: 跑 `plausibility.check(book, sample_text)` 在生产 Ch1 **前**,验证 codex 已经载入(plausibility check 必须能拿到 `data['rules']`)
5. ✅ **必做**: 跑 `diff-init-bible.py`(待写,v0.2 路线图),对比 `codex.json` 的所有字符串字段跟 `bible.md` 的 5个固定段(角色卡/规则铁律/时间线/伏笔表/数值状态),**任何不匹配 = 报警**

**反例(2026-07-03 番茄 Ch1 全部 bug 根因)**:
- 番茄 Ch1 重写时,level_curve_score 只有 60 → 原因是 codex.level_curve 用的是起点档位
- 番茄 Ch1 全部逻辑漏洞,根因**不是**写作层,是 codex 层跟 bible 层完全不一致 → AI 写章节时不知道规则边界(不知道是 200x 还是 10000x,不知道是 5 块起步还是 100 块起步)
- ✅ 修复方案见 v0.2 路线图

**正向自检动作**(每次双书初始化前必做 checklist):
- [ ] 调 `init_book()` 后,`codex.load_book()` 返回非空?
- [ ] `data['characters']` 全是本本的独立角色(无任何起点角色名)?
- [ ] `data['rules']['base_multiple']` = bible 设定的起步倍数?
- [ ] `data['rules']['level_curve']` 全档是本本独立档?
- [ ] `data['world_anchors']['city']` = 本本独立城市?
- [ ] `data['current_state']['cash']` = 本本 Ch1 起点值?
- [ ] `data['voice_style']['signature_phrases']` 全是本本主角口头禅?
- [ ] 跑 `plausibility.check()` 在 Ch1 前能正常拿 `data['rules']`?

**示例番茄初始化**(对齐 2026-07-03 重写后的《破财转运牌》):
```python
import codex
# ❌ 错: 直接init
# codex.init_book('fanqie', title='X')

# ✅ 对: 一次性全字段填齐(逐字段独立设计,不抄起点)
data = codex.init_book('fanqie', title='破财转运牌:花掉一块来一万',
                         author='Riky', platform='fanqie')
codex.add_character('fanqie', dict(name='顾行舟', role='主角', ...))
codex.add_character('fanqie', dict(name='顾秀芝', role='母亲', ...))
# ... 8个角色全独立命名,无林北辰/林秀芝任何残留
codex.update_rules('fanqie', {
    'trigger': '花得冤的商业行为',
    'base_multiple': 200,  # 起点是10,番茄必须是200
    'level_curve': {'Lv.1': {'multiple': 200, 'upgrade_threshold': 10000, 'daily_quota': 10000}, ...},
    'ban_list': ['赌','毒','黄','骗','传销','洗钱','黑产'],
    ...
})
codex.update_voice_style('fanqie', {
    'signature_phrases': ['我顾行舟,穷得只剩花钱这本事了', ...]
})
codex.update_world_anchors('fanqie', {'city': '深圳'})  # 起点是江城
codex.update_state('fanqie', cash=5.0, multiple=200, level='Lv.1')  # 起点是51.8万
```

## ⚠️ 用户"流程优化"指令 — 元级反馈信号(2026-07-03 焊死)

**触发**: 用户原话"番茄Ch1这么多逻辑漏洞,你怎么写的?一点都不符合逻辑,整套写小说的流程你再优化下"。

**含义**(重要,跟"重做章节"完全不同):
- 用户**不是**让我"重写番茄Ch1"
- 用户**是**在说"你整个生产流程里有 bug,导致 Ch1 这种系统性 bug 才会发生,优化流程"
- 必须以修技能/工具层为主,修章节为辅
- 用户说过"用户对数据造假零容忍,不跑就说跑不动"——所以优化流程时如果发现"codex 全是错的"这种根因,**如实报告根因,不能只粉饰章节**

**正确动作序列**:
1. **根因审计**: 跑检测器看哪些维度全 0 分, 反推到工具层哪个组件失灵
2. **报告用户**: 不只说"Ch1 写崩了",要说"番茄 codex 整个是从起点模板复制过来没改 → 当前 detector 全失效 → 所以 Ch1 没法写得对"
3. **修工具**: 加 detector / 改 init_book 流程 / 加 diff-init-bible 校验
4. **再修章节**: 在工具修好后,重写章节才能产生新质量
5. **验证**: 跑同一段文本看分数从多少升到多少

**反例**:
- ❌ 用户说"流程优化" → AI 只重写章节不修工具 → 下一章 Ch2 又犯同样的逻辑漏洞
- ❌ 用户说"流程优化" → AI 编造"已优化"(实则只改了一个变量名) → 用户说"对数据造假零容忍"被踩雷
- ✅ 用户说"流程优化" → AI 老实报告"番茄 codex 全是错的,数据层就有 bug" → 用户认可后修工具

**关键判断问题**(给未来的 DS-0):
- 用户反复提同样的章节质量问题时 → **别再修章节, 回去修工具**
- 用户说"流程 / 整套 / 系统 / 优化"等元词时 → **元级反馈信号, 修技能层**
- 用户说"重做 ChX" 时 → 具体反馈信号, 修章节层

## v0.2 路线图(更新)

| 优先级 | 项 | 工时 |
|---|---|---|
| 🔴 高 | `_publish_qidian` 实装(CDP) | 半天 |
| 🔴 高 | `_publish_fanqie` 实装(CDP) | 半天 |
| 🔴 **高** | **`diff-init-bible.py` 双书一致性核查脚本** | **2h** |
| 🔴 **高** | **`init_<book>.py` 模板生成器**(从 bible.md 自动生成 codex.json) | **半天** |
| 🔴 **高** | **`codex.init_book()` 必填字段校验**(少填就抛异常) | **1h** |
| 🟡 中 | DeepSeek批产跑通(API key到位) | 1天 |
| 🟡 中 | data_scraper 实装(CDP抓起点后台) | 1天 |
| 🟢 低 | 章末摘要入库(每章+200字) | 2h |
| 🟢 低 | 异步审计队列 | 4h |
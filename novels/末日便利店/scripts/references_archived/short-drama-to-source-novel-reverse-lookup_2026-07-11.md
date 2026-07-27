# 短剧→原著小说反向溯源方法论(2026-07-11 焊死 — 本会话实踩)

> **触发**: 用户问"短剧《末日庇护》是根据什么小说改编的",我**两次**错答:
> - 第 1 次:仅凭小说标题含"末日庇护"四个字,就把飞卢《重生:我在末日庇护全人类》当成原著 → **错**(主角许文七,情节是末世重生+超级庇护系统,与用户描述的"白夜+暴雨+沙丁鱼+房租升级+迁移变船"对不上)
> - 第 2 次:用户提示"先搜短剧内容再找小说",但我用"末日庇护 陈野"猜,又卡住
>
> 最终正确答案:《**末日洪水:我的房屋无限升级**》(一三得七 / 番茄+书旗连载 / 主角白夜),靠**章节名匹配剧情关键词**才锁定。

---

## 🚨 核心铁律(2026-07-11 焊死):**先看短剧内容,再反查原著**

### 用户原话(2026-07-11,踩了两次才纠正)
> "你可以先搜一下短剧的内容,根据这个内容去寻找原著小说"

### 反模式(本会话实踩两次)

| 反模式 | 后果 |
|---|---|
| ❌ 凭小说标题含相同关键词猜 | 飞卢《重生:我在末日庇护全人类》标题含"末日庇护",但剧情完全不是用户描述的暴雨+白夜+沙丁鱼 |
| ❌ 凭演员名猜"末日庇护 短剧男主是陈野" | 把"陈野"当成小说主角,实际是演员名(林晨/白烨/陈野是 3 部不同的末日短剧男主,容易混淆) |
| ❌ 凭"末日庇护所"系列猜 | "末日庇护所" ≠ "末日庇护",前者是《末世庇护所》(夜雨北归客)1059 万字已完结,与用户描述无关 |

### 正模式(workflow)

```
Step 1: 锁定短剧本身的内容信号
        - 平台(番茄/红果/抖音/快手/B站)
        - 主角名(白夜 / 林晨 / 陈野 / 江诚 / 苏辰 ...)
        - 核心爽点关键词(暴雨/沙丁鱼/房租/房屋升级/迁移变船/系统/异能...)
        - 演员名(可能跟主角名不同,需区分)

Step 2: 用"主角名 + 核心爽点"在头条/抖音搜索具体剧情
        - 头条相关搜索词里会出现 "末日庇护 主角 白夜"、"末日庇护 沙丁鱼"
        - 找到剧情描述/章节标题/改编自哪个小说

Step 3: 用章节名匹配小说
        - 小说章节列表 (番茄/书旗/飞卢/起点都有) 列出 30-100 章标题
        - 用户描述的关键词在章节标题里精确出现 → 这就是原著

Step 4: 验证(双向证据链)
        - 小说作者 + 平台 + 字数 + 状态(连载/完结) 与短剧信息是否一致
        - 至少 3 个用户描述的剧情点对应到具体章节标题
```

---

## 📊 搜索关键词矩阵(本会话实证)

### 用户描述拆解
- 平台:番茄
- 主角:白夜
- 题材:暴雨末世
- 关键道具:变异沙丁鱼
- 关键动作:杀怪爆奖励("房租"实际是"房屋升级材料")
- 关键系统:改造图纸、迁移变船

### 命中路径(实际验证)
1. `白夜 暴雨末世 沙丁鱼 房租` → 头条第一条命中书旗网《末日洪水:我的房屋无限升级》简介
2. `末日洪水 房屋无限升级` → 书旗网 bookid=9251783
3. 章节目录精确匹配:
   - 第9章"被感染的住户,变异沙丁鱼!" ←→ 用户"杀变异沙丁鱼"
   - 第10章"沙丁鱼肉,意想不到的收获!" ←→ 用户"爆房租"
   - 第21章"再次外出,摩托艇制作图纸!" ←→ 用户"改造图纸"
   - 第25章"离开小区!变异电鳗!" ←→ 用户"迁移变船"

---

## 🔍 平台搜索 API 速查

| 平台 | 搜索 URL | 反爬 | 备注 |
|---|---|---|---|
| **番茄小说** | `https://fanqienovel.com/search/{query}` | 中等,SPA 渲染,需等 JS | 头条搜索可绕过,SPA 结果抓 body 文本 |
| **书旗小说** | `https://www.shuqi.com/search?keyword={query}` | 较低,SSR | **最容易出结果的入口**,章节列表 SSR 渲染 |
| **飞卢小说** | `https://b.faloo.com/` | 高,搜索 API 经常 404 | 头条搜 "作者名 小说名" 可绕 |
| **起点中文网** | `https://www.qidian.com/search?kw={query}` | 高,需 Cookie | 头条搜小说简介可绕 |
| **头条 so** | `https://so.toutiao.com/search?keyword={query}` | 低,SSR | **最强入口**,能聚合全网小说卡片 + 相关搜索词 |

**核心规律**: 番茄/起点/飞卢的反爬都比头条强,**先在头条搜作者+关键词拿到 bookid/链接**,再去对应平台验证。

---

## 🎭 短剧命名套路(避免被"同名干扰")

网文改编短剧时,标题经常**简化/重命名**以适配短视频传播:

| 小说原名 | 短剧常见改名 |
|---|---|
| 《末日洪水:我的房屋无限升级》 | 《末日庇护》 |
| 《我在永夜打造庇护所》 | 《三千庇护》 |
| 《全球冰封,我打造了末日安全屋》 | 《末日庇护所:我的安全屋》 |
| 《末世庇护所》(夜雨北归客) | 《末日庇护所》(红果短剧) |
| 《重生:我在末日庇护全人类》 | ❌ 还没拍成短剧(本会话误判) |

**反推逻辑**: 短剧标题 = 小说名 + 简化(去掉冒号后内容/合并双名)。在头条/抖音搜"短剧名 原著小说" 通常能得到原著。

---

## ⚠️ 短剧同名干扰陷阱(本会话踩雷)

番茄/抖音上**同名/相似名**短剧一大堆,**短剧名含"末日"俩字**的至少有 5+ 部:

| 短剧名 | 主角 | 原著 |
|---|---|---|
| 末日庇护 | 白夜 | 《末日洪水:我的房屋无限升级》 |
| 末日庇护所 | 狄平 | 《末世庇护所》(夜雨北归客) |
| 末日庇护所:父女情深 | 林峰 | (另一本) |
| 末日庇护所:我的安全屋 | 李长明 | 《全球冰封,我打造了末日安全屋》 |
| 末日庇护所:双生微光 | ? | 《末日庇护所:双生微光》(番茄/爱吃肉肉的兔兔乖) |
| 三千庇护 | 陈凡 | 《我在永夜打造庇护所》(中世纪的兔子) |

**铁律**: **同名/相似名 = 不同原著**,不能凭短剧名撞小说名就下结论。必须用剧情关键词匹配章节。

---

## 🛠 头条搜结果的高价值信号

头条搜索"X 短剧 改编"时,**相关搜索词列表**是金矿:

```
[末日庇护 短剧剧情梗概]    ← 说明确实有这短剧
[末日庇护 主角 白夜]        ← 主角确认
[末日庇护 沙丁鱼]            ← 关键道具
[末日庇护 林晨 短剧]         ← 干扰项(同名的另一部)
```

**用法**: 看到相关搜索词时,把这些词当**新 query**再搜一遍,层层剥开。

---

## 📋 工作流脚本(可直接复用)

### 1. 头条相关搜索词抓取
```python
from playwright.async_api import async_playwright
from urllib.parse import quote

async def get_toutiao_related_queries(query):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.goto(f"https://so.toutiao.com/search?keyword={quote(query)}",
                        wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(5)
        body = await page.locator("body").inner_text()
        # 头条相关搜索词以 "大家都在搜" / "相关搜索" 开头
        related = []
        capture = False
        for line in body.split('\n'):
            line = line.strip()
            if '大家都在搜' in line or '相关搜索' in line:
                capture = True
                continue
            if capture and line and len(line) > 2:
                # 多个查询词连在一起,需要切分
                # 头条格式: 多个词连成一段,无空格
                related.append(line)
        await browser.close()
        return related
```

### 2. 书旗网章节目录抓取(bookid → chapter titles)
```python
async def get_shuqi_chapters(bookid):
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0]
        page = await ctx.new_page()
        await page.goto(f"https://www.shuqi.com/book/{bookid}.html",
                        wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(5)
        body = await page.locator("body").inner_text()
        chapters = []
        for line in body.split('\n'):
            line = line.strip()
            # 书旗格式: "1.第1章 XXX 2.第2章 XXX"
            import re
            matches = re.findall(r'第(\d+)章\s*([^0-9]+?)(?=\d+\.第|$)', line)
            for n, title in matches:
                chapters.append((int(n), title.strip()))
        await browser.close()
        return chapters
```

### 3. 剧情关键词匹配评分
```python
def score_novel_match(chapters, user_keywords):
    """对每个 user_keyword,在 chapters 里搜包含该词的数量"""
    score = 0
    matched = []
    for n, title in chapters:
        for kw in user_keywords:
            if kw in title:
                score += 1
                matched.append((n, title, kw))
    return score, matched

# 用法:
# user_keywords = ["白夜", "暴雨", "沙丁鱼", "房租", "升级", "船"]
# chapters = [(1, "全球洪水..."), (2, "海中怪鱼..."), ..., (25, "离开小区...")]
# score, matched = score_novel_match(chapters, user_keywords)
# 命中率 >= 3 → 这就是原著
```

---

## 🎯 关键教训(2026-07-11 焊死)

1. **不要凭小说标题里的关键词猜原著**。同名/相似名太多,番茄至少 5 部"末日X"短剧。
2. **必须用剧情关键词(主角名 + 核心道具/动作)反向锁源**。
3. **章节目录是终极 fingerprint**。小说前 30 章的标题列表足以做"剧情指纹匹配"。
4. **头条搜结果是中间产物,不是终点**。头条拿到 bookid/链接后,必须去原平台验证。
5. **用户已经看过短剧,TA 给的剧情描述是 ground truth**,**不要替用户重新解读**。

---

## 📌 反查场景速查表

| 用户问 | 反查 workflow |
|---|---|
| "X 短剧是改编哪本小说" | 头条搜"X 短剧 剧情"→ 抓剧情关键词+主角名 → 头条搜"主角名 关键词" → 找到 bookid → 书旗/番茄验证章节标题匹配 |
| "这本小说拍成短剧了吗" | 头条搜"书名 短剧/漫剧" → 看是否有改编信息;查作者其他作品是否被改编 |
| "番茄上 X 短剧原著" | 番茄小说搜小说名 → 找作者 → 头条搜"作者名 改编/漫剧" |
| "短剧里的 X 元素对应小说哪个情节" | bookid + 章节列表 → 用户描述关键词 → 章节标题匹配 → 返回具体章节号 |
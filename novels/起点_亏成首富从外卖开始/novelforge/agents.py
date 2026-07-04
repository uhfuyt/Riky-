# Multi-Agent 流水线 — 5个Agent函数
"""
[DS-0] 5个Agent (2026-07-04升级):
1. 大纲师(outliner) — 我(DS-0)产出
2. 写手(writer) — aipro gemini-3.1-flash-lite API 量产章节 (替代原DeepSeek,因用户提速需求)
3. 审计(auditor) — 同API (独立调一次,做守门员)
4. 润色(polisher) — 我(MiniMax)审+精修文学性,0成本
5. 发布(publisher) — chrome-cdp-bridge / computer-use

每个Agent是纯函数,主控CLI按顺序串接。
日常对话仍走MiniMax-M3主模型,写网文走aipro gemini-3.1-flash-lite API。
"""
import os, json, time, subprocess, re
from pathlib import Path

# === 自动加载 .env(2026-07-04焊死) ===
# 根因: Python子进程不会自动加载 .env,导致 os.environ.get('AIPRO_API_KEY') 返回空
# 修复: agents.py 顶部自动从 /home/admin/.env 加载 (覆盖 default 空值)
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path('/home/admin/.env')
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)  # 不覆盖已有env(允许用户运行时export覆盖)
except ImportError:
    # 没装 python-dotenv 时退化:手动解析 .env
    _ENV_PATH = Path('/home/admin/.env')
    if _ENV_PATH.exists():
        for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k, _v)

import codex, bible, consistency

ROOT = Path(__file__).parent.resolve()
CHAPTERS_DIR = ROOT.parent.joinpath('chapters')

def _chapter_path(book, num, title):
    # 修复bug: chapters_meta title 可能是"第N章"或"待生成"占位 → 落盘文件名重复"第N章"
    # 2026-07-04 修复: 去掉title开头的"第N章"前缀,空title回退到默认名
    safe_title = title.replace('/', '_').replace(' ', '_')[:30]
    safe_title = re.sub(r'^第\d+章[_\s]*', '', safe_title) or f'章节{num}'
    return CHAPTERS_DIR / f"{book}_第{num}章_{safe_title}.md"

# === Agent-1 大纲师 ===
def run_outliner(book, vol_num):
    """大纲师产出卷X细纲 — DS-0手动跑(已写好卷一,后续可半自动)"""
    print(f"[大纲师] 为 [{book}] 生成第{vol_num}卷细纲")
    print("→ 需用户触发,DS-0手动产出,写入 outline/起点_卷X细纲.md")
    print("→ 然后跑: python3 bible.py parse_chapter_tasks 自动入库")

# === Agent-2 写手 ===
def run_writer(book, num):
    """写手Agent:DeepSeek/Claude API 量产章节
    流程:
      1. 加载任务卡
      2. 加载必读上下文
      3. 调用LLM API
      4. 落盘
      5. 触发审计
    """
    task = bible.next_task_card(book, num)
    if not task:
        print(f"❌ 无任务卡 for {book} Ch{num}")
        return
    print(f"\n[写手] [{book}] 第{num}章 {task.get('title','?')}")
    print(f"  钩子: {task.get('hook','?')[:60]}")
    print(f"  爽点: {task.get('pleasure','?')[:60]}")
    
    # 任务卡prompt
    prompt = bible.task_card_prompt(book, num)
    consistency.pre_read_checklist(book, num)
    
    # === 实际调用 aipro gemini-3.1-flash-lite API ===
    api_key = os.environ.get('AIPRO_API_KEY', '')
    base_url = os.environ.get('AIPRO_BASE_URL', 'https://vip.aipro.love/v1')
    model = os.environ.get('AIPRO_DEFAULT_MODEL', 'gemini-3.1-flash-lite')
    if not api_key:
        print("\n⚠️ AIPRO_API_KEY 未设置 — 当前无法调用LLM")
        print("→ 临时方案: 由DS-0直接产出章节正文,手动写到:", _chapter_path(book, num, task.get('title','')))
        return

    # 调用 aipro OpenAI 兼容 chat API
    import urllib.request
    # max_tokens 动态算:字数目标×2.5 (中文1字≈2.5 token) + 200 buffer
    # 起点头3章3000字 → max_tokens=7700, 起点后续1500字 → max_tokens=3950
    # 番茄后续800字 → max_tokens=2200
    word_target = task.get('word_target', 1500)
    # 从task_card_prompt解析 wc_min-wc_max
    import re as _re
    wc_match = _re.search(r'字数目标:\s*(\d+)-(\d+)', prompt)
    if wc_match:
        wc_max = int(wc_match.group(2))
    else:
        wc_max = word_target
    max_tokens = max(2000, int(wc_max * 2.8) + 300)
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': '''你是中国起点中文网/番茄小说网资深男频爽文写手,擅长都市脑洞系统流。

【🔒 不可违反的硬约束】
1. 主角名严格按用户给的角色锁定表,不改名/不编造/不谐音
2. 场景严格接续上一章末尾,禁止重置场景
3. 数值直接引用用户给的JSON,不要自己心算
4. 字数严格在用户给的字数区间内
5. 不写任何日期开头/数据卡/剧透方括号
6. 章末必须有钩子
7. 第一人称"我"视角,口吻贴合角色锁定表里的人设'''},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 1.0,
        'max_tokens': max_tokens
    }).encode()
    req = urllib.request.Request(
        f'{base_url}/chat/completions',
        data=body,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ aipro调用失败: {e}")
        return
    
    # 落盘
    path = _chapter_path(book, num, task.get('title', ''))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    print(f"✅ 已落盘: {path}")
    
    # 触发审计
    print("\n[自动触发审计] ↓")
    audit = consistency.audit_chapter(book, text)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    
    # 注册章节元数据
    codex.register_chapter(book, num, task.get('title', ''), 
                          audit['word_count'], task.get('hook',''))

# === Agent-3 审计 ===
def run_auditor(book, ch_file):
    """独立审计Agent — Claude/DeepSeek 调用"""
    path = CHAPTERS_DIR / ch_file
    if not path.exists():
        print(f"❌ 不存在: {path}")
        return
    text = path.read_text(encoding='utf-8')
    
    # 提取章节号
    import re
    m = re.search(r'第(\d+)章', ch_file)
    num = int(m.group(1)) if m else 0
    
    # 基础审计(本地)
    local = consistency.audit_chapter(book, text)
    print(f"\n[本地审计] verdict={local['verdict']}")
    
    # LLM审计prompt
    prompt = consistency.make_audit_prompt(book, num, text)
    api_key = os.environ.get('AIPRO_API_KEY', '')
    base_url = os.environ.get('AIPRO_BASE_URL', 'https://vip.aipro.love/v1')
    model = os.environ.get('AIPRO_DEFAULT_MODEL', 'gemini-3.1-flash-lite')
    if not api_key:
        print("⚠️ 无API key(AIPRO_API_KEY),跳过LLM审计")
        return

    import urllib.request
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': '你是严格的网文审计员,人设/规则/伏笔/数值任何一项不符都PASS=FAIL。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': 2000
    }).encode()
    req = urllib.request.Request(
        f'{base_url}/chat/completions',
        data=body,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            print("\n【LLM审计报告】")
            print(result['choices'][0]['message']['content'])
    except Exception as e:
        print(f"❌ LLM审计失败: {e}")

# === Agent-4 润色 ===
def run_polisher(book, ch_file):
    """润色Agent — DS-0手动审 + 文学性精修"""
    path = CHAPTERS_DIR / ch_file
    text = path.read_text(encoding='utf-8')
    print(f"[润色] {ch_file} 当前字数: {len(text)}")
    print("→ 需DS-0手动操作:修对话/修爽点/修金句")
    print("→ 完成后手动覆盖文件")

# === Agent-5 发布 ===
def run_publisher(book, ch_file):
    """发布Agent — chrome-cdp-bridge 浏览器自动化"""
    path = CHAPTERS_DIR / ch_file
    if not path.exists():
        print(f"❌ 不存在: {path}")
        return
    text = path.read_text(encoding='utf-8')
    
    platform_url = {
        'qidian': 'https://write.qq.com/write',
        'fanqie': 'https://fanqie.fenqile.com/author'
    }.get(book, '')
    
    print(f"\n[发布Agent] {ch_file} → [{book}]")
    print(f"  平台: {platform_url}")
    print(f"  字数: {len(text)}")
    print(f"  ⚠️ 需用户先在浏览器登录{book}作家后台")
    print(f"  ⚠️ 启动命令: hermes browser_navigate {platform_url}")
    print(f"  ⚠️ 然后调用 browser_type 粘贴正文, browser_click 发布按钮")
    print(f"\n  已注册的发布函数(待补全):")
    print(f"    def _publish_qidian(text): ...")
    print(f"    def _publish_fanqie(text): ...")
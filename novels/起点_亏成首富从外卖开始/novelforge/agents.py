# Multi-Agent 流水线 — 5个Agent函数
"""
[DS-0] 5个Agent:
1. 大纲师(outliner) — 我(DS-0)产出
2. 写手(writer) — DeepSeek 量产章节
3. 审计(auditor) — 独立LLM/Claude 做守门员
4. 润色(polisher) — 我审+精修文学性
5. 发布(publisher) — chrome-cdp-bridge / computer-use

每个Agent是纯函数,主控CLI按顺序串接。
"""
import os, json, time, subprocess
from pathlib import Path
import codex, bible, consistency

ROOT = Path(__file__).parent.resolve()
CHAPTERS_DIR = ROOT.parent.joinpath('chapters')

def _chapter_path(book, num, title):
    safe_title = title.replace('/', '_').replace(' ', '_')[:30]
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
    
    # === 实际调用DeepSeek API ===
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        print("\n⚠️ DEEPSEEK_API_KEY 未设置 — 当前无法调用LLM")
        print("→ 临时方案: 由DS-0直接产出章节正文,手动写到:", _chapter_path(book, num, task.get('title','')))
        return
    
    # 调用DeepSeek chat API
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': '你是起点男频爽文写手,擅长都市脑洞系统流,严格遵循任务卡要求。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 1.1,
        'max_tokens': 4000
    }).encode()
    req = urllib.request.Request(
        'https://api.deepseek.com/chat/completions',
        data=body,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result['choices'][0]['message']['content']
    except Exception as e:
        print(f"❌ DeepSeek调用失败: {e}")
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
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        print("⚠️ 无API key,跳过LLM审计")
        return
    
    import urllib.request
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': '你是严格的网文审计员,人设/规则/伏笔/数值任何一项不符都PASS=FAIL。'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,
        'max_tokens': 2000
    }).encode()
    req = urllib.request.Request(
        'https://api.deepseek.com/chat/completions',
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
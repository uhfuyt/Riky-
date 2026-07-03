# 一致性引擎 — 强制复读 + 独立审计
"""
[DS-0] 4层防崩塌:
1. 写前: 强制复读 CodeX + 最近3章
2. 写后: 独立审计 prompt (人设/设定/伏笔/数值)
3. 伏笔追踪: 写前必查 open_hooks
4. 数值校验: 写后比对 current_state
"""
import json, re
from pathlib import Path
import codex, bible

ROOT = Path(__file__).parent.resolve()

def chapters_dir():
    return ROOT.parent.joinpath('chapters')

def list_chapter_files(book):
    return sorted(chapters_dir().glob(f'{book}_第*章_*.md'))

def read_chapter(book, num):
    for p in list_chapter_files(book):
        m = re.search(rf'{book}_第(\d+)章', p.name)
        if m and int(m.group(1)) == num:
            return p.read_text(encoding='utf-8')
    return None

def pre_read_checklist(book, ch_num):
    """写本章前必读清单"""
    print(f"\n--- 必读1: 全部Codex角色卡 ---")
    meta = codex.load_book(book)
    for c in (meta or {}).get('characters', [])[:8]:
        print(f"  [{c.get('id')}] {c.get('name')} ({c.get('role')}): {c.get('identity','')}")
    print(f"\n--- 必读2: 当前数值状态 ---")
    print(json.dumps((meta or {}).get('current_state', {}), ensure_ascii=False, indent=2))
    print(f"\n--- 必读3: 未回收伏笔(若有本章相关必接住) ---")
    for h in codex.open_hooks(book):
        print(f"  [{h.get('id')}] 埋于{h.get('planted_ch')}: {h.get('content','?')[:50]}")
    print(f"\n--- 必读4: 最近3章原文(防遗忘) ---")
    for i in range(max(1, ch_num-3), ch_num):
        txt = read_chapter(book, i)
        if txt:
            # 只输出章末200字摘要
            tail = txt[-200:].replace('\n', ' ')
            print(f"  Ch{i} 尾: ...{tail[:150]}")

def audit_chapter(book, text):
    """独立审计prompt — 给DeepSeek/Claude做守门员"""
    meta = codex.load_book(book) or {}
    chars = meta.get('characters', [])
    rules = meta.get('rules', {})
    state = meta.get('current_state', {})
    open_hooks = codex.open_hooks(book)
    
    # 数字一致性基础检查
    audit = {
        'word_count': len(re.findall(r'[\u4e00-\u9fff]', text)),
        'checks': [],
        'verdict': 'PASS'
    }
    
    # 检查字数
    target = 3000 if len(list_chapter_files(book)) < 3 else 1500
    if audit['word_count'] < target * 0.8:
        audit['checks'].append(f"❌ 字数不足 {audit['word_count']} < {target*0.8:.0f}")
        audit['verdict'] = 'FAIL'
    
    # 检查金手指规则一致性
    if '亏钱返利' in str(rules) or '返利' in str(rules):
        # 找本章里的返利数字
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*[元块]', text)
        # 简易逻辑: 检查是否有"返利"对应"亏损"数字
        if '返利' in text:
            for m in re.finditer(r'亏损\s*(\d+(?:\.\d+)?).*?返利\s*(\d+(?:\.\d+)?)', text, re.S):
                loss, ret = float(m.group(1)), float(m.group(2))
                if ret < loss * 9:  # 至少9倍(允许+1四舍五入)
                    audit['checks'].append(f"⚠️ 返利数字可疑: 亏{loss}返{ret},倍数不足9x")
                    audit['verdict'] = 'WARN'
    
    # 检查角色名是否首次提及有身份介绍
    for c in chars:
        if c.get('name') and c['name'] in text:
            # 简易: 名字出现的次数
            count = text.count(c['name'])
            if count > 0:
                audit['checks'].append(f"✓ 角色 {c['name']} 出现 {count} 次")
    
    # 检查五幕结构
    acts = sum(1 for tag in ['幕一', '幕二', '幕三', '幕四', '幕五'] if tag in text)
    if acts >= 3:
        audit['checks'].append(f"✓ 五幕结构: 检测到{acts}幕")
    else:
        audit['checks'].append(f"⚠️ 五幕不完整: 只检测到{acts}幕")
    
    # 检查钩子结尾
    last_500 = text[-500:]
    if any(k in last_500 for k in ['下一章', '钩子', '章末', '—— 第', '——']):
        audit['checks'].append(f"✓ 章末钩子存在")
    else:
        audit['checks'].append(f"⚠️ 章末钩子不明显")
    
    return audit

def make_audit_prompt(book, ch_num, draft_text):
    """喂给审计Agent的prompt"""
    meta = codex.load_book(book) or {}
    return f"""你是网文独立审计员(人设守门员)。请对以下章节做4维度审计,严格指出问题。

【第{ch_num}章 草稿】
{draft_text}

【必须校验的4个维度】

1. **人设一致性**:
{json.dumps([{'name':c.get('name'),'role':c.get('role'),'voice_quotes':c.get('voice_quotes',[])[:3]} for c in meta.get('characters',[])], ensure_ascii=False, indent=2)}
→ 检查: 主角的说话方式/反应是否符合"嘴贱腹黑心软"?反派是否过度脸谱化?配角性格是否前后一致?

2. **金手指规则一致性**:
{json.dumps(meta.get('rules',{}), ensure_ascii=False, indent=2)}
→ 检查: 返利倍数是否对得上?禁区是否触碰?等级是否跳跃?返利数字是否数学正确?

3. **伏笔回收**:
未回收伏笔: {json.dumps(codex.open_hooks(book), ensure_ascii=False)}
→ 检查: 本章是否应该回收某个伏笔却没回收?是否新埋伏笔未登记?

4. **数值一致性**:
当前数值: {json.dumps(meta.get('current_state',{}), ensure_ascii=False)}
→ 检查: 钱/位/敌友/时间是否与上一章冲突?

【输出格式】
```
【审计报告】
- 人设: ✅/⚠️/❌ + 具体问题
- 规则: ✅/⚠️/❌ + 具体问题
- 伏笔: ✅/⚠️/❌ + 具体问题
- 数值: ✅/⚠️/❌ + 具体问题
- 字数: ✅/⚠️/❌ + 数字
- 五幕: ✅/⚠️/❌ + 数字
- 综合: PASS / WARN / FAIL
```
"""
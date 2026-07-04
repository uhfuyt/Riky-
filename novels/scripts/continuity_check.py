#!/usr/bin/env python3
"""
承接性detector —— 把每章末态"下一章预告"提到的：人物/地点/事件/数值
跟下一章首段（300字内）是否承接做交叉验证。

输出: 每章 1行 报告 PASS/WARN/FAIL
"""
import os, re, json, sys

CHAPTERS_DIR = "/home/admin/.hermes/mempalace/novel/chapters"
BOOKS = {
    "起点_": "起点_亏成首富从外卖开始",
    "番茄_": "番茄_破财转运牌",
}

def get_promise(chapter_path):
    """提取章节末态"下一章预告/钩子"""
    content = open(chapter_path).read()
    m = re.search(r'下一章(?:预告|钩子)[：:](.+?)(?:\n|$)', content)
    if m:
        return m.group(1).strip()
    return ""

def get_chapter_meta(chapter_path):
    """提取章节首段300字 + 章名"""
    content = open(chapter_path).read()
    lines = content.split('\n')
    title = ""
    for line in lines[:5]:
        if line.startswith('# '):
            title = line[2:].strip()
            break
    body_start = re.sub(r'^# .+\n', '', content)
    return title, body_start[:300]

def extract_entities(text):
    """简单实体提取"""
    entities = set()
    # 人名
    for m in re.finditer(r'([林顾钱周王张苏程沈何][\u4e00-\u9fa5]{1,2})', text):
        ent = m.group(1)
        if ent not in {'林总','林叔','林北','林建业','顾行'}:
            entities.add(ent)
    # 数字
    for m in re.finditer(r'(\d+(?:[千万亿]|\.\d+)?)', text):
        entities.add(m.group(1))
    # 关键词
    for kw in ['便利店', '理发店', '王氏建材', '春风帮扶会', '铂尔曼', '汉庭府',
               '江城日报', '破财转运', '和解金', '王大龙', '王建国', '周映雪',
               '何秀兰', '暖暖', '王小川', '林建业', '钱小宝', '程晚棠',
               '苏婉清', '张德彪']:
        if kw in text:
            entities.add(kw)
    return entities

def check_pair(prev_path, curr_path):
    promise = get_promise(prev_path)
    title, head = get_chapter_meta(curr_path)
    if not promise:
        return "PREV:无承诺", []
    p_entities = extract_entities(promise)
    h_entities = extract_entities(head)
    matched = p_entities & h_entities
    missing = p_entities - h_entities
    return f"承诺{len(p_entities)}承接词 vs 命中{len(matched)}", missing

# 跑全部
total_pass = total_warn = total_fail = 0
for prefix, book_name in BOOKS.items():
    chapters_full = [f for f in os.listdir(CHAPTERS_DIR)
                        if f.startswith(prefix) and not f.startswith('_archive')]
    # 按章节号排序（不是按文件名字符串）
    def chapter_num(name):
        m = re.search(r'第(\d+)章', name)
        return int(m.group(1)) if m else 0
    chapters = sorted(chapters_full, key=chapter_num)
    print(f"\n{'='*60}")
    print(f"📚 {book_name}")
    print(f"{'='*60}")
    for i, cf in enumerate(chapters):
        if i == 0:
            print(f"  Ch1 起始章（前章承诺 N/A）")
            continue
        prev_cf = chapters[i-1]
        prev_path = os.path.join(CHAPTERS_DIR, prev_cf)
        curr_path = os.path.join(CHAPTERS_DIR, cf)
        result, missing = check_pair(prev_path, curr_path)
        status = "✅" if len(missing) == 0 else "⚠️ "
        if len(missing) > 3:
            status = "❌"
        print(f"  {status} {prev_cf} → {cf} | {result} | 缺:{list(missing)[:5]}")
        if status == "✅": total_pass += 1
        elif status == "⚠️ ": total_warn += 1
        elif status == "❌": total_fail += 1

print(f"\n{'='*60}")
print(f"📊 总结: ✅ {total_pass} | ⚠️  {total_warn} | ❌ {total_fail}")
print(f"{'='*60}")

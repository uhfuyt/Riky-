#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标题统一 + 分节残留清理
规则:
  1. 第一行统一为 '# 第NNN章 <标题>' (阿数零填充, 标题取自文件名)
  2. 删除第二行重复标题 '## 第NNN章 ...' (Ch1-12/21-30 双标题)
  3. 删除孤立分节残留 '## 一'~'## 十' (Ch13-20 共39处)
  4. 第一行 '## 一' 开头(Ch13-20正文首行) 一并处理
用法: python3 unify_titles.py   (在 chapters/ 下运行)
"""
import re, os, shutil

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f): return int(re.search(r'第(\d+)章', f).group(1))
files.sort(key=chnum)

BACKUP = '/tmp/title_backup'
os.makedirs(BACKUP, exist_ok=True)

CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12,
          '十三':13,'十四':14,'十五':15,'十六':16,'十七':17,'十八':18,'十九':19,'二十':20,
          '二十一':21,'二十二':22,'二十三':23,'二十四':24,'二十五':25,'二十六':26,'二十七':27,
          '二十八':28,'二十九':29,'三十':30,'三十一':31,'三十二':32,'三十三':33,'三十四':34,
          '三十五':35,'三十六':36,'三十七':37,'三十八':38,'三十九':39,'四十':40,'四十一':41,
          '四十二':42,'四十三':43,'四十四':44,'四十五':45,'四十六':46,'四十七':47,'四十八':48,
          '四十九':49,'五十':50,'五十一':51,'五十二':52,'五十三':53,'五十四':54,'五十五':55,
          '五十六':56,'五十七':57,'五十八':58,'五十九':59,'六十':60,'六十一':61,'六十二':62,
          '六十三':63,'六十四':64,'六十五':65,'六十六':66,'六十七':67,'六十八':68,'六十九':69,
          '七十':70,'七十一':71,'七十二':72,'七十三':73,'七十四':74,'七十五':75,'七十六':76,
          '七十七':77,'七十八':78,'七十九':79,'八十':80,'八十一':81,'八十二':82,'八十三':83,
          '八十四':84,'八十五':85,'八十六':86,'八十七':87,'八十八':88,'八十九':89,'九十':90,
          '九十一':91,'九十二':92,'九十三':93,'九十四':94,'九十五':95,'九十六':96,'九十七':97,
          '九十八':98,'九十九':99,'一百':100,'一百零一':101,'一百零二':102,'一百零三':103,
          '一百零四':104,'一百零五':105,'一百零六':106,'一百零七':107,'一百零八':108,'一百零九':109,
          '一百一十':110,'一百一十一':111,'一百一十二':112,'一百一十三':113,'一百一十四':114,
          '一百一十五':115,'一百一十六':116,'一百一十七':117,'一百一十八':118,'一百一十九':119,
          '一百二十':120}

def get_title_from_filename(f):
    m = re.search(r'第\d+章_(.+)\.md$', f)
    return m.group(1) if m else ''

changed, skipped = [], []
for f in files:
    n = chnum(f)
    title = get_title_from_filename(f)
    text = open(f, encoding='utf-8').read()
    orig = text
    lines = text.split('\n')

    # 1. 处理第一行：找出所有 '# xxx' 标题行，重写为 '# 第NNN章 <title>'
    #    先收集非空行中所有 markdown 标题行
    new_lines = []
    first_title_done = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('# ') and not first_title_done:
            # 第一行标题 → 标准格式
            new_lines.append(f'# 第{n:03d}章 {title}')
            first_title_done = True
            continue
        if s.startswith('## 第') and re.match(r'## 第\d+章', s):
            # 重复标题(第二行) → 删除
            continue
        if re.match(r'^## [一二三四五六七八九十]$', s):
            # 孤立分节残留 → 删除
            continue
        new_lines.append(line)

    new_text = '\n'.join(new_lines)
    # 清理多空行
    new_text = re.sub(r'\n{3,}', '\n\n', new_text)
    if new_text != orig:
        shutil.copy2(f, os.path.join(BACKUP, f))
        open(f, 'w', encoding='utf-8').write(new_text)
        changed.append(n)
    else:
        skipped.append(n)

print(f'✅ 已处理 {len(changed)} 章: {changed}')
print(f'跳过(无变化): {skipped}')
print(f'备份: {BACKUP}')

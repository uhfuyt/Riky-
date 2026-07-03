#!/usr/bin/env python3
"""一次性迁移脚本:把已有的起点 outline/*.md 文件解析成 codex.json"""
import json, re, os, sys
from pathlib import Path

# 切到 novelforge 目录
NF = Path(__file__).parent.resolve()
sys.path.insert(0, str(NF))
import codex, bible

# 智能找大纲目录:novelforge/../大纲设定/ (桌面布局) 或 novelforge/../outline/ (服务器布局)
OUTLINE_DIR = NF.parent.joinpath('大纲设定')
if not OUTLINE_DIR.exists():
    OUTLINE_DIR = NF.parent.joinpath('outline')

def main():
    book = 'qidian'
    
    # 1. 读设定
    set_path = OUTLINE_DIR / '起点_亏成首富从外卖开始_设定.md'
    main_outline = OUTLINE_DIR / '起点_主线大纲.md'
    if not set_path.exists():
        print(f"❌ 缺文件: {set_path}")
        return
    
    # 2. 初始化codex
    data = codex.init_book(book, 
                          title='亏成首富从外卖开始',
                          author='林北舟',
                          platform='qidian')
    
    # 3. 解析设定.md 提取角色/规则/数值
    text = set_path.read_text(encoding='utf-8')
    
    # 规则
    rules = {
        'trigger': '商业行为净亏损',
        'base_multiple': 10,
        'level_thresholds': {'Lv.2': 10000, 'Lv.3': 100000, 'Lv.4': 1000000, 'Lv.5': 10000000},
        'ban_list': ['赌', '毒', '黄', '骗', '传销', '洗钱'],
        'source': '系统生成,直接到账个人银行账户',
        'side_effect': 'Lv.5后"想亏"本能压过"想赚"'
    }
    data['rules'] = rules
    
    # 角色
    data['characters'] = [
        {'id': 'c001', 'name': '林北舟', 'role': '主角', 'age': 28,
         'identity': '前互联网大厂P7,现外卖骑手',
         'personality': '嘴贱、腹黑、心软、极度务实',
         'voice_quotes': ['赚什么赚,我亏钱呢', '您别买,真别买,求求您了', '系统大大,加大力度啊'],
         'hidden_attrs': {'data_sensitivity': 5, 'business_acumen': 5, 'mouth_cannon': 5},
         'relations': {'ex_wife': '苏婉清', 'mother': '何秀兰', 'rival': '王大龙'}},
        {'id': 'c002', 'name': '苏婉清', 'role': '前妻', 'age': 27,
         'identity': '前鹅厂运营经理,现嫁王大龙',
         'personality': '现实、要强、有愧',
         'relations': {'ex_husband': '林北舟', 'current_husband': '王大龙'}},
        {'id': 'c003', 'name': '王大龙', 'role': '反派·前妻现任', 'age': 31,
         'identity': '江城首富之子',
         'personality': '跋扈、虚荣、嫉妒心强',
         'relations': {'wife': '苏婉清', 'father': '老王总'}},
        {'id': 'c004', 'name': '张德彪', 'role': '外卖站长', 'age': 45,
         'identity': '美团江城站站长',
         'personality': '贪小便宜、看人下菜',
         'relations': {}},
        {'id': 'c005', 'name': '何秀兰', 'role': '母亲', 'age': 58,
         'identity': '菜市场卖菜',
         'personality': '善良、节俭、不知主角现状',
         'relations': {'son': '林北舟'}},
        {'id': 'c006', 'name': '马化腾', 'role': '系统本体(化名)', 'age': '?',
         'identity': 'Lv.10后露面',
         'personality': '神秘',
         'relations': {}},
    ]
    
    # 数值
    data['current_state'] = {
        'cash': 623.50,
        'debt': 500000,
        'cumulative_loss': 0,
        'cumulative_return': 0,
        'level': 'Lv.1',
        'multiple': 10,
        'positions': [],
    }
    
    # 地理锚点
    data['world_anchors'] = {
        'city': '江城市(虚构三线小城,靠近南京)',
        'apartment': '江城花园小区,月租1200',
        'work': '美团外卖江城站(雨花区)',
        'mother_home': '江北新区,菜市场旁老小区',
        'rival_business': '江城建材城(王大龙家族)'
    }
    
    # 风格
    data['voice_style'] = {
        'tone': '都市脑洞·男频爽文·反套路',
        'voice': '主角嘴贱腹黑心软',
        'avg_sentence_len': '15-25字',
        'banned_words': [],
        'signature_phrases': [
            '赚什么赚,我亏钱呢',
            '您别买,真别买',
            '系统大大,加大力度',
            '又是想让我赚钱的一天,真烦'
        ],
        'pleasure_density': '每5章1个小高潮,每20章1个中高潮',
        'hook_density': '每章末必有钩子,3钩子起步'
    }
    
    # 时间线
    data['timeline'] = [
        {'date': '2026-04-15', 'event': '林北舟二次被优化', 'ch': None},
        {'date': '2026-05-20', 'event': '累计债务50万', 'ch': None},
        {'date': '2026-06-02', 'event': '苏婉清提出离婚', 'ch': None},
        {'date': '2026-06-28', 'event': '协议离婚', 'ch': None},
        {'date': '2026-07-01', 'event': '回到江城,余额623.50', 'ch': None},
        {'date': '2026-07-02', 'event': '第一单外卖,系统激活', 'ch': 1},
    ]
    
    # 伏笔
    data['hooks'] = [
        {'id': 'F001', 'planted_ch': 1, 'content': '系统"为什么选我"提示',
         'planned_redeem_ch': '第二卷末', 'status': 'planted'},
        {'id': 'F002', 'planted_ch': 2, 'content': '女儿暖暖"爸爸什么时候回来"',
         'planned_redeem_ch': '第一卷中段', 'status': 'planted'},
        {'id': 'F003', 'planted_ch': 3, 'content': '王大龙"我爸和马总关系好"',
         'planned_redeem_ch': '第二卷揭露马化腾', 'status': 'planted'},
        {'id': 'F004', 'planted_ch': 8, 'content': '母亲收到神秘汇款',
         'planned_redeem_ch': '第一卷末解释(主角返利钱)', 'status': 'planted'},
    ]
    
    codex.save_book(book, data)
    print(f"✅ Codex初始化: {book}")
    print(f"   角色{len(data['characters'])}人 / 伏笔{len(data['hooks'])}条 / 时间线{len(data['timeline'])}条")
    
    # 4. 解析卷一细纲 → 任务卡
    tasks = bible.parse_chapter_tasks(book)
    print(f"✅ 章节任务卡: {len(tasks)} 张已入库")
    
    # 5. 注册已有第1章
    codex.register_chapter(book, 1, '系统激活', 3330, '系统的"亏损"判定边界')
    print(f"✅ 第1章元数据已注册")
    
    print("\n=== 迁移完成 ===")
    print("下一步: python3 novelforge.py status")

if __name__ == '__main__':
    main()
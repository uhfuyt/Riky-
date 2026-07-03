# 数据闭环 — 起点/番茄数据抓取 + 反馈分析
"""
[DS-0] 抓取:
- 起点: 作家中心后台的章节数据(在读/追读/收藏/推荐票/评论)
- 番茄: 番茄作家助手 web 版数据

存储:
- data/{book}/{date}_stats.json
- data/feedback/{book}_comments.jsonl
"""
import json, time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()

def scrape(book):
    """抓取入口 — 待接入 chrome-cdp-bridge 或 API"""
    today = datetime.now().strftime('%Y%m%d')
    out_dir = ROOT / book
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[抓取] {book} - {today}")
    print(f"  ⚠️ 当前为占位,需 chrome-cdp-bridge 接入:")
    
    if book == 'qidian':
        print(f"  → 起点作家中心: https://write.qq.com/portal/work")
        print(f"  → 数据点: 在读/追读率/收藏/推荐票/本周字数/签约状态")
    elif book == 'fanqie':
        print(f"  → 番茄作家后台: https://fanqie.fenqile.com/author")
        print(f"  → 数据点: 在读/读完率/广告分成/全勤达标/签约状态")
    
    print(f"\n  抓取后落盘: {out_dir}/{today}_stats.json")
    print(f"  评论落盘: {ROOT.parent}/feedback/{book}_comments.jsonl")

def analyze_feedback(book):
    """反馈分析 — 提取爽点/抱怨关键词,生成节奏调整建议"""
    feedback_file = ROOT.parent / 'feedback' / f'{book}_comments.jsonl'
    if not feedback_file.exists():
        print(f"⚠️ 无反馈数据: {feedback_file}")
        return
    print(f"[反馈分析] {book}")
    # TODO: 调用LLM做关键词提取

def adjust_pleasure_density(book, target_chapter):
    """根据最近N章反馈,动态调整爽点密度"""
    print(f"[爽点调整] {book} Ch{target_chapter}")
    print(f"  → 若完读<30%: 提高爽点密度+章末钩子强度")
    print(f"  → 若抱怨'太水': 砍掉过渡章,合并剧情")
    print(f"  → 若收藏增速快: 维持当前节奏")
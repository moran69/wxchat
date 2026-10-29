#!/usr/bin/env python3
"""列出消息量最多的联系人"""
import os, sys, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wxlib

t0 = time.time()
convs = wxlib.scan_conversations()
print(f"会话总数 {len(convs)}  耗时 {time.time()-t0:.1f}s\n")
print(f"{'#':>3} {'消息数':>8} {'联系人':<18} {'用户名':<34} {'首条':<11} {'末条':<11} 群")
for i, c in enumerate(convs[:40], 1):
    f = datetime.fromtimestamp(c["first"]).strftime("%Y-%m-%d") if c["first"] else "-"
    l = datetime.fromtimestamp(c["last"]).strftime("%Y-%m-%d") if c["last"] else "-"
    print(f"{i:>3} {c['cnt']:>8} {c['name'][:17]:<18} {c['username'][:33]:<34} {f:<11} {l:<11} {'群' if c['is_room'] else ''}")

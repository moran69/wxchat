#!/usr/bin/env python3
"""按联系人聚合（跨分库 message_0~5 合并）"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wxlib

convs = wxlib.scan_conversations()
agg = {}
for c in convs:
    a = agg.setdefault(c["username"], {"name": c["name"], "cnt": 0, "first": 10**12, "last": 0,
                                       "shards": [], "is_room": c["is_room"]})
    a["cnt"] += c["cnt"]
    a["first"] = min(a["first"], c["first"] or a["first"])
    a["last"] = max(a["last"], c["last"] or 0)
    a["shards"].append((c["db"].replace("message_", "m").replace(".db", ""), c["table"]))

rows = sorted(agg.items(), key=lambda kv: kv[1]["cnt"], reverse=True)
dms = [(u, a) for u, a in rows if not a["is_room"]]
rooms = [(u, a) for u, a in rows if a["is_room"]]

def fmt(a):
    f = datetime.fromtimestamp(a["first"]).strftime("%Y-%m") if a["first"] < 10**12 else "-"
    l = datetime.fromtimestamp(a["last"]).strftime("%Y-%m") if a["last"] else "-"
    return f"{f}~{l}"

print(f"=== 私聊 Top 25（共 {len(dms)} 个）===")
print(f"{'#':>3} {'总消息':>8} {'联系人':<14} {'wxid':<26} {'跨度':<16} 分片")
for i, (u, a) in enumerate(dms[:25], 1):
    print(f"{i:>3} {a['cnt']:>8} {a['name'][:13]:<14} {u[:25]:<26} {fmt(a):<16} {len(a['shards'])}")

print(f"\n=== 群聊 Top 10（共 {len(rooms)} 个）===")
print(f"{'#':>3} {'总消息':>8} {'群名':<22} {'跨度':<16} 分片")
for i, (u, a) in enumerate(rooms[:10], 1):
    print(f"{i:>3} {a['cnt']:>8} {a['name'][:21]:<22} {fmt(a):<16} {len(a['shards'])}")

tot = sum(a["cnt"] for _, a in rows)
print(f"\n总消息 {tot:,} 条 / 会话 {len(rows)} 个")

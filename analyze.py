#!/usr/bin/env python3
"""导出 + 定量分析某个联系人的微信聊天记录"""
import os, sys, json, re, statistics, time
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wxlib

if len(sys.argv) < 2:
    sys.exit("用法: python3 analyze.py <wxid 或 备注名>")
TARGET = sys.argv[1]
if not TARGET.startswith("wxid_") and "@" not in TARGET:
    # 允许直接传备注名/群名，按显示名唯一匹配到 wxid
    hits = [c for c in wxlib.scan_conversations() if c["name"] == TARGET]
    if len(hits) == 1:
        TARGET = hits[0]["username"]
        print(f"按名称匹配到: {TARGET}")
    elif len(hits) > 1:
        sys.exit(f"「{TARGET}」匹配到 {len(hits)} 个会话，请改用 wxid")
    else:
        sys.exit(f"未找到名为「{TARGET}」的会话")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

t0 = time.time()
convs = [c for c in wxlib.scan_conversations() if c["username"] == TARGET]
NAME = convs[0]["name"] if convs else TARGET
print(f"目标: {NAME} ({TARGET})  分片 {len(convs)}")

msgs = []
for c in convs:
    rows = wxlib.fetch_messages(TARGET, table=c["table"], dbname=c["db"])
    msgs.extend(rows)
    print(f"  {c['db']} {c['table'][:14]} -> {len(rows)}")
msgs.sort(key=lambda x: x["t"] or 0)
# 去重（分片重叠）
seen, uniq = set(), []
for m in msgs:
    k = (m["t"], m["sid"], m["text"][:40])
    if k in seen:
        continue
    seen.add(k)
    uniq.append(m)
msgs = uniq
print(f"合计 {len(msgs):,} 条（去重后），耗时 {time.time()-t0:.1f}s")

# ─── 导出 ───
with open(f"{OUT}/chat_{TARGET}.jsonl", "w", encoding="utf-8") as f:
    for m in msgs:
        f.write(json.dumps({"t": m["t"], "time": datetime.fromtimestamp(m["t"]).strftime("%Y-%m-%d %H:%M:%S"),
                            "from": "我" if m["is_self"] else NAME, "kind": m["kind"],
                            "text": m["text"]}, ensure_ascii=False) + "\n")

# ─── 基础统计 ───
S = {}
S["name"] = NAME
S["total"] = len(msgs)
if not msgs:
    print("无消息"); sys.exit(0)
S["first"] = datetime.fromtimestamp(msgs[0]["t"]).strftime("%Y-%m-%d %H:%M")
S["last"] = datetime.fromtimestamp(msgs[-1]["t"]).strftime("%Y-%m-%d %H:%M")
span_days = (msgs[-1]["t"] - msgs[0]["t"]) / 86400
S["span_days"] = round(span_days, 1)
S["span_years"] = round(span_days / 365, 2)

mine = [m for m in msgs if m["is_self"]]
hers = [m for m in msgs if not m["is_self"]]
S["mine"] = len(mine)
S["hers"] = len(hers)
S["ratio"] = f"{len(mine)/len(hers):.2f}:1" if hers else "n/a"
S["per_day"] = round(len(msgs) / max(span_days, 1), 1)

# 类型
kinds = Counter(m["kind"] for m in msgs)
S["kinds"] = dict(kinds)
S["types"] = Counter(m["type"] for m in msgs).most_common(8)

# 按年 / 月
yr = Counter(); yrm = Counter(); yrm_mine = Counter(); yrm_hers = Counter()
hour_mine = Counter(); hour_hers = Counter()
wd = Counter()
for m in msgs:
    dt = datetime.fromtimestamp(m["t"])
    y = dt.year
    yr[y] += 1
    yrm[dt.strftime("%Y-%m")] += 1
    (yrm_mine if m["is_self"] else yrm_hers)[dt.strftime("%Y-%m")] += 1
    (hour_mine if m["is_self"] else hour_hers)[dt.hour] += 1
    wd[dt.weekday()] += 1
S["by_year"] = {str(k): v for k, v in sorted(yr.items())}
S["by_month"] = dict(sorted(yrm.items()))
S["by_month_mine"] = dict(sorted(yrm_mine.items()))
S["by_month_hers"] = dict(sorted(yrm_hers.items()))
S["hour_mine"] = {str(h): hour_mine.get(h, 0) for h in range(24)}
S["hour_hers"] = {str(h): hour_hers.get(h, 0) for h in range(24)}
S["weekday"] = {str(k): wd.get(k, 0) for k in range(7)}

# 文本长度
def lens(ms):
    return [len(m["text"]) for m in ms if m["kind"] == "text" and m["text"]]
lm, lh = lens(mine), lens(hers)
def pct(a, p):
    if not a: return 0
    a = sorted(a); return a[min(len(a)-1, int(len(a)*p))]
S["len_mine"] = {"avg": round(statistics.mean(lm), 1) if lm else 0, "median": pct(lm, .5), "p90": pct(lm, .9), "max": max(lm) if lm else 0}
S["len_hers"] = {"avg": round(statistics.mean(lh), 1) if lh else 0, "median": pct(lh, .5), "p90": pct(lh, .9), "max": max(lh) if lh else 0}

# 回复延迟（对方发完后我的下一条，<=6h 视为回复）
lat_mine, lat_hers = [], []
for i in range(1, len(msgs)):
    prev, cur = msgs[i-1], msgs[i]
    if prev["is_self"] == cur["is_self"]:
        continue
    gap = cur["t"] - prev["t"]
    if 0 <= gap <= 6*3600:
        (lat_mine if cur["is_self"] else lat_hers).append(gap)
S["lat_mine"] = {"median": round(pct(lat_mine, .5)/60, 1), "avg": round(statistics.mean(lat_mine)/60, 1) if lat_mine else 0,
                 "p90": round(pct(lat_mine, .9)/60, 1), "n": len(lat_mine)}
S["lat_hers"] = {"median": round(pct(lat_hers, .5)/60, 1), "avg": round(statistics.mean(lat_hers)/60, 1) if lat_hers else 0,
                 "p90": round(pct(lat_hers, .9)/60, 1), "n": len(lat_hers)}
S["lat_mine_5min"] = round(sum(1 for x in lat_mine if x <= 300)/max(len(lat_mine), 1)*100, 1)
S["lat_hers_5min"] = round(sum(1 for x in lat_hers if x <= 300)/max(len(lat_hers), 1)*100, 1)

# 会话切分（间隔 > 30min 算新会话）
sessions, cur = [], [msgs[0]]
for i in range(1, len(msgs)):
    if msgs[i]["t"] - msgs[i-1]["t"] > 1800:
        sessions.append(cur); cur = [msgs[i]]
    else:
        cur.append(msgs[i])
sessions.append(cur)
S["sessions"] = len(sessions)
S["msgs_per_session"] = round(len(msgs)/len(sessions), 1)
S["session_len_min"] = round(statistics.median([(s[-1]["t"]-s[0]["t"])/60 for s in sessions]), 1)

# 日活
days = Counter(datetime.fromtimestamp(m["t"]).strftime("%Y-%m-%d") for m in msgs)
S["active_days"] = len(days)
S["active_day_ratio"] = round(len(days)/max(span_days, 1)*100, 1)
S["top_days"] = days.most_common(8)

# 沉默期
gaps = []
for i in range(1, len(msgs)):
    g = msgs[i]["t"] - msgs[i-1]["t"]
    if g > 86400:
        gaps.append((round(g/86400, 1), datetime.fromtimestamp(msgs[i-1]["t"]).strftime("%Y-%m-%d"),
                     datetime.fromtimestamp(msgs[i]["t"]).strftime("%Y-%m-%d")))
gaps.sort(reverse=True)
S["silences"] = gaps[:6]
S["silence_avg"] = round(sum(g for g, _, _ in gaps)/len(gaps), 1) if gaps else 0
S["silence_n"] = len(gaps)

# 谁先开口 / 谁最后说话（按天）
first_by = Counter(); last_by = Counter()
day_first = {}
day_last = {}
for m in msgs:
    d = datetime.fromtimestamp(m["t"]).strftime("%Y-%m-%d")
    if d not in day_first:
        day_first[d] = m
    day_last[d] = m
for d, m in day_first.items():
    first_by["我" if m["is_self"] else NAME] += 1
for d, m in day_last.items():
    last_by["我" if m["is_self"] else NAME] += 1
S["first_speaker"] = dict(first_by)
S["last_speaker"] = dict(last_by)
S["goodnight"] = {"我": sum(1 for d, m in day_last.items() if m["is_self"]),
                  NAME: sum(1 for d, m in day_last.items() if not m["is_self"])}

# 文本内容分析
texts = [m for m in msgs if m["kind"] == "text" and m["text"]]
CJK = re.compile(r"[\u4e00-\u9fa5]+")
STOP = set("的 了 是 我 你 他 她 它 在 不 吗 呢 啊 吧 就 都 也 和 要 会 有 这 那 个 什 么 嗯 哦 哈 呀 嘛 呗 把 被 给 地 得 着 过 之 与 或 但 而 又 还 很 太 好 吗 我 我们 你们 他们 现在 时候 一个 什么 怎么 可以 没有 知道 就是 这个 那个 但是 因为 所以 觉得 可能 真的 一下 一样 还是 已经 自己 不是 有点".split())
EMO = re.compile(r"\[[^\[\]]{1,6}\]")
try:
    import jieba
    jieba.setLogLevel(60)
    _JIEBA = True
except Exception:
    _JIEBA = False

def words_of(ms, minlen=2):
    """jieba 分词优先；无 jieba 时退化为 2-3 字 n-gram"""
    c = Counter()
    for m in ms:
        if m["kind"] != "text":
            continue
        t = EMO.sub("", m["text"] or "")
        # 笑声/附和归一，避免被 jieba 切碎
        t = re.sub(r"哈{2,}", "哈哈", t)
        t = re.sub(r"嗯{2,}", "嗯嗯", t)
        t = re.sub(r"哦{2,}", "哦哦", t)
        if _JIEBA:
            for w in jieba.cut(t):
                w = w.strip()
                if len(w) >= minlen and w not in STOP and CJK.fullmatch(w):
                    c[w] += 1
        else:
            for run in CJK.findall(t):
                for n in (2, 3):
                    for i in range(len(run) - n + 1):
                        g = run[i:i+n]
                        if g not in STOP:
                            c[g] += 1
    return c

def prune(counter, topn=120):
    items = counter.most_common(4000)
    d = dict(items)
    keep = []
    for g, c in items:
        if c < 12: break
        if any(g != h and g in h and hc >= c * 0.8 for h, hc in items[:300] if len(h) > len(g)):
            continue
        if not _JIEBA and len(g) == 3 and g[:2] != g[1:] and d.get(g[:2], 0) >= c * 0.8 and d.get(g[1:], 0) >= c * 0.8:
            continue
        keep.append((g, c))
        if len(keep) >= topn: break
    return keep

S["top_phrases"] = prune(words_of(msgs), 60)
S["top_phrases_mine"] = prune(words_of(mine), 25)
S["top_phrases_hers"] = prune(words_of(hers), 25)

# 关键词命中
KEY = ["想你", "晚安", "早安", "爱你", "老公", "老婆", "宝宝", "宝贝", "吃饭", "回家", "睡", "累", "生气",
       "对不起", "谢谢", "好的", "哈哈", "么么", "亲亲", "抱抱", "想见你", "见面", "买", "钱", "上班", "下班",
       "考试", "工作", "妈妈", "爸爸", "结婚", "喜欢", "讨厌", "不理", "分手", "吵架", "哭"]
S["keywords"] = {k: sum(1 for m in texts if k in m["text"]) for k in KEY}
S["keywords"] = dict(sorted(S["keywords"].items(), key=lambda kv: -kv[1]))

# 表情 [xxx]
emojis = Counter()
for m in texts:
    for e in re.findall(r"\[[^\[\]]{1,6}\]", m["text"]):
        emojis[e] += 1
S["emoji_top"] = emojis.most_common(15)
S["emoji_total"] = sum(emojis.values())

# 分年度快照
yearly = {}
for y in sorted(yr):
    a = [m for m in msgs if datetime.fromtimestamp(m["t"]).year == y]
    am = [m for m in a if m["is_self"]]
    lat = []
    for i in range(1, len(a)):
        if a[i-1]["is_self"] != a[i]["is_self"]:
            g = a[i]["t"] - a[i-1]["t"]
            if 0 <= g <= 6*3600: lat.append(g)
    d = Counter(datetime.fromtimestamp(m["t"]).strftime("%Y-%m-%d") for m in a)
    yearly[y] = {"n": len(a), "mine": len(am), "ratio": round(len(am)/max(len(a)-len(am),1), 2),
                 "days": len(d), "per_day": round(len(a)/max(len(d),1), 1),
                 "lat_med": round(pct(lat, .5)/60, 1) if lat else 0}
S["yearly"] = yearly

# 最近 30 条原文样本（给报告用）
S["tail_sample"] = [{"time": datetime.fromtimestamp(m["t"]).strftime("%Y-%m-%d %H:%M"),
                     "from": "我" if m["is_self"] else NAME, "text": m["text"][:80], "kind": m["kind"]}
                    for m in msgs[-40:] if m["kind"] in ("text", "link")]

S["top_days"] = [[d, c] for d, c in S["top_days"]]
json.dump(S, open(f"{OUT}/stats_{TARGET}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"stats -> {OUT}/stats_{TARGET}.json  ({time.time()-t0:.1f}s)")
print(f"总 {S['total']:,} | 我 {S['mine']:,} : 对方 {S['hers']:,} | 跨度 {S['span_years']} 年 | 活跃天数 {S['active_days']}")
print("年度:", {k: v["n"] for k, v in yearly.items()})
print("Top短语:", S["top_phrases"][:20])

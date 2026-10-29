#!/usr/bin/env python3
"""根据 stats.json 生成 HTML 可视化报告（纯内联 SVG，无外部依赖）"""
import json, os, sys
from datetime import datetime

if len(sys.argv) < 2:
    sys.exit("用法: python3 gen_report.py <wxid>")
TARGET = sys.argv[1]
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
S = json.load(open(f"{BASE}/stats_{TARGET}.json", encoding="utf-8"))

ME, HER = "我", S["name"]
C1, C2, ACC, MUT = "#2b6cb0", "#dd6b20", "#FF6B35", "#718096"


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bars(data, w=880, h=180, colors=(C1,), labels=None, fmt=lambda v: f"{v:,}", gap=0.28, minlabel=0):
    """data: [(label, [v1, v2...])]  分组柱状图"""
    n = len(data)
    if n == 0:
        return ""
    series = len(data[0][1])
    pad_l, pad_b, pad_t = 44, 26, 14
    iw, ih = w - pad_l - 8, h - pad_b - pad_t
    maxv = max(max(v) for _, v in data) or 1
    gw = iw / n
    bw = gw * (1 - gap) / series
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">']
    for gy in range(5):
        y = pad_t + ih * gy / 4
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-4}" y2="{y:.1f}" stroke="#e6e9ee" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" font-size="10" fill="{MUT}" text-anchor="end">{fmt(int(maxv*(4-gy)/4))}</text>')
    for i, (lab, vals) in enumerate(data):
        x0 = pad_l + i * gw + gw * gap / 2
        for j, v in enumerate(vals):
            bh = ih * v / maxv
            x = x0 + j * bw
            out.append(f'<rect x="{x:.1f}" y="{pad_t+ih-bh:.1f}" width="{max(bw-1.2,1):.1f}" height="{bh:.1f}" '
                       f'rx="1.5" fill="{colors[j % len(colors)]}"><title>{lab}: {fmt(v)}</title></rect>')
        if n <= 30 or i % max(1, n // 12) == 0:
            out.append(f'<text x="{pad_l+i*gw+gw/2:.1f}" y="{h-pad_b+14}" font-size="10" fill="{MUT}" text-anchor="middle">{esc(lab)}</text>')
    out.append("</svg>")
    return "".join(out)


def line(data, w=880, h=170, color=ACC, fmt=lambda v: f"{v:,}"):
    """data: [(label, v)]"""
    if not data:
        return ""
    pad_l, pad_b, pad_t = 44, 26, 14
    iw, ih = w - pad_l - 8, h - pad_b - pad_t
    maxv = max(v for _, v in data) or 1
    n = len(data)
    pts = [(pad_l + iw * i / max(n - 1, 1), pad_t + ih - ih * v / maxv) for i, (_, v) in enumerate(data)]
    d = " ".join(f"{'M' if i==0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = d + f" L{pts[-1][0]:.1f},{pad_t+ih} L{pts[0][0]:.1f},{pad_t+ih} Z"
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img">']
    for gy in range(4):
        y = pad_t + ih * gy / 3
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-4}" y2="{y:.1f}" stroke="#e6e9ee"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" font-size="10" fill="{MUT}" text-anchor="end">{fmt(int(maxv*(3-gy)/3))}</text>')
    out.append(f'<path d="{area}" fill="{color}" opacity="0.10"/>')
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>')
    step = max(1, n // 10)
    for i, (lab, v) in enumerate(data):
        if i % step == 0 or i == n - 1:
            out.append(f'<text x="{pts[i][0]:.1f}" y="{h-pad_b+14}" font-size="10" fill="{MUT}" text-anchor="middle">{esc(lab)}</text>')
    out.append("</svg>")
    return "".join(out)


def heat(months, w=880, cell_h=26):
    """月度热力条：横向 12 列 × N 年"""
    years = sorted({m[:4] for m in months})
    maxv = max(months.values()) or 1
    rows = []
    for y in years:
        rows.append((y, [months.get(f"{y}-{m:02d}", 0) for m in range(1, 13)]))
    cw = (w - 46) / 12
    h = len(rows) * cell_h + 22
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%">']
    for m in range(12):
        out.append(f'<text x="{46+(m+0.5)*cw:.1f}" y="11" font-size="9" fill="{MUT}" text-anchor="middle">{m+1}月</text>')
    for r, (y, vals) in enumerate(rows):
        yy = 18 + r * cell_h
        out.append(f'<text x="40" y="{yy+cell_h*0.62:.0f}" font-size="10" fill="{MUT}" text-anchor="end">{y}</text>')
        for m, v in enumerate(vals):
            t = (v / maxv) ** 0.6
            color = f"rgba(43,108,176,{0.06 + 0.9*t:.2f})" if v else "#f2f4f7"
            out.append(f'<rect x="{46+m*cw:.1f}" y="{yy}" width="{cw-2:.1f}" height="{cell_h-3}" rx="3" fill="{color}">'
                       f'<title>{y}-{m+1:02d}: {v:,} 条</title></rect>')
            if v > maxv * 0.25:
                out.append(f'<text x="{46+m*cw+(cw-2)/2:.1f}" y="{yy+cell_h*0.62:.0f}" font-size="9" fill="#fff" text-anchor="middle">{v//1000}k</text>')
    out.append("</svg>")
    return "".join(out), rows


def hbars(items, w=880, color=C1, fmt=lambda v: f"{v:,}"):
    if not items:
        return ""
    maxv = max(v for _, v in items) or 1
    row = 24
    h = len(items) * row + 8
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%">']
    lw = 150
    for i, (k, v) in enumerate(items):
        y = 4 + i * row
        bw = (w - lw - 70) * v / maxv
        out.append(f'<text x="{lw-8}" y="{y+14}" font-size="11.5" fill="#2d3748" text-anchor="end">{esc(k)}</text>')
        out.append(f'<rect x="{lw}" y="{y+2}" width="{bw:.1f}" height="15" rx="3" fill="{color}" opacity="{0.45+0.5*v/maxv:.2f}"/>')
        out.append(f'<text x="{lw+bw+8:.1f}" y="{y+14}" font-size="11" fill="{MUT}">{fmt(v)}</text>')
    out.append("</svg>")
    return "".join(out)


# ─── 组装数据 ───
months = S["by_month"]
years_data = [(str(y), [v["n"]]) for y, v in S["yearly"].items()]
perday = [(str(y), [v["per_day"]]) for y, v in S["yearly"].items()]
hours = [(f"{h}", [S["hour_mine"][str(h)], S["hour_hers"][str(h)]]) for h in range(24)]
wdd = ["一", "二", "三", "四", "五", "六", "日"]
week = [(wdd[k], [S["weekday"][str(k)]]) for k in range(7)]
heatmap, rows = heat({k: v for k, v in months.items()})
kwh = [(k, v) for k, v in list(S["keywords"].items())[:14]]
ph_both = {k: v for k, v in S["top_phrases"]}

# 关键推导
peak_hour = max(range(24), key=lambda h: S["hour_mine"][str(h)] + S["hour_hers"][str(h)])
tot_kind = S["kinds"]
text_share = round(tot_kind.get("text", 0) / S["total"] * 100, 1)
maxy = max(S["yearly"].items(), key=lambda kv: kv[1]["n"])
peak_day = S["top_days"][0] if S["top_days"] else ("-", 0)

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(S['name'])} · 聊天记录分析</title>
<style>
:root{{--acc:{ACC};--ink:#1a202c;--mut:{MUT};--line:#e6e9ee;--bg:#fbfcfd}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.7 -apple-system,"PingFang SC","Microsoft Yahei",sans-serif;
 -webkit-font-smoothing:antialiased}}
.wrap{{max-width:1000px;margin:0 auto;padding:44px 24px 80px}}
h1{{font-size:30px;margin:0 0 6px;letter-spacing:-.4px}}
h1 span{{color:var(--acc)}}
.sub{{color:var(--mut);font-size:13.5px;margin-bottom:36px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 40px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px}}
.card .v{{font-size:25px;font-weight:700;letter-spacing:-.5px;font-variant-numeric:tabular-nums}}
.card .k{{font-size:12px;color:var(--mut);margin-top:2px}}
.card .n{{font-size:11.5px;color:#a0aec0;margin-top:4px}}
section{{margin:0 0 42px}}
h2{{font-size:17px;margin:0 0 4px;padding-left:11px;border-left:4px solid var(--acc);line-height:1.3}}
h2 small{{font-weight:400;color:var(--mut);font-size:12.5px;margin-left:8px}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 16px 10px;margin-top:14px}}
.legend{{display:flex;gap:16px;font-size:12px;color:var(--mut);margin:0 0 4px 2px}}
.legend i{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}}
th{{font-size:12px;color:var(--mut);font-weight:600;background:#f8fafc}}
td.n{{font-variant-numeric:tabular-nums;text-align:right}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
ul.take{{margin:6px 0 0;padding-left:20px}}
ul.take li{{margin:7px 0}}
.note{{font-size:12.5px;color:var(--mut);margin-top:10px;line-height:1.6}}
.tag{{display:inline-block;background:#fff3ec;color:#c05621;border-radius:5px;padding:1px 7px;font-size:12px;margin-right:5px}}
footer{{color:#a0aec0;font-size:12px;border-top:1px solid var(--line);padding-top:16px}}
@media(max-width:640px){{.two{{grid-template-columns:1fr}}.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">

<h1>与「<span>{esc(S['name'])}</span>」的聊天记录分析</h1>
<div class="sub">{S['first']} — {S['last']} ｜ 共 {S['total']:,} 条 ｜ 本地解密库离线分析，无数据外传</div>

<div class="cards">
  <div class="card"><div class="v">{S['total']:,}</div><div class="k">消息总数</div><div class="n">去重后</div></div>
  <div class="card"><div class="v">{S['span_years']} 年</div><div class="k">时间跨度</div><div class="n">{S['span_days']:.0f} 天</div></div>
  <div class="card"><div class="v">{S['per_day']}</div><div class="k">日均消息</div><div class="n">按全跨度均摊</div></div>
  <div class="card"><div class="v">{S['active_days']:,}</div><div class="k">有聊天的天</div><div class="n">占 {S['active_day_ratio']}%</div></div>
  <div class="card"><div class="v">{S['ratio']}</div><div class="k">我 : 对方</div><div class="n">{S['mine']:,} / {S['hers']:,}</div></div>
  <div class="card"><div class="v">{S['sessions']:,}</div><div class="k">独立对话轮次</div><div class="n">间隔&gt;30min 切分</div></div>
</div>

<section>
<h2>年度体量<small>2021 只从 8 月开始，属于残段</small></h2>
<div class="panel">{bars(years_data, h=190, colors=(C1,))}</div>
</section>

<section>
<h2>月度热力<small>颜色越深 = 当月越活跃</small></h2>
<div class="panel">{heatmap}</div>
</section>

<section>
<h2>日均强度演变<small>有聊天的日子里平均每天多少条</small></h2>
<div class="panel">{bars(perday, h=170, colors=(ACC,))}
<div class="note">峰值在 {maxy[0]} 年：{maxy[1]['per_day']} 条/聊天天；最低是 {min(S['yearly'].items(), key=lambda kv: kv[1]['per_day'])[0]} 年。</div></div>
</section>

<section>
<h2>一天中的作息<small>0—23 时消息量分布</small></h2>
<div class="panel">
<div class="legend"><span><i style="background:{C1}"></i>我</span><span><i style="background:{C2}"></i>对方</span></div>
{bars(hours, h=200, colors=(C1, C2), gap=0.22)}
<div class="note">双方共同高峰在 <b>{peak_hour}:00</b> 前后；凌晨 2—6 点仍有零星消息，属于睡前/夜聊余波。</div></div>
</section>

<section>
<h2>一周节律<small>周一 → 周日</small></h2>
<div class="panel">{bars(week, h=150, colors=("#805ad5",))}</div>
</section>

<section>
<h2>回复速度<small>对方发完后的下一条消息，6 小时内计为回复</small></h2>
<div class="panel">
<table>
<tr><th>指标</th><th class="n">我回对方</th><th class="n">对方回我</th></tr>
<tr><td>样本数</td><td class="n">{S['lat_mine']['n']:,}</td><td class="n">{S['lat_hers']['n']:,}</td></tr>
<tr><td>中位延迟</td><td class="n">{S['lat_mine']['median']} 分钟</td><td class="n">{S['lat_hers']['median']} 分钟</td></tr>
<tr><td>平均延迟</td><td class="n">{S['lat_mine']['avg']} 分钟</td><td class="n">{S['lat_hers']['avg']} 分钟</td></tr>
<tr><td>P90 延迟</td><td class="n">{S['lat_mine']['p90']} 分钟</td><td class="n">{S['lat_hers']['p90']} 分钟</td></tr>
<tr><td>5 分钟内回复占比</td><td class="n">{S['lat_mine_5min']}%</td><td class="n">{S['lat_hers_5min']}%</td></tr>
</table>
<div class="note">双方中位延迟都在 12 秒级，说明绝大多数时间处于「在线对聊」状态，而不是留言式往来。</div></div>
</section>

<section>
<h2>对话结构<small>谁先开口、谁收尾、聊多长</small></h2>
<div class="panel">
<table>
<tr><th>指标</th><th class="n">我</th><th class="n">对方</th></tr>
<tr><td>当天第一条发起</td><td class="n">{S['first_speaker'].get('我',0):,} 天</td><td class="n">{S['first_speaker'].get(S['name'],0):,} 天</td></tr>
<tr><td>当天最后一条收尾</td><td class="n">{S['last_speaker'].get('我',0):,} 天</td><td class="n">{S['last_speaker'].get(S['name'],0):,} 天</td></tr>
</table>
<div class="note">平均每轮对话 {S['msgs_per_session']} 条、时长中位 {S['session_len_min']} 分钟。消息构成：文本 {tot_kind.get('text',0):,} 条（{text_share}%）、图片/语音/表情等媒体 {tot_kind.get('media',0):,} 条、卡片链接 {tot_kind.get('link',0):,} 条。</div>
</div>
</section>

<section>
<h2>沉默期<small>间隔超过 24 小时的断档，共 {S['silence_n']} 次，平均 {S['silence_avg']} 天</small></h2>
<div class="panel">
<table>
<tr><th>天数</th><th>从</th><th>到</th></tr>
{''.join(f'<tr><td>{g} 天</td><td>{a}</td><td>{b}</td></tr>' for g, a, b in S['silences'])}
</table>
<div class="note">最长的 {S['silences'][0][0]} 天出现在 {S['silences'][0][1]} → {S['silences'][0][2]}。</div></div>
</section>

<section>
<h2>高频词<small>jieba 分词后统计，已过滤功能词与单字</small></h2>
<div class="panel">
<div class="two">
<div><div class="legend"><span><i style="background:{C1}"></i>我常说</span></div>
{hbars([(k, v) for k, v in S['top_phrases_mine'][:12]], w=440 if False else 430, color=C1)}
</div>
<div><div class="legend"><span><i style="background:{C2}"></i>对方常说</span></div>
{hbars([(k, v) for k, v in S['top_phrases_hers'][:12]], w=430, color=C2)}
</div></div></div>
</section>

<section>
<h2>关键表达命中<small>包含该词的文本消息条数</small></h2>
<div class="panel">{hbars(kwh, color="#38a169")}</div>
</section>

<section>
<h2>表情使用<small>共 {S['emoji_total']:,} 次</small></h2>
<div class="panel">
<table>
{''.join(f'<tr><td>{esc(k)}</td><td class="n">{v:,}</td></tr>' for k, v in S['emoji_top'][:10])}
</table></div>
</section>

<section>
<h2>看点</h2>
<div class="panel"><ul class="take">
<li><span class="tag">体量</span>{S['total']:,} 条、{S['span_years']} 年、日均 {S['per_day']} 条。这是本机所有会话里排第一的私聊，第二名「东芳姐」只有 4.8 万条，量级差 9 倍。</li>
<li><span class="tag">对等</span>我 {S['mine']:,} : 对方 {S['hers']:,}，比例 {S['ratio']}，几乎完全对称——典型的「双高投入」关系，没有明显的单方输出。</li>
<li><span class="tag">在线感</span>双方 5 分钟内回复占比分别为 {S['lat_mine_5min']}% 和 {S['lat_hers_5min']}%，中位延迟 12 秒上下。这是把微信当「对讲机」用的状态。</li>
<li><span class="tag">峰值</span>最热一天是 {peak_day[0]}（{peak_day[1]:,} 条）。{maxy[0]} 年日均 {maxy[1]['per_day']} 条为全期最高，2026 年回落到 {S['yearly']['2026']['per_day']} 条（且仅统计到 9 月）。</li>
<li><span class="tag">短句</span>我平均 {S['len_mine']['avg']} 字/条、对方 {S['len_hers']['avg']} 字/条，中位数只有 {S['len_mine']['median']}/{S['len_hers']['median']} 字。聊的是碎片，不是长信。</li>
<li><span class="tag">仪式</span>「晚安」{S['keywords'].get('晚安',0):,} 次、「爱你」{S['keywords'].get('爱你',0):,} 次、「想你」{S['keywords'].get('想你',0):,} 次；我发起当天对话 {S['first_speaker'].get('我',0):,} 天、收尾 {S['last_speaker'].get('我',0):,} 天，两端都由我承担更多。</li>
<li><span class="tag">断档</span>{S['silence_n']} 次超过一天的沉默，最长 {S['silences'][0][0]} 天（{S['silences'][0][1]} → {S['silences'][0][2]}）。其余断档多集中在 2021—2023 年。</li>
<li><span class="tag">内容</span>高频词是「哈哈哈 / 嗯嗯 / 老婆 / 吃饭 / 睡觉 / 牛逼」，情绪基调偏轻松；媒体消息 {tot_kind.get('media',0):,} 条占 {round(tot_kind.get('media',0)/S['total']*100,1)}%，以表情和图片为主。</li>
</ul>
<div class="note">数据来源：~/WeChat_Decrypted 解密库（微信 4.0 Mac 版，6 个分库合并去重）。消息方向依据各分库 Name2Id 的 rowid 映射还原 wxid 后判定，非固定 sender_id——原 viewer 用 <code>sender_id==2</code> 判断「我」，在 message_0/1/2/3 上会串号，本报告已规避。</div>
</div>
</section>

<footer>生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 全部处理在本机完成，未上传任何内容</footer>
</div></body></html>"""

out = f"{BASE}/report_{TARGET}.html"
open(out, "w", encoding="utf-8").write(html)
print("written:", out, len(html), "bytes")

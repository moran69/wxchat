#!/usr/bin/env python3
"""
wxlib —— 本地微信 4.0（macOS）明文库读取库，只读。

约定：
  WX_DB_DIR   明文 SQLite 所在目录，默认 ~/WeChat_Decrypted
  WX_MY_WXID  本人 wxid；未设置时依次尝试 $WX_DB_DIR/.account、自动推断
"""
import os, glob, sqlite3, hashlib, re

DB_DIR = os.path.expanduser(os.environ.get("WX_DB_DIR", "~/WeChat_Decrypted"))

try:
    import zstandard as zstd
    _zd = zstd.ZstdDecompressor()
except Exception:
    _zd = None

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

TYPE_MAP = {1: "文本", 3: "图片", 34: "语音", 43: "视频", 47: "表情", 48: "位置",
            49: "链接/文件/引用", 42: "名片", 50: "通话", 10000: "系统", 10002: "撤回"}


def conn(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def msg_dbs():
    return [(os.path.basename(p), conn(p)) for p in sorted(glob.glob(os.path.join(DB_DIR, "message_*.db")))]


def decompress(raw):
    """微信 4.0 的消息正文是 zstd 压缩；非压缩内容原样解码。"""
    if raw is None:
        return ""
    if isinstance(raw, str):
        try:
            raw_b = raw.encode("latin-1")
        except Exception:
            return raw
    else:
        raw_b = bytes(raw)
    if len(raw_b) >= 4 and raw_b[:4] == ZSTD_MAGIC and _zd:
        try:
            return _zd.decompress(raw_b).decode("utf-8", errors="replace")
        except Exception:
            pass
    return raw_b.decode("utf-8", errors="replace")


def contact_map():
    """username -> 显示名（备注 > 昵称 > 别名）"""
    m = {}
    try:
        c = conn(os.path.join(DB_DIR, "contact.db"))
        for r in c.execute("SELECT username, remark, nick_name, alias FROM contact"):
            name = (r["remark"] or "").strip() or (r["nick_name"] or "").strip() or (r["alias"] or "").strip()
            m[r["username"]] = name or r["username"]
        c.close()
    except Exception:
        pass
    return m


def md5tbl(username):
    """会话表名 = Msg_<md5(username)>"""
    return "Msg_" + hashlib.md5(username.encode()).hexdigest()


def detect_my_wxid():
    """推断本人 wxid：env → .account 文件 → 跨库高频发送者"""
    env = os.environ.get("WX_MY_WXID")
    if env:
        return env
    f = os.path.join(DB_DIR, ".account")
    if os.path.exists(f):
        v = open(f).read().strip()
        if v:
            return v
    from collections import Counter
    cnt = Counter()
    for _, c in msg_dbs():
        try:
            tables = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%' LIMIT 40")]
        except Exception:
            continue
        for t in tables:
            try:
                idmap = {r[0]: r[1] for r in c.execute("SELECT rowid, user_name FROM Name2Id")}
                for sid, n in c.execute(f'SELECT real_sender_id, COUNT(*) FROM "{t}" GROUP BY 1').fetchall():
                    if idmap.get(sid):
                        cnt[idmap[sid]] += n
            except Exception:
                continue
    return cnt.most_common(1)[0][0] if cnt else ""


MY_WXID = detect_my_wxid()


def list_tables(c):
    return [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]


def scan_conversations():
    """返回 [{username, name, db, table, cnt, first, last, is_room}]"""
    cmap = contact_map()
    out = []
    for dbname, c in msg_dbs():
        rev = {}
        try:
            for r in c.execute("SELECT user_name FROM Name2Id"):
                u = r["user_name"]
                rev[md5tbl(u)] = u
        except Exception:
            pass
        for t in list_tables(c):
            u = rev.get(t)
            if not u:
                continue
            try:
                row = c.execute(f'SELECT COUNT(*) cnt, MIN(create_time) f, MAX(create_time) l FROM "{t}"').fetchone()
            except Exception:
                continue
            if not row or not row["cnt"]:
                continue
            out.append({"username": u, "name": cmap.get(u, u.split("@")[0]), "db": dbname,
                        "table": t, "cnt": row["cnt"], "first": row["f"], "last": row["l"],
                        "is_room": u.endswith("@chatroom")})
    out.sort(key=lambda x: x["cnt"], reverse=True)
    return out


def parse_content(local_type, content):
    """-> (kind, text)；kind ∈ text / media / link / system"""
    bt = local_type & 0xFFFF
    if bt > 100:
        bt = local_type & 0xFF
    if bt == 1:
        t = content or ""
        if t.lstrip().startswith(("<msg", "<?xml")):
            m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", t, re.S)
            return "link", "📎 " + (m.group(1).strip() if m else "卡片")
        return "text", t
    if bt == 49:
        m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", content or "", re.S)
        return "link", "📎 " + (m.group(1).strip() if m else "链接/文件")
    if bt == 10000:
        s = " ".join(re.sub(r"<[^>]+>", " ", content or "").split())
        return "system", s[:120]
    if bt == 10002:
        return "system", "[撤回]"
    return "media", f"[{TYPE_MAP.get(bt, bt)}]"


def fetch_messages(username, table=None, dbname=None):
    """读取某会话全部消息，按时间升序。

    关键：real_sender_id 是「该分库内 Name2Id 的 rowid」，逐库映射不同，
    必须解析成 wxid 再判断是否本人，绝不能硬编码某个 id。
    """
    tgt = table or md5tbl(username)
    rows = []
    for dbname_i, c in msg_dbs():
        if dbname and dbname_i != dbname:
            continue
        try:
            idmap = {r[0]: r[1] for r in c.execute("SELECT rowid, user_name FROM Name2Id")}
        except Exception:
            idmap = {}
        try:
            cur = c.execute(f'SELECT local_id, local_type, sort_seq, real_sender_id, create_time, '
                            f'message_content, compress_content FROM "{tgt}" '
                            f'ORDER BY create_time, sort_seq')
        except Exception:
            continue
        for r in cur:
            raw = r["message_content"]
            if raw is None or raw == "":
                raw = r["compress_content"]
            content = decompress(raw)
            wxid = idmap.get(r["real_sender_id"] or 0, "")
            is_self = bool(MY_WXID) and wxid == MY_WXID
            name = ""
            if username.endswith("@chatroom") and ":\n" in content:
                parts = content.split(":\n", 1)
                name, content = parts[0].strip(), parts[1]
            kind, text = parse_content(r["local_type"], content)
            rows.append({"t": r["create_time"], "sid": r["real_sender_id"], "wxid": wxid,
                         "is_self": is_self, "kind": kind, "type": r["local_type"] & 0xFF,
                         "text": text, "sender": name, "lid": r["local_id"]})
        if dbname:
            break
    rows.sort(key=lambda x: (x["t"] or 0))
    return rows

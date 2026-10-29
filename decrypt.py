#!/usr/bin/env python3
"""
decrypt.py —— 把微信 4.0（macOS）的 SQLCipher 加密库导出为明文 SQLite。

前置：
  1. 已在同目录生成 wx_keys.json（由 scan_keys.py 在 lldb 里扫内存得到）：{salt: key}
  2. 已安装 sqlcipher 与 python3

用法：
  python3 decrypt.py                    # 自动探测账号目录，导出到 ~/WeChat_Decrypted
  WX_OUT=/path/out python3 decrypt.py
"""
import os, sys, glob, json, shutil, sqlite3, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS_JSON = os.path.join(HERE, "wx_keys.json")
OUT = os.path.expanduser(os.environ.get("WX_OUT", "~/WeChat_Decrypted"))
CONTAINER = os.path.expanduser("~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files")

TARGETS = [f"message/message_{i}.db" for i in range(6)] + ["contact/contact.db", "session/session.db"]


def find_db_storage():
    """在容器目录里找 <wxid>/db_storage（多账号时取最近修改的那个）"""
    cands = glob.glob(os.path.join(CONTAINER, "*", "db_storage"))
    if not cands:
        sys.exit(f"未找到 db_storage，检查路径: {CONTAINER}\n"
                 f"（微信 4.0 默认在此，若你的版本不同请改 CONTAINER）")
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


def salt_of(path):
    with open(path, "rb") as f:
        return f.read(16).hex()


def decrypt(src, outpath, rawkey_with_salt):
    """复制 db(+wal/shm) 到临时目录再导出，避免与运行中的微信争用文件锁。"""
    tmpdir = tempfile.mkdtemp(prefix="wxdec_")
    base = os.path.basename(src)
    for suf in ("", "-wal", "-shm"):
        p = src + suf
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(tmpdir, base + suf))
    outtmp = outpath + ".tmp"
    if os.path.exists(outtmp):
        os.remove(outtmp)
    sql = (f'PRAGMA key = "x\'{rawkey_with_salt}\'";\n'
           f'PRAGMA cipher_compatibility = 4;\n'
           f"ATTACH DATABASE '{outtmp}' AS plaintext KEY '';\n"
           f"SELECT sqlcipher_export('plaintext');\n"
           f"DETACH DATABASE plaintext;\n")
    r = subprocess.run(["sqlcipher", os.path.join(tmpdir, base)], input=sql, text=True, capture_output=True)
    shutil.rmtree(tmpdir, ignore_errors=True)
    if not os.path.exists(outtmp):
        return False, (r.stderr or r.stdout or "sqlcipher 无输出").strip()[:200]
    try:
        c = sqlite3.connect(outtmp)
        n = c.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        c.close()
        if n < 5:
            return False, f"导出后表数异常 {n}"
    except Exception as e:
        return False, f"校验失败 {e}"
    os.replace(outtmp, outpath)      # 校验通过才覆盖旧库
    return True, f"{n} objects, {os.path.getsize(outpath)/1e6:.1f} MB"


def main():
    if not os.path.exists(KEYS_JSON):
        sys.exit(f"缺少 {KEYS_JSON}\n先用 scan_keys.py 在 lldb 里扫一遍内存（见 README「第二步」）")
    keys = json.load(open(KEYS_JSON))
    if not keys:
        sys.exit("wx_keys.json 是空的：扫描时一个 x'...' 字符串都没命中，见 README 的排查说明")

    dbdir = find_db_storage()
    account = os.path.basename(os.path.dirname(dbdir))      # 形如 wxid_xxxxxxxx_add5
    os.makedirs(OUT, exist_ok=True)
    wxid = account.split("_add")[0] if "_add" in account else account
    with open(os.path.join(OUT, ".account"), "w") as f:     # 供 wxlib 判断「我」
        f.write(wxid)

    print(f"加密库目录: {dbdir}")
    print(f"导出目录  : {OUT}\n{'库':<16} {'结果':<4} 详情")
    for rel in TARGETS:
        src = os.path.join(dbdir, rel)
        name = os.path.basename(src)
        if not os.path.exists(src):
            print(f"{name:<16} {'-':<4} 不存在")
            continue
        salt = salt_of(src)
        key = keys.get(salt)
        if not key:
            print(f"{name:<16} {'❌':<4} 无匹配密钥 (salt={salt[:8]}…)；微信是否重启过？需重扫")
            continue
        ok, info = decrypt(src, os.path.join(OUT, name), key + salt)
        print(f"{name:<16} {'✅' if ok else '❌':<4} {info}")


if __name__ == "__main__":
    main()

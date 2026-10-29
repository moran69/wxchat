import lldb
import json
import os

# WCDB 密钥在内存中是 99 字符 ASCII：x'<64hex key><32hex salt>'
# 本版不预设 salt 白名单，凡是合法字符串一律记录 salt -> key，供按 salt 精确匹配解密。
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wx_keys.json")


def scan_memory(debugger, command, result, internal_dict):
    process = debugger.GetSelectedTarget().GetProcess()
    regions = []
    addr = 0
    while addr < 0x200000000:
        info = lldb.SBMemoryRegionInfo()
        err = process.GetMemoryRegionInfo(addr, info)
        if err.Success() and info.GetRegionEnd() > addr:
            if info.IsReadable():
                regions.append((info.GetRegionBase(), info.GetRegionEnd()))
            addr = info.GetRegionEnd()
        else:
            addr += 0x1000

    print(f"[scan] readable regions: {len(regions)}")
    needle = b"x'"
    found = {}

    for bi, (base, end) in enumerate(regions):
        size = end - base
        if size <= 0 or size > 256 * 1024 * 1024:
            continue
        err = lldb.SBError()
        data = process.ReadMemory(base, size, err)
        if not err.Success() or data is None:
            continue
        off = 0
        while True:
            pos = data.find(needle, off)
            if pos == -1:
                break
            if pos + 99 <= len(data):
                cand = data[pos:pos + 99]
                if cand[98:99] == b"'":
                    try:
                        hex_str = cand[2:98].decode("ascii")
                        if all(c in "0123456789abcdefABCDEF" for c in hex_str):
                            key, salt = hex_str[:64], hex_str[64:96].lower()
                            found.setdefault(salt, key)
                    except Exception:
                        pass
            off = pos + 2
        if bi % 50 == 0:
            print(f"[scan] region {bi}/{len(regions)}  salts so far: {len(found)}")

    print(f"[scan] distinct salt->key pairs: {len(found)}")
    with open(OUT, "w") as f:
        json.dump(found, f, indent=1)
    for salt, key in found.items():
        print(f"  {salt} : {key}")
    print(f"[scan] written {OUT}")


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f scan_hexkey_all.scan_memory scan_hexkey_all")

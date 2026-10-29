#!/usr/bin/env bash
# 环境自检：跑解密前先过一遍
set -u
ok=0; bad=0
chk() { printf "%-46s" "$1"; if eval "$2" >/dev/null 2>&1; then echo "✅"; ok=$((ok+1)); else echo "❌ $3"; bad=$((bad+1)); fi; }

echo "== 前置检查 =="
chk "macOS"                       "[ \"$(uname)\" = Darwin ]"                  "本项目仅支持 macOS"
chk "微信进程在运行"              "pgrep -x WeChat"                           "先启动并登录微信"
chk "SIP 已关闭（lldb 才能 attach）" "csrutil status | grep -q disabled"        "需进恢复模式执行 csrutil disable"
chk "sqlcipher 可用"              "command -v sqlcipher"                      "brew install sqlcipher"
chk "python3 >= 3.8"              "python3 -c 'import sys;assert sys.version_info>=(3,8)'" "安装新版 python3"
chk "zstandard 可用"              "python3 -c 'import zstandard'"             "pip3 install zstandard"
chk "加密库目录存在"              "ls -d \"$HOME\"/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/*/db_storage" "确认微信 4.x 已登录过"

echo
echo "通过 $ok 项，失败 $bad 项"
[ "$bad" -eq 0 ] && echo "可以继续：python3 scan_keys.py（在 lldb 里）→ python3 decrypt.py" || echo "先解决上面的 ❌ 再继续"
exit 0

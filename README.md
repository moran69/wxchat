# wxchat — 本地微信 4.0（macOS）聊天记录导出与量化分析

把微信 4.0 for macOS 的本地加密库还原成明文 SQLite，再对**单个会话**做全量量化分析，输出一份纯内联 SVG 的 HTML 报告（年度体量、月度热力、24 小时作息、回复速度、对话结构、沉默期、双方词频、关键词、表情）。

全流程在本机完成，不联网、不上传。

```
scan_keys.py  →  decrypt.py  →  list_convs.py  →  analyze.py  →  gen_report.py
（lldb 取密钥）  （sqlcipher 导出）  （找会话）        （统计）        （出报告）
```

---

## 0. 适用边界

- ✅ macOS + 微信 **4.0.x**（"xinWeChat" / WCDB 架构），只处理**本人设备、本人账号**的本地数据
- ❌ Windows（微信 3.x/4.x 走别的路子，本项目不覆盖）
- ❌ 不能把密钥给第二个人：密钥在每台机器登录时生成，我的给不了你，你的也给不了我

> 解密操作始终在**副本**上进行，原始库一个字节都不改。

---

## 1. 环境

```bash
brew install sqlcipher
pip3 install zstandard
bash setup.sh          # 逐项自检：微信是否在跑 / SIP / sqlcipher / python / 库目录
```

**SIP 必须关闭**，否则 `lldb` 无法 attach 微信读取内存：

```bash
csrutil status                       # 需显示 disabled
# 关闭方式：重启进恢复模式 → 终端 → csrutil disable → 重启
```

---

## 2. 取密钥

密钥是 SQLCipher 的 **raw key**，在进程内存中以 99 字符 ASCII 存在：

```
x'<64 位 hex = 32 字节 AES-256 key><32 位 hex = 16 字节 salt>'
```

WCDB 源码 `CipherHandle.cpp` 里就是这个判断：`m_isInitializing && data.size() == 99`，前缀 `x'`、后缀 `'`。

```bash
# 微信必须在运行且已登录
lldb -p $(pgrep -x WeChat) \
  -o "command script import $PWD/scan_keys.py" \
  -o "scan_hexkey_all" \
  -o "detach" -o "quit"
```

产出 `wx_keys.json`：`{ "<salt>": "<key>" }`，覆盖所有能扫到的库。

**扫不到怎么办**（实测会遇到）：微信长跑之后这些字符串可能已被释放，扫描结果是 0 命中。
此时重启微信、**立刻**再扫一次——密钥是在开库那一刻写入内存的。

---

## 3. 解密

```bash
python3 decrypt.py
# 默认导出到 ~/WeChat_Decrypted，可用 WX_OUT 改
```

逻辑：按 `db_storage` 里每个 `.db` 的**前 16 字节 salt** 去 `wx_keys.json` 反查密钥 → 复制 `.db` + `-wal` + `-shm` 到临时目录（避免和运行中的微信争锁）→ `sqlcipher_export` 导成明文 → 校验表数通过才覆盖目标文件。

顺带写入 `~/WeChat_Decrypted/.account`，记下本人 wxid，供后续判断「谁是我」。

---

## 4. 分析

```bash
python3 list_convs.py                       # 全量会话排行（含消息数/时间跨度/分库数）
python3 analyze.py <wxid 或 备注名>          # 统计 → out/stats_*.json + out/chat_*.jsonl
python3 gen_report.py <wxid>                # → out/report_*.html
```

`analyze.py` 统计口径：

| 指标 | 定义 |
|---|---|
| 回复延迟 | 对方发完后我的下一条，间隔 ≤6h 计入；给中位/均值/P90/5 分钟内占比 |
| 对话轮次 | 相邻消息间隔 >30min 切分，统计轮次数、每轮条数、时长中位 |
| 沉默期 | 相邻消息间隔 >24h 的断档，按长度排序 |
| 发起/收尾 | 按自然日看当天第一条、最后一条是谁 |
| 词频 | jieba 分词（无 jieba 自动退化为 2–3 字 n-gram），过滤功能词与单字；「哈哈哈」这类连续笑声先归一再分词 |

---

## 5. 两个必须知道的坑

**① `real_sender_id` 不是固定值。**
它是「**该分库内** `Name2Id` 表的 rowid」，而每个 `message_N.db` 的映射各不相同——
同一个 id 在 `message_0` 里可能是你，在 `message_2` 里可能是对方。
硬编码 `real_sender_id == 2` 判断「我」会得出完全错误的方向统计（实测能把 1:1 算成 1:6）。
正确做法：按库解析 `Name2Id` 的 `rowid → user_name`，再比对本人的 wxid。

**② 消息正文是 zstd 压缩的。**
`message_content` 以 `28 b5 2f fd` 开头时要先解压；纯文本直接用。字段为空时回退读 `compress_content`。

另外 `Msg_<md5(username)>` 是会话表名的规则，用它反查 `Name2Id` 就能还原出每个表对应哪个 wxid / 群号。

---

## 6. 仓库里没有什么

- 没有密钥、没有 wxid、没有任何聊天内容或统计结果
- `wx_keys.json` / `out/` / `~/WeChat_Decrypted` 都在 `.gitignore` 里

---

## 7. 合规

仅用于访问**本人设备上本人账号**的本地数据。不要用它处理他人数据，不要把解密库或分析结果公开传播。因使用不当造成的后果由使用者自负。

## License

MIT

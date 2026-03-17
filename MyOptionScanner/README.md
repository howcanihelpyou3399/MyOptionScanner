# MyOptionScanner 📊

一个轻量级的期权IV监控系统，专为 **Sell Premium** 策略设计（Covered Call + Cash Secured Put）。
运行在 Google Colab，通过 Telegram 推送交易提醒。躺着收租，不用盯盘。

---

## 设计理念

### 核心思路
- **不追求频繁交易**，两周一次的节奏，只在IV Rank足够高的时候出手
- **不盯盘**，让程序每周扫描一次，有机会才通知你
- **数据不乱跑**，一次性读入，一次性写出，中间全在内存里处理
- **方便排错**，每一步都打印中间状态，保存log文件

### 为什么用 Google Colab
- 免费，不需要自己的服务器
- 复用现有的 Telegram Bot（原来用于 YouTube 项目提醒）
- CPU模式足够用，不需要GPU，省资源
- Python + Bash 混合运行，灵活高效

### 为什么用 Telegram 提醒
- 已有现成的 Bot Token，零成本复用
- 手机直接收到推送，不需要开电脑
- 消息简洁，只在值得出手的时候才通知

---

## 目录结构

```
/MyOptionScanner/
│
├── main.py                   # 主程序入口，串联所有模块
├── scanner.py                # IV扫描核心逻辑
├── notifier.py               # Telegram通知模块
├── setup.sh                  # 一键安装所有依赖
├── run.sh                    # 每次启动用这个
├── README.md                 # 本文件
│
├── /config/
│   ├── config.json           # Telegram token、chat ID、扫描参数（勿上传GitHub）
│   └── config.example.json   # 配置模板，方便参考和分享
│
├── /input/
│   └── watchlist.csv         # 你的股票清单，含策略类型和IV门槛
│
├── /output/
│   └── YYYY-MM-DD.json       # 每天扫描结果，自动按日期命名，方便复盘
│
└── /logs/
    └── YYYY-MM-DD.log        # 每天运行日志，方便排错
```

---

## 配置文件说明

### config.json 结构
```json
{
  "telegram": {
    "token": "your_bot_token_here",
    "chat_id": "your_chat_id_here"
  },
  "scan": {
    "iv_rank_threshold": 50,
    "scan_day": "Monday",
    "scan_time": "09:00"
  },
  "data": {
    "iv_lookback_days": 252
  }
}
```

### 参数说明
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `iv_rank_threshold` | IV Rank最低门槛，低于此值不提醒 | 50 |
| `scan_day` | 每周扫描日 | Monday |
| `scan_time` | 扫描时间（美东时间） | 09:00 |
| `iv_lookback_days` | 计算IV Rank的历史回看天数 | 252（约一年） |

---

## watchlist.csv 格式
```csv
symbol,name,strategy,min_iv_rank
AAPL,Apple,covered_call,50
TSLA,Tesla,cash_secured_put,60
SPY,S&P500 ETF,covered_call,45
```

| 字段 | 说明 |
|------|------|
| `symbol` | 股票代码 |
| `name` | 公司名称（备注用） |
| `strategy` | covered_call 或 cash_secured_put |
| `min_iv_rank` | 这支股票的个性化IV门槛，覆盖全局设置 |

---

## 数据流设计

```
启动
  ↓
一次性读入：config.json + watchlist.csv（从Google Drive）
  ↓
内存中处理：抓取行情 → 计算IV Rank → 筛选符合条件的标的
  ↓
一次性写出：output/YYYY-MM-DD.json + logs/YYYY-MM-DD.log（写回Google Drive）
  ↓
符合条件？→ Telegram推送提醒
不符合？  → 沉默，下周再见
```

---

## Telegram 提醒格式（示意）

```
📊 期权扫描周报 2025-03-17

✅ 值得关注：
• TSLA — IV Rank: 72 | 策略: Cash Secured Put
• NVDA — IV Rank: 68 | 策略: Covered Call

⏳ 暂时观望：
• AAPL — IV Rank: 38（门槛: 50）
• SPY  — IV Rank: 42（门槛: 45）

下次扫描：2025-03-24 周一
```

---

## 开发顺序

1. `setup.sh` — 先把依赖装好
2. `config.json` — 填入 Telegram token 和 chat ID
3. `notifier.py` — 先测通 Telegram，收到消息再往下走
4. `scanner.py` — IV 扫描核心逻辑
5. `main.py` — 把所有模块串起来

---

## 数据来源

- **行情数据**：Yahoo Finance（免费，够用）
- **IV历史数据**：基于历史收盘价计算（252个交易日）
- 将来如需更精准数据，可升级至 CBOE DataShop（付费）

---

## 注意事项

- `config.json` 含有 Telegram Token，**不要上传至 GitHub**
- `config.example.json` 是脱敏模板，可以安全分享
- output 文件按日期命名，定期清理避免 Google Drive 堆积
- 本项目仅供学习和个人使用，**不构成任何投资建议**

---

## 版本记录

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.1 | 2025-03 | 初始设计，IV扫描 + Telegram提醒 |

---

*慢慢玩，不急。好行情等得到。🎯*

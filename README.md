# BookMyShow Seat-Sniper Agent 🎬

Monitors BookMyShow for your preferred seats and sends an instant Telegram alert with a direct booking link the moment they open up.

---

## Setup (5 minutes)

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Create your Telegram bot

1. Open Telegram → search **@BotFather** → `/newbot`
2. Copy the **bot token** it gives you
3. Send any message to your new bot
4. Get your **chat ID**: visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser — your chat ID is in `result[0].message.chat.id`

### 3. Edit `config.yaml`

Fill in:
- `movie.name` and `movie.url` (copy the BMS URL for your movie's city page)
- `movie.release_date` (enables week-1 fast-poll mode for top rows)
- `theatres` list — names exactly as shown on BMS
- `shows.dates` and `shows.times` — your preferred slots
- `seats.preferred_rows` — grouped by priority (group 0 = most preferred)
- `telegram.bot_token` and `telegram.chat_id`

### 4. Run the agent

```bash
python agent.py
```

Or with a custom config path:
```bash
python agent.py --config /path/to/my_config.yaml
```

---

## How it works

| Situation | Behaviour |
|---|---|
| Normal times | Polls every 45 seconds |
| Week 1 of release | Polls every 10 seconds, top rows only |
| Seats found | Telegram alert + browser opens automatically |
| Seats still available | Re-alerts every 2 minutes (configurable) |

### Alert message example

```
🥇 Seats Found! 🔥 TOP ROW

🎬 PVR INOX GVK One
📅 2025-01-15 · 07:00 PM
💺 Row A — Seats A3, A4, A5
🏷️ GOLD
💰 ₹1,350

⏱️ Tap below to book before they're gone!

[ 🎟️ Book Now → ]
```

The **Book Now** button opens BMS directly at the seat selection page. You tap it → confirm seats → pay with UPI. Total time: ~10 seconds.

---

## Keep it running (optional)

**On Linux/Mac** — run in background with `nohup`:
```bash
nohup python agent.py > /dev/null 2>&1 &
```

**Or as a systemd service** (Linux):
```ini
[Unit]
Description=BMS Seat Sniper

[Service]
WorkingDirectory=/path/to/bms_agent
ExecStart=/usr/bin/python3 agent.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Important notes

- This agent **does not complete payment** — Indian banking regulations (RBI) require OTP/biometric at checkout. The agent handles everything up to that point.
- Running this respects BMS's server load — the polling intervals are conservative. Do not reduce below 5 seconds.
- Your BMS account is never touched by the agent — you log in manually after the alert.
- Tested on Python 3.11+.

---

## Troubleshooting

**No shows found** — Check that the `movie.url` is the correct city-specific BMS page and theatre names match exactly.

**Seat map not parsing** — BMS occasionally updates their HTML structure. Check `bms_agent.log` for selector errors — you may need to update the CSS selectors in `scraper.py`.

**Telegram alerts not arriving** — Verify `bot_token` and `chat_id` are correct, and that you've sent at least one message to the bot first.

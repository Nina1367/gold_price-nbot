#!/usr/bin/env python3
"""Hantar update harga Public Gold GAP ke Telegram channel.

Penggunaan:
  python gold_bot.py --dry-run     # papar mesej sahaja, tiada hantar & tiada simpan
  python gold_bot.py               # hantar ke Telegram + kemas kini state.json
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (cth. @AmaninaMatali)
"""
import argparse, html, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_URL = "https://publicgold.com.my/"
STATE_FILE = Path(__file__).with_name("state.json")
MYT = timezone(timedelta(hours=8))
SIGNUP_URL = "https://boards.com/a/ZIcpOi.rtNrUk"
SITE_URL = "https://www.amaninamatali.com"
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Ogo", "Sep", "Okt", "Nov", "Dis"]


def fetch_gap():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    m = re.search(r"GOLD ACCUMULATION PROGRAM \(24K\)(.*?)</table>", page, re.S)
    if not m:
        raise RuntimeError("Seksyen GAP tidak dijumpai - struktur laman mungkin berubah")
    block = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))))
    g = re.search(r"RM\s*100\s*=\s*([\d.]+)\s*gram", block)
    p = re.search(r"RM\s*(\d+(?:\.\d+)?)\s*=\s*1\.0+\s*gram", block)
    if not (g and p):
        raise RuntimeError(f"Gagal parse harga GAP daripada: {block!r}")
    return float(p.group(1)), float(g.group(1))


def rm(x):
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"


def fmt_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_price": None, "last_date": None, "high": None, "low": None}


def build_message(price, grams, state, now):
    today = now.strftime("%Y-%m-%d")
    prev = state.get("last_price")
    high, low = state.get("high"), state.get("low")
    if not high or price >= high["price"]:
        high = {"price": price, "date": today}
    if not low or price <= low["price"]:
        low = {"price": price, "date": today}

    diff = None if prev is None else price - prev
    if diff is None or diff == 0:
        head = "‼️ PRICE UPDATE GAP ‼️"
        intro = f"Harga GAP hari ini: <b>RM{rm(price)}</b> per gram" + (
            " (tiada perubahan daripada semalam)." if diff == 0 else ".")
        trend, closing = "", f"RM100 kini dapat {grams:.4f} gram."
    elif diff > 0:
        head = "‼️ PRICE UPDATE GAP ‼️"
        intro = f"Harga GAP baru dikemaskini <b>NAIK RM{rm(diff)}</b> daripada RM{rm(prev)} kepada RM{rm(price)}."
        trend = f"Harga GAP 🔼 RM {rm(diff)}\n\n"
        closing = f"📈 Harga naik hari ini, RM100 kini dapat {grams:.4f} gram."
    else:
        head = "‼️ PRICE UPDATE GAP ‼️"
        intro = f"Harga GAP baru dikemaskini <b>TURUN RM{rm(-diff)}</b> daripada RM{rm(prev)} kepada RM{rm(price)}."
        trend = f"Harga GAP 🔽 RM {rm(-diff)}\n\n"
        closing = f"📉 Harga turun hari ini, RM100 kini dapat {grams:.4f} gram."

    stamp = f"{now.day} {BULAN[now.month - 1]} {now.year} @ {now.strftime('%-I:%M %p').lower()}"
    msg = (
        f"{head}\n\n{intro}\n\n"
        f"<b>Public Gold GAP</b>\nRM 100 = {grams:.4f} gram\nRM {rm(price)} = 1.0000 gram\n\n"
        f"{trend}"
        f"Terendah: RM {rm(low['price'])} ({fmt_date(low['date'])})\n"
        f"Tertinggi: RM {rm(high['price'])} ({fmt_date(high['date'])})\n\n"
        f"Dikemaskini: {stamp}\n\n"
        f"{closing}\n"
        f"Belum ada akaun emas? Buka akaun &amp; mula simpan dari RM100:\n"
        f"👉 {SIGNUP_URL}\n\n"
        f"🌐 <a href=\"{SITE_URL}\">www.amaninamatali.com</a> | Master Dealer Public Gold"
    )
    new_state = {"last_price": price, "last_date": today, "high": high, "low": low}
    return msg, new_state


def send_telegram(text):
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30) as r:
        if not json.load(r).get("ok"):
            raise RuntimeError("Telegram menolak mesej")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--price", type=float, help="(ujian) paksa harga, langkau fetch")
    ap.add_argument("--grams", type=float)
    a = ap.parse_args()

    price, grams = (a.price, a.grams or round(100 / a.price, 4)) if a.price else fetch_gap()
    now = datetime.now(MYT)
    msg, new_state = build_message(price, grams, load_state(), now)
    if a.dry_run:
        print(html.unescape(re.sub(r"<[^>]+>", "", msg)))
        return
    send_telegram(msg)
    STATE_FILE.write_text(json.dumps(new_state, indent=2) + "\n")
    print("Dihantar.")


if __name__ == "__main__":
    sys.exit(main())

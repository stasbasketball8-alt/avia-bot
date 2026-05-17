import re
import logging
import threading
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8250112079:AAHEkW9AyhgeAXfMhP_SjmW_X-FTh4vlTL0"

AIRLINES = {"SU": "Аэрофлот", "3U": "Сычуаньские линии", "HU": "Хайнаньские линии", "MU": "Китайские восточные линии", "CZ": "Южно-китайские линии", "JD": "Пекинские линии", "VI": "Волга-Днепр", "CA": "Air China", "GS": "Тяньцзиньские линии", "4B": "Авиастар"}

AIRPORTS = {"PKX": "Пекин (Дасин)", "PEK": "Пекин (Столичный)", "PVG": "Шанхай (Пудун)", "HRB": "Харбин", "SVO": "Шереметьево", "SVO1": "Шереметьево-1", "SVO2": "Шереметьево-2", "BQS": "Благовещенск", "UUD": "Улан-Удэ", "TFU": "Чэнду (Тяньфу)", "HAK": "Хайкоу", "CGO": "Чжэнчжоу"}

def parse_etd(s):
    s = re.sub(r'(st|nd|rd|th)', '', s)
    if s.strip().isdigit():
        return s.strip() + "го числа"
    return "неизвестно"

def parse_frequency(s):
    if not s:
        return ""
    s = s.upper()
    if s == "DAILY":
        return "ежедневно"
    if s.startswith("DAY"):
        s = "D" + s[3:]
    m = re.search(r'D([1-7]+)', s)
    return f"{len(set(m.group(1)))} раз/нед" if m else s

def parse_route(r):
    if not r:
        return ""
    parts = r.split('-')
    return '-'.join(AIRPORTS.get(p.upper(), p) for p in parts)

def extract_airline(line):
    line = re.sub(r'^BY\s+', '', line.strip())
    for w in re.findall(r'\b([A-Z0-9]{2,3})\b', line):
        if w in AIRLINES:
            return w
    return None

def extract_route(line):
    m = re.search(r'([A-Z]{3})-([A-Z]{3})(?:-([A-Z]{3}))?', line)
    if m:
        return f"{m.group(1)}-{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
    return None

def extract_frequency(line):
    m = re.search(r'\b(D(?:AY)?[1-7]+)\b', line, re.I)
    if m:
        return m.group(1).upper()
    if re.search(r'\bDAILY\b', line, re.I):
        return "Daily"
    return None

def extract_etd(line):
    m = re.search(r'ETD\s+(\d+(?:st|nd|rd|th)?)', line, re.I)
    if m:
        return m.group(1)
    m2 = re.search(r'(?<!\d)(\d+(?:st|nd|rd|th)?)(?!\d)', line, re.I)
    if m2 and not m2.group(1).isdigit():
        return m2.group(1)
    return None

def extract_rate_and_extra(line):
    line = line.replace("UDS/KG", "USD/KG")
    m = re.search(r'(\d+(?:\.\d+)?)\s*USD\s*/\s*KG', line, re.I) or re.search(r'(\d+(?:\.\d+)?)\s*/\s*KG', line)
    rate = float(m.group(1)) if m else None
    extra = 0
    m2 = re.search(r'\+\s*(\d+)\s*USD', line, re.I)
    if m2:
        extra += float(m2.group(1))
    return rate, extra

def parse_fees_block(block, origin, dest, weight):
    total = 0.0
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        # AWB
        if line.startswith('AWB:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
        # CC
        elif line.startswith('CC:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
        # HC
        elif line.startswith('HC:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    val = float(m.group(1))
                    total += val * weight if '/KG' in line else val
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    val = float(m.group(1))
                    total += val * weight if '/KG' in line else val
        # Pick up fee
        elif 'Pick up fee' in line:
            # разбираем все части через запятую
            parts = line.split(',')
            best = 0
            for part in parts:
                mt = re.search(r'USD(\d+(?:\.\d+)?)\s*TO\s+([A-Z/]+)', part, re.I)
                if mt and origin in mt.group(2).upper().split('/'):
                    best = float(mt.group(1))
                    break
            total += best
        # Label fee, Customs, Doc, TC можно добавить позже
    return total

def process_offer(offer_line, fees_block, weight):
    # Убираем BY в начале
    offer_line = re.sub(r'^BY\s+', '', offer_line.strip())
    # Убираем комментарии в скобках (например, via UUD)
    offer_line = re.sub(r'\([^)]*\)', '', offer_line)
    # Извлекаем авиакомпанию
    code = extract_airline(offer_line)
    if not code:
        return None
    airline = AIRLINES[code]
    # Маршрут
    route_str = extract_route(offer_line)
    if not route_str:
        return None
    route_pretty = parse_route(route_str)
    origin = route_str.split('-')[0].upper()
    dest = route_str.split('-')[-1].upper()
    # Частота
    freq = extract_frequency(offer_line)
    freq_pretty = parse_frequency(freq) if freq else ""
    # ETD
    etd = extract_etd(offer_line)
    etd_pretty = parse_etd(etd) if etd else ""
    # Тариф и дополнительные фиксированные суммы
    rate, extra = extract_rate_and_extra(offer_line)
    if rate is None:
        return None
    total = rate * weight + extra
    # Общие сборы
    total += parse_fees_block(fees_block, origin, dest, weight)
    # Если есть inline Label fee (в строке перевозчика)
    m_label = re.search(r'Label fee\s*USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL\)', offer_line, re.I)
    if m_label:
        per_kg = float(m_label.group(1))
        min_val = float(m_label.group(2))
        total += max(per_kg * weight, min_val)
    return f"{round(total)} долларов {airline}, {route_pretty}, {freq_pretty}, места с {etd_pretty}".replace("  ", " ").strip()

def split_offers_and_fees(text):
    lines = text.splitlines()
    offers = []
    fees_lines = []
    in_fees = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(AWB|CC|HC|Pick up fee|back board fee|Label fee|Customs|Doc|TC)', line, re.I):
            in_fees = True
        if in_fees:
            fees_lines.append(line)
        else:
            offers.append(line)
    return offers, '\n'.join(fees_lines)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✈️ Бот для расчёта авиаставок. /weight 100")

async def set_weight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        w = float(ctx.args[0])
        ctx.user_data['weight'] = w
        await update.message.reply_text(f"✅ Вес {w} кг")
    except:
        await update.message.reply_text("❌ /weight 100")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    weight = ctx.user_data.get('weight')
    if weight is None:
        await update.message.reply_text("⚠️ Сначала /weight 100")
        return
    text = update.message.text
    offers, fees_block = split_offers_and_fees(text)
    if not offers:
        await update.message.reply_text("⚠️ Не найдены строки с авиакомпаниями")
        return
    results = []
    for off in offers:
        res = process_offer(off, fees_block, weight)
        if res:
            results.append(res)
        else:
            results.append(f"❌ Не удалось разобрать: {off[:80]}...")
    await update.message.reply_text("\n\n".join(results))

def run_bot():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    except:
        pass
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weight", set_weight))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен")
    app.run_polling()

def run_flask():
    app = Flask(__name__)
    @app.route('/', methods=['GET','HEAD'])
    def health():
        return "OK", 200
    app.run(host='0.0.0.0', port=8000, use_reloader=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()

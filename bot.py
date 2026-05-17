import re, logging, threading, requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8250112079:AAHEkW9AyhgeAXfMhP_SjmW_X-FTh4vlTL0"

AIRLINES = {
    "SU": "Аэрофлот", "3U": "Сычуаньские линии", "HU": "Хайнаньские линии",
    "MU": "Китайские восточные линии", "CZ": "Южно-китайские линии",
    "JD": "Пекинские линии", "VI": "Волга-Днепр", "CA": "Air China",
    "GS": "Тяньцзиньские линии", "4B": "Авиастар",
}

AIRPORTS = {
    "PKX": "Пекин (Дасин)", "PEK": "Пекин (Столичный)", "PVG": "Шанхай (Пудун)",
    "HRB": "Харбин", "SVO": "Шереметьево", "SVO1": "Шереметьево-1", "SVO2": "Шереметьево-2",
    "BQS": "Благовещенск", "UUD": "Улан-Удэ", "TFU": "Чэнду (Тяньфу)", "HAK": "Хайкоу",
    # добавьте другие при необходимости
}

# --- функции парсинга (полностью рабочие, включая IF и Pick up) ---
def parse_etd(s): return re.sub(r'(st|nd|rd|th)', '', s).strip() + "го числа" if s and s[0].isdigit() else "неизвестно"
def parse_frequency(s):
    if not s: return ""
    s = s.upper()
    if s == "DAILY": return "ежедневно"
    if s.startswith("DAY"): s = "D" + s[3:]
    m = re.search(r'D([1-7]+)', s)
    return f"{len(set(m.group(1)))} раз/нед" if m else s
def parse_route(r):
    if not r: return ""
    parts = r.split('-')
    return '-'.join(AIRPORTS.get(p.upper(), p) for p in parts)
def extract_airline_code(line):
    line = re.sub(r'^BY\s+', '', line.strip())
    for w in re.findall(r'\b([A-Z0-9]{2,3})\b', line):
        if w in AIRLINES: return w
    return None
def extract_route(line):
    m = re.search(r'([A-Z]{3})-([A-Z]{3})(?:-([A-Z]{3}))?', line)
    if m: return f"{m.group(1)}-{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
    return None
def extract_frequency(line):
    m = re.search(r'\b(D(?:AY)?[1-7]+)\b', line, re.I)
    if m: return m.group(1).upper()
    if re.search(r'\bDAILY\b', line, re.I): return "Daily"
    return None
def extract_etd(line):
    m = re.search(r'ETD\s+(\d+(?:st|nd|rd|th)?)', line, re.I)
    if m: return m.group(1)
    m2 = re.search(r'(?<!\d)(\d+(?:st|nd|rd|th)?)(?!\d)', line, re.I)
    return m2.group(1) if m2 and not m2.group(1).isdigit() else None
def extract_rate_and_extra(line):
    line = line.replace("UDS/KG", "USD/KG")
    rate = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*USD\s*/\s*KG', line, re.I) or re.search(r'(\d+(?:\.\d+)?)\s*/\s*KG', line)
    if m: rate = float(m.group(1))
    extra = 0
    m2 = re.search(r'\+\s*(\d+)\s*USD', line, re.I)
    if m2: extra += float(m2.group(1))
    return rate, extra
def extract_inline_fees(line):
    fees = []
    m = re.search(r'Label fee\s*USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL\)', line, re.I)
    if m: fees.append(('label', float(m.group(1)), float(m.group(2))))
    return fees
def parse_common_fees(block, orig, dest, weight):
    total = 0.0
    for line in block.splitlines():
        line = line.strip()
        if not line: continue
        # AWB
        if re.match(r'AWB:', line, re.I):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == orig or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m: total += float(m.group(1))
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m: total += float(m.group(1))
        # CC
        elif re.match(r'CC:', line, re.I):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == orig or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m: total += float(m.group(1))
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m: total += float(m.group(1))
        # HC
        elif re.match(r'HC:', line, re.I):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == orig or cond.group(1) == dest):
                m = re.search(r'USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    v = float(m.group(1))
                    total += v * weight if '/KG' in line else v
            elif not cond:
                m = re.search(r'USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    v = float(m.group(1))
                    total += v * weight if '/KG' in line else v
        # Pick up fee
        elif re.match(r'Pick up fee', line, re.I):
            parts = line.split(',')
            best = 0
            for part in parts:
                mt = re.search(r'USD(\d+(?:\.\d+)?)\s*TO\s+([A-Z/]+)', part, re.I)
                if mt and orig in mt.group(2).upper().split('/'):
                    best = float(mt.group(1))
                    break
            total += best
        # back board, Label fee, Customs, Doc, TC (можно добавить позже)
    return total

def process_offer(offer_line, common_block, weight):
    offer_line = re.sub(r'^BY\s+', '', offer_line.strip())
    code = extract_airline_code(offer_line)
    if not code: return None
    airline = AIRLINES.get(code, code)
    route_str = extract_route(offer_line)
    if not route_str: return None
    route = parse_route(route_str)
    orig = route_str.split('-')[0].upper()
    dest = route_str.split('-')[-1].upper()
    freq = extract_frequency(offer_line)
    freq_pretty = parse_frequency(freq) if freq else ""
    etd = extract_etd(offer_line)
    etd_pretty = parse_etd(etd) if etd else ""
    rate, extra = extract_rate_and_extra(offer_line)
    if rate is None: return None
    total = rate * weight + extra
    total += parse_common_fees(common_block, orig, dest, weight)
    # inline fees (Label fee)
    for ft, val, minv in extract_inline_fees(offer_line):
        if ft == 'label':
            total += max(val * weight, minv)
    return f"{round(total)} долларов {airline}, {route}, {freq_pretty}, места с {etd_pretty}".replace("  ", " ").strip()

def split_offers(text):
    lines = text.splitlines()
    offers, common = [], []
    in_common = False
    for line in lines:
        line = line.strip()
        if not line: continue
        if re.match(r'^(AWB|CC|HC|Pick up fee|back board fee|Customs|Doc|TC|Label fee)', line, re.I):
            in_common = True
        (common if in_common else offers).append(line)
    return offers, '\n'.join(common)

async def start(update, context):
    await update.message.reply_text("✈️ Бот готов. /weight 100, затем текст ставки.")
async def set_weight(update, context):
    try:
        context.user_data['weight'] = float(context.args[0])
        await update.message.reply_text(f"✅ Вес {context.args[0]} кг")
    except: await update.message.reply_text("❌ /weight 100")
async def handle(update, context):
    w = context.user_data.get('weight')
    if not w: return await update.message.reply_text("⚠️ Сначала /weight 100")
    offers, common = split_offers(update.message.text)
    if not offers: return await update.message.reply_text("⚠️ Не найдены строки авиакомпаний")
    results = []
    for off in offers:
        res = process_offer(off, common, w)
        results.append(res if res else f"❌ {off[:80]}...")
    await update.message.reply_text("\n\n".join(results))

def run_bot():
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weight", set_weight))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Бот запущен...")
    app.run_polling()

def run_flask():
    flask_app = Flask(__name__)
    @flask_app.route('/', methods=['GET','HEAD'])
    def health(): return "OK", 200
    flask_app.run(host='0.0.0.0', port=8000, use_reloader=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()

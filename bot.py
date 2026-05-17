import re
import logging
import threading
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8250112079:AAHEkW9AyhgeAXfMhP_SjmW_X-FTh4vlTL0"   # ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ТОКЕН

# ---------- Справочник авиакомпаний ----------
AIRLINES = {
    "SU": "Аэрофлот",
    "3U": "Сычуаньские линии",
    "HU": "Хайнаньские линии",
    "MU": "Китайские восточные линии",
    "CZ": "Южно-китайские линии",
    "JD": "Пекинские линии",
    "VI": "Волга-Днепр",
    "CA": "Air China",
    "GS": "Тяньцзиньские линии",
    "4B": "Авиастар",
}

# ---------- Справочник аэропортов (основные) ----------
AIRPORTS = {
    "PKX": "Пекин (Дасин)",
    "PEK": "Пекин (Столичный)",
    "PVG": "Шанхай (Пудун)",
    "SHA": "Шанхай (Хунцяо)",
    "CAN": "Гуанчжоу",
    "SZX": "Шэньчжэнь",
    "CTU": "Чэнду",
    "CKG": "Чунцин",
    "XIY": "Сиань",
    "HGH": "Ханчжоу",
    "NKG": "Нанкин",
    "KMG": "Куньмин",
    "XMN": "Сямынь",
    "TAO": "Циндао",
    "CSX": "Чанша",
    "URC": "Урумчи",
    "DLC": "Далянь",
    "HRB": "Харбин",
    "SHE": "Шэньян",
    "WUH": "Ухань",
    "KWL": "Гуйлинь",
    "SJW": "Шицзячжуан",
    "TNA": "Цзинань",
    "SVO": "Шереметьево",
    "SVO1": "Шереметьево-1",
    "SVO2": "Шереметьево-2",
    "DME": "Домодедово",
    "VKO": "Внуково",
    "LED": "Пулково",
    "KHV": "Хабаровск",
    "VVO": "Владивосток",
    "IKT": "Иркутск",
    "OVB": "Новосибирск",
    "KJA": "Красноярск",
    "UFA": "Уфа",
    "KZN": "Казань",
    "KUF": "Самара",
    "ROV": "Ростов-на-Дону",
    "AER": "Сочи",
    "BQS": "Благовещенск",
    "CGO": "Чжэнчжоу",
    "UUD": "Улан-Удэ",
    "TFU": "Чэнду (Тяньфу)",
    "HAK": "Хайкоу",
}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def parse_etd(etd_str):
    if not etd_str:
        return "неизвестно"
    s = re.sub(r'(st|nd|rd|th)', '', etd_str, flags=re.I)
    if s.strip().isdigit():
        return f"{s.strip()}го числа"
    return "неизвестно"

def parse_frequency(freq_str):
    if not freq_str:
        return ""
    s = freq_str.strip().upper()
    if s == "DAILY":
        return "ежедневно"
    if s.startswith("DAY"):
        s = "D" + s[3:]
    m = re.search(r'D([1-7]+)', s)
    if m:
        days = len(set(m.group(1)))
        return f"{days} раз/нед"
    return s

def parse_route(route_str):
    if not route_str:
        return ""
    parts = route_str.split('-')
    translated = [AIRPORTS.get(p.upper(), p) for p in parts]
    return '-'.join(translated)

def extract_airline(line):
    # Убираем BY в начале
    line = re.sub(r'^BY\s+', '', line.strip())
    words = re.findall(r'\b([A-Z0-9]{2,3})\b', line)
    for w in words:
        if w in AIRLINES:
            return w
    return None

def extract_route(line):
    m = re.search(r'([A-Z]{3})-([A-Z]{3})(?:-([A-Z]{3}))?', line)
    if m:
        if m.group(3):
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        else:
            return f"{m.group(1)}-{m.group(2)}"
    return None

def extract_frequency(line):
    m = re.search(r'\b(D(?:AY)?[1-7]+)\b', line, re.I)
    if m:
        return m.group(1).upper()
    if re.search(r'\bDAILY\b', line, re.I):
        return "Daily"
    return None

def extract_etd(line):
    # Вариант с ETD
    m = re.search(r'ETD\s+(\d+(?:st|nd|rd|th)?)', line, re.I)
    if m:
        return m.group(1)
    # Число с суффиксом без ETD, например 21TH
    m2 = re.search(r'\b(\d+(?:st|nd|rd|th))\b', line, re.I)
    if m2:
        return m2.group(1)
    # Число перед DAILY
    m3 = re.search(r'\b(\d+)\s+DAILY', line, re.I)
    if m3:
        return m3.group(1)
    return None

def extract_rate_and_extra(line):
    line = line.replace("UDS/KG", "USD/KG")
    m = re.search(r'(\d+(?:\.\d+)?)\s*USD\s*/\s*KG', line, re.I)
    if not m:
        m = re.search(r'(\d+(?:\.\d+)?)\s*/\s*KG', line)
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
        if line.startswith('AWB:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'IF\s+[A-Z]{3}\s+USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
            else:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
        elif line.startswith('CC:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'IF\s+[A-Z]{3}\s+USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
            else:
                m = re.search(r'USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if m:
                    total += float(m.group(1))
        elif line.startswith('HC:'):
            cond = re.search(r'IF\s+([A-Z]{3})', line, re.I)
            if cond and (cond.group(1) == origin or cond.group(1) == dest):
                m = re.search(r'IF\s+[A-Z]{3}\s+USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    val = float(m.group(1))
                    total += val * weight if '/KG' in line else val
            else:
                m = re.search(r'USD(\d+(?:\.\d+)?)(?:/KG)?', line, re.I)
                if m:
                    val = float(m.group(1))
                    total += val * weight if '/KG' in line else val
        elif 'Pick up fee' in line:
            parts = line.split(',')
            best = 0
            for part in parts:
                mt = re.search(r'USD(\d+(?:\.\d+)?)\s*TO\s+([A-Z/]+)', part, re.I)
                if mt and origin in mt.group(2).upper().split('/'):
                    best = float(mt.group(1))
                    break
            total += best
        # можно добавить другие сборы при необходимости
    return total

def process_offer(offer_line, fees_block, weight, index):
    # очистка строки
    offer_line = re.sub(r'^BY\s+', '', offer_line.strip())
    offer_line = re.sub(r'\([^)]*\)', '', offer_line)
    # авиакомпания
    code = extract_airline(offer_line)
    if not code:
        return None
    airline = AIRLINES[code]
    # маршрут
    route_str = extract_route(offer_line)
    if not route_str:
        return None
    route_pretty = parse_route(route_str)
    origin = route_str.split('-')[0].upper()
    dest = route_str.split('-')[-1].upper()
    # частота
    freq = extract_frequency(offer_line)
    freq_pretty = parse_frequency(freq) if freq else ""
    # ETD
    etd = extract_etd(offer_line)
    etd_pretty = parse_etd(etd) if etd else "неизвестно"
    # тариф
    rate, extra = extract_rate_and_extra(offer_line)
    if rate is None:
        return None
    total = rate * weight + extra
    total += parse_fees_block(fees_block, origin, dest, weight)
    # Label fee в строке
    m_label = re.search(r'Label fee\s*USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL\)', offer_line, re.I)
    if m_label:
        per_kg = float(m_label.group(1))
        min_val = float(m_label.group(2))
        total += max(per_kg * weight, min_val)
    # формируем вывод
    total_rounded = round(total)
    desc = f"{airline}, {route_pretty}, {freq_pretty}, места с {etd_pretty}".replace("  ", " ").strip()
    return f"{index}. {total_rounded} долларов\n   {desc}"

def split_offers_and_fees(text):
    lines = text.splitlines()
    offers = []
    fees = []
    in_fees = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(AWB|CC|HC|Pick up fee|back board fee|Label fee|Customs|Doc|TC)', line, re.I):
            in_fees = True
        if in_fees:
            fees.append(line)
        else:
            offers.append(line)
    return offers, '\n'.join(fees)

# ================= ОБРАБОТЧИКИ КОМАНД =================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✈️ Бот для расчёта авиаставок.\n"
        "1. /weight 100\n"
        "2. Отправьте текст ставки.\n"
        "Бот выдаст пронумерованные строки: цена и описание."
    )

async def set_weight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        w = float(ctx.args[0])
        ctx.user_data['weight'] = w
        await update.message.reply_text(f"✅ Вес установлен: {w} кг")
    except:
        await update.message.reply_text("❌ Используйте: /weight 100")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    weight = ctx.user_data.get('weight')
    if weight is None:
        await update.message.reply_text("⚠️ Сначала укажите вес командой /weight 100")
        return
    text = update.message.text
    offers, fees_block = split_offers_and_fees(text)
    if not offers:
        await update.message.reply_text("⚠️ Не найдены строки с авиакомпаниями. Проверьте формат.")
        return
    results = []
    for i, off in enumerate(offers, start=1):
        res = process_offer(off, fees_block, weight, i)
        if res:
            results.append(res)
        else:
            results.append(f"{i}. ❌ Не удалось разобрать: {off[:80]}...")
    await update.message.reply_text("\n\n".join(results))

# --- ЗАПУСК БОТА С FLASK ДЛЯ UPTIMEROBOT ---
def run_bot():
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        print("Webhook deleted")
    except Exception as e:
        print(f"Webhook error: {e}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weight", set_weight))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен и слушает сообщения...")
    app.run_polling()

def run_flask():
    flask_app = Flask(__name__)
    @flask_app.route('/', methods=['GET', 'HEAD'])
    def health():
        return "I'm alive!", 200
    flask_app.run(host='0.0.0.0', port=8000, use_reloader=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Запускаем Flask в фоновом потоке (для UptimeRobot)
    threading.Thread(target=run_flask, daemon=True).start()
    # Бот в главном потоке
    run_bot()

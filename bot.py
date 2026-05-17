import re
import logging
import threading
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8250112079:AAHEkW9AyhgeAXfMhP_SjmW_X-FTh4vlTL0"   # ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ТОКЕН

# ---------- Справочник авиакомпаний (код -> русское имя) ----------
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

# ---------- Справочник аэропортов ----------
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
    "FOC": "Фучжоу",
    "HRB": "Харбин",
    "SHE": "Шэньян",
    "WUH": "Ухань",
    "KWL": "Гуйлинь",
    "NGB": "Нинбо",
    "SJW": "Шицзячжуан",
    "TNA": "Цзинань",
    "HFE": "Хэфэй",
    "KHN": "Наньчан",
    "ZUH": "Чжухай",
    "LHW": "Ланьчжоу",
    "INC": "Иньчуань",
    "HET": "Хух-Хото",
    "BAV": "Баотоу",
    "WXN": "Ваньчжоу",
    "JJN": "Цюаньчжоу",
    "NNG": "Наньнин",
    "SWA": "Шаньтоу",
    "YNZ": "Яньчэн",
    "YNT": "Яньтай",
    "WEH": "Вэйхай",
    "ENH": "Эньши",
    "LYI": "Линьи",
    "XUZ": "Сюйчжоу",
    "WEF": "Вэйфан",
    "DOY": "Дунъин",
    "JNG": "Цзинин",
    "HYN": "Тайчжоу",
    "HSN": "Чжоушань",
    "LYG": "Ляньюньган",
    "NTG": "Наньтун",
    "YTY": "Янчжоу",
    "CZX": "Чанчжоу",
    "WUX": "Уси",
    "HZA": "Хэцзэ",
    "JHG": "Цзинхун",
    "LJG": "Лицзян",
    "DIG": "Шангри-Ла",
    "ZAT": "Чжаотун",
    "LUM": "Манши",
    "BSD": "Баошань",
    "TCZ": "Тэнчун",
    "LXA": "Лхаса",
    "YIC": "Ичунь",
    "KOW": "Ганьчжоу",
    "YIH": "Ичан",
    "BFU": "Бэнбу",
    "FUG": "Фуян",
    "AQG": "Аньцин",
    "JXA": "Цзиси",
    "JGD": "Цзягэдаци",
    "NZH": "Маньчжоули",
    "HLD": "Хайлар",
    "XIL": "Силинь-Хото",
    "TGO": "Тунляо",
    "NZL": "Чжаланьтунь",
    "YIE": "Аршань",
    "ERL": "Эрэн-Хото",
    "DSN": "Дондшэн",
    "HDG": "Ханьдань",
    "CIH": "Чанчжи",
    "WUT": "Синьчжоу",
    "LLV": "Люйлян",
    "YGH": "Юнцзи",
    "AOG": "Аньшань",
    "DDG": "Даньдун",
    "JNZ": "Цзиньчжоу",
    "CHG": "Чаоян",
    "XFN": "Сянъян",
    "HPG": "Шэньнунцзя",
    "HUZ": "Хуэйчжоу",
    "FUO": "Фошань",
    "MXZ": "Мэйчжоу",
    "ZHA": "Чжаньцзян",
    "BHY": "Бэйхай",
    "LYA": "Лоян",
    "NNY": "Наньян",
    "WZU": "Вэйчжоу",
    "DYG": "Чжанцзяцзе",
    "HJJ": "Хуайхуа",
    "CGD": "Чандэ",
    "HNY": "Хэнъян",
    "LLF": "Юнчжоу",
    "LCX": "Ляньчэн",
    "YBP": "Ибинь",
    "GYS": "Гуанъюань",
    "LZO": "Лучжоу",
    "NAO": "Наньчун",
    "DCY": "Даочэн",
    "JZH": "Цзючжайгоу",
    "PZI": "Паньчжихуа",
    "XIC": "Сичан",
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
    "MRV": "Минеральные Воды",
    "KRR": "Краснодар",
    "VOG": "Волгоград",
    "SOK": "Саратов",
    "ULV": "Ульяновск",
    "CEK": "Челябинск",
    "TJM": "Тюмень",
    "SVX": "Екатеринбург",
    "MQF": "Магнитогорск",
    "NBC": "Нижнекамск",
    "NFG": "Нижневартовск",
    "SGC": "Сургут",
    "HMA": "Ханты-Мансийск",
    "BQS": "Благовещенск",
    "CGO": "Чжэнчжоу",
    "UUD": "Улан-Удэ",
    "TFU": "Чэнду (Тяньфу)",
    "HAK": "Хайкоу",
}

# ---------- ФУНКЦИИ ПАРСИНГА ----------
def parse_etd(etd_str):
    if not etd_str:
        return "неизвестно"
    etd_clean = re.sub(r'(st|nd|rd|th)', '', etd_str, flags=re.I)
    months = {
        "JAN": "января", "FEB": "февраля", "MAR": "марта", "APR": "апреля",
        "MAY": "мая", "JUN": "июня", "JUL": "июля", "AUG": "августа",
        "SEP": "сентября", "OCT": "октября", "NOV": "ноября", "DEC": "декабря"
    }
    for eng, rus in months.items():
        if eng in etd_clean.upper():
            etd_clean = etd_clean.upper().replace(eng, rus)
            return etd_clean.capitalize()
    if etd_clean.strip().isdigit():
        return f"{etd_clean}го числа"
    return etd_clean

def parse_frequency(freq_str):
    if not freq_str:
        return "расписание не указано"
    freq_str = freq_str.strip().upper()
    if freq_str == "DAILY":
        return "ежедневно"
    if freq_str.startswith("DAY"):
        freq_str = "D" + freq_str[3:]
    match = re.search(r'D([1-7]+)', freq_str)
    if match:
        days = len(set(match.group(1)))
        return f"{days} раз/нед"
    return freq_str

def parse_route(route_str):
    if not route_str:
        return "маршрут не указан"
    segments = route_str.split('-')
    translated = [AIRPORTS.get(seg.upper(), seg) for seg in segments]
    return '-'.join(translated)

def extract_airline_code(line):
    # Удаляем "BY " в начале
    line = re.sub(r'^BY\s+', '', line.strip())
    # Ищем слова из 2-3 символов (буквы и цифры) из списка AIRLINES
    words = re.findall(r'\b([A-Z0-9]{2,3})\b', line)
    for word in words:
        if word in AIRLINES:
            return word
    return None

def extract_route(line):
    # Ищем последовательность из 2 или 3 аэропортов
    match = re.search(r'([A-Z]{3})-([A-Z]{3})(?:-([A-Z]{3}))?', line)
    if match:
        if match.group(3):
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        else:
            return f"{match.group(1)}-{match.group(2)}"
    return None

def extract_frequency(line):
    match = re.search(r'\b(D(?:AY)?[1-7]+)\b', line, re.I)
    if match:
        return match.group(1).upper()
    if re.search(r'\bDAILY\b', line, re.I):
        return "Daily"
    return None

def extract_etd(line):
    # Ищем ETD число с суффиксом
    match = re.search(r'ETD\s+(\d+(?:st|nd|rd|th)?)', line, re.I)
    if match:
        return match.group(1)
    # Ищем просто число с суффиксом (не цифры)
    match2 = re.search(r'(?<!\d)(\d+(?:st|nd|rd|th)?)(?!\d)', line, re.I)
    if match2 and not match2.group(1).isdigit():
        return match2.group(1)
    return None

def extract_rate_and_extra_from_line(line):
    rate = None
    extra = 0.0
    line = line.replace("UDS/KG", "USD/KG").replace("UDS/ KG", "USD/KG")
    # Тариф
    match = re.search(r'(\d+(?:\.\d+)?)\s*USD\s*/\s*KG', line, re.I)
    if not match:
        match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*KG', line)
    if match:
        rate = float(match.group(1))
    # Дополнительная фиксированная сумма
    match_extra = re.search(r'\+\s*(\d+)\s*USD', line, re.I)
    if match_extra:
        extra += float(match_extra.group(1))
    # Forklift
    match_fork = re.search(r'\+.*?Forklift\s*USD(\d+(?:\.\d+)?)/BL', line, re.I)
    if match_fork:
        extra += float(match_fork.group(1))
    return rate, extra

def extract_inline_fees(line):
    fees = []
    match = re.search(r'Label fee\s*USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL\)', line, re.I)
    if match:
        fees.append(('label', float(match.group(1)), float(match.group(2))))
    return fees

def parse_common_fees(fees_block, origin_airport, dest_airport, weight):
    """
    Разбирает блок общих сборов. Поддерживает условия вида:
    AWB: USD35/BL IF HRB USD50/BL
    CC: USD40/BL IF HRB USD50/BL
    """
    total = 0.0
    if not fees_block:
        return total
    lines = fees_block.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Обрабатываем каждую строку независимо
        # AWB
        if re.match(r'AWB:', line, re.I):
            # Поиск условия IF X
            condition_match = re.search(r'IF\s+([A-Z]{3})\s+USD(\d+(?:\.\d+)?)/BL', line, re.I)
            if condition_match:
                airport_cond = condition_match.group(1).upper()
                value_if = float(condition_match.group(2))
                # Если условие совпадает с аэропортом отправления или назначения
                if airport_cond in (origin_airport, dest_airport):
                    total += value_if
                else:
                    # Ищем значение по умолчанию (до IF)
                    default_match = re.search(r'AWB:\s*USD(\d+(?:\.\d+)?)/BL', line, re.I)
                    if default_match:
                        total += float(default_match.group(1))
            else:
                # Нет условия, просто значение
                default_match = re.search(r'AWB:\s*USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if default_match:
                    total += float(default_match.group(1))
        # CC
        elif re.match(r'CC:', line, re.I):
            condition_match = re.search(r'IF\s+([A-Z]{3})\s+USD(\d+(?:\.\d+)?)/BL', line, re.I)
            if condition_match:
                airport_cond = condition_match.group(1).upper()
                value_if = float(condition_match.group(2))
                if airport_cond in (origin_airport, dest_airport):
                    total += value_if
                else:
                    default_match = re.search(r'CC:\s*USD(\d+(?:\.\d+)?)/BL', line, re.I)
                    if default_match:
                        total += float(default_match.group(1))
            else:
                default_match = re.search(r'CC:\s*USD(\d+(?:\.\d+)?)/BL', line, re.I)
                if default_match:
                    total += float(default_match.group(1))
        # HC
        elif re.match(r'HC:', line, re.I):
            # HC: USD100 (может быть без привязки)
            # Или HC: USD0.05/KG (за кг)
            # Или HC: USD0.05/KG to CAN (привязка)
            match_to = re.search(r'to\s+([A-Z]{3})', line, re.I)
            if match_to:
                airport_code = match_to.group(1).upper()
                if airport_code == origin_airport or airport_code == dest_airport:
                    # Ищем значение за кг или фикс
                    match_val = re.search(r'USD(\d+(?:\.\d+)?)/KG', line, re.I)
                    if match_val:
                        total += float(match_val.group(1)) * weight
                    else:
                        match_fix = re.search(r'USD(\d+(?:\.\d+)?)(?!/KG)', line, re.I)
                        if match_fix:
                            total += float(match_fix.group(1))
            else:
                # Нет привязки - применяем ко всем
                match_val = re.search(r'USD(\d+(?:\.\d+)?)/KG', line, re.I)
                if match_val:
                    total += float(match_val.group(1)) * weight
                else:
                    match_fix = re.search(r'USD(\d+(?:\.\d+)?)(?!/KG)', line, re.I)
                    if match_fix:
                        total += float(match_fix.group(1))
        # Pick up fee
        elif re.match(r'Pick up fee', line, re.I):
            if origin_airport:
                # Ищем USDxxx TO origin_airport
                pattern = rf'USD(\d+(?:\.\d+)?)\s*TO\s+.*?\b{origin_airport}\b'
                match = re.search(pattern, line, re.I)
                if not match:
                    # Возможно перечисление через слеш: TO PKX/PEK
                    pattern2 = rf'USD(\d+(?:\.\d+)?)\s*TO\s+([A-Z/]+)'
                    m2 = re.search(pattern2, line, re.I)
                    if m2 and origin_airport in m2.group(2).upper().split('/'):
                        total += float(m2.group(1))
                else:
                    total += float(match.group(1))
        # back board fee
        elif re.match(r'back board fee', line, re.I):
            match = re.search(r'USD(\d+(?:\.\d+)?)/KG', line, re.I)
            if match:
                total += float(match.group(1)) * weight
        # Label fee
        elif re.match(r'Label fee', line, re.I):
            match = re.search(r'USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL\)', line, re.I)
            if match:
                per_kg = float(match.group(1))
                min_val = float(match.group(2))
                total += max(per_kg * weight, min_val)
        # Customs
        elif re.match(r'Customs:', line, re.I):
            match = re.search(r'(\d+(?:\.\d+)?)/BL', line, re.I)
            if match:
                total += float(match.group(1))
        # Doc
        elif re.match(r'Doc:', line, re.I):
            match = re.search(r'(\d+(?:\.\d+)?)/BL', line, re.I)
            if match:
                total += float(match.group(1))
        # TC
        elif re.match(r'TC:', line, re.I):
            match = re.search(r'(\d+(?:\.\d+)?)/KG,\s*Min\s*(\d+)/Shpt', line, re.I)
            if match:
                per_kg = float(match.group(1))
                min_val = float(match.group(2))
                total += max(per_kg * weight, min_val)
    return total

def process_offer(offer_line, common_fees_block, weight):
    # Очистка и предобработка
    offer_line = offer_line.replace("UDS/KG", "USD/KG").replace("UDS/ KG", "USD/KG")
    offer_line = re.sub(r'^BY\s+', '', offer_line.strip())
    
    airline_code = extract_airline_code(offer_line)
    if not airline_code:
        return None
    airline_name = AIRLINES.get(airline_code, airline_code)

    route_str = extract_route(offer_line)
    if not route_str:
        return None
    route_pretty = parse_route(route_str)
    origin_airport = route_str.split('-')[0].upper()
    dest_airport = route_str.split('-')[-1].upper()

    freq = extract_frequency(offer_line)
    if not freq:
        return None
    freq_pretty = parse_frequency(freq)

    etd = extract_etd(offer_line)
    if not etd:
        return None
    etd_pretty = parse_etd(etd)

    rate, extra = extract_rate_and_extra_from_line(offer_line)
    if rate is None:
        return None

    total = rate * weight + extra
    total += parse_common_fees(common_fees_block, origin_airport, dest_airport, weight)

    inline_fees = extract_inline_fees(offer_line)
    for fee_type, val, min_val in inline_fees:
        if fee_type == 'label':
            fee_amount = val * weight
            if min_val:
                fee_amount = max(fee_amount, min_val)
            total += fee_amount

    total_rounded = round(total)
    result = f"{total_rounded} долларов {airline_name}, {route_pretty}, {freq_pretty}, места с {etd_pretty}"
    return result

def split_into_offers_and_common_fees(full_text):
    lines = full_text.strip().splitlines()
    offers = []
    common_lines = []
    in_common = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Если строка начинается с ключевых слов сборов, переключаемся в блок общих сборов
        if re.match(r'^(AWB|CC|HC|Pick up fee|back board fee|Customs|Doc|TC|Label fee)', line, re.I):
            in_common = True
        if in_common:
            common_lines.append(line)
        else:
            offers.append(line)
    common_block = "\n".join(common_lines)
    return offers, common_block

# ================= ОБРАБОТЧИКИ КОМАНД =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✈️ Бот для расчёта авиаставок.\n"
        "1. Установите вес командой /weight 100\n"
        "2. Пришлите текст ставки (можно копировать несколько строк).\n"
        "Бот сам найдёт перевозчиков, маршруты, сборы и выдаст итог по каждому предложению."
    )

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(context.args[0])
        context.user_data['weight'] = weight
        await update.message.reply_text(f"✅ Вес установлен: {weight} кг. Теперь присылайте ставку.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Используйте: /weight 100 (число в кг)")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    weight = context.user_data.get('weight')
    if weight is None:
        await update.message.reply_text("⚠️ Сначала укажите вес командой /weight 100")
        return
    text = update.message.text
    offers, common_block = split_into_offers_and_common_fees(text)
    if not offers:
        await update.message.reply_text("⚠️ Не удалось найти строки с авиакомпаниями. Проверьте формат.")
        return
    results = []
    for offer in offers:
        res = process_offer(offer, common_block, weight)
        if res:
            results.append(res)
        else:
            results.append(f"❌ Не удалось разобрать: {offer[:100]}...")
    if results:
        await update.message.reply_text("\n\n".join(results))
    else:
        await update.message.reply_text("⚠️ Ни одной ставки не обработано. Возможно, не хватает данных.")

# --- ОСНОВНАЯ ФУНКЦИЯ БОТА ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weight", set_weight))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()

# --- ЗАПУСК FLASK В ФОНОВОМ ПОТОКЕ ДЛЯ UPTIMEROBOT ---
def run_flask():
    flask_app = Flask(__name__)
    @flask_app.route('/', methods=['GET', 'HEAD'])
    def health_check():
        if request.method == 'HEAD':
            return '', 200
        return "I'm alive!", 200
    flask_app.run(host='0.0.0.0', port=8000, use_reloader=False)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Запускаем Flask в фоновом потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    # Запускаем основного бота в главном потоке
    main()

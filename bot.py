import re
import logging
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

# ---------- Справочник аэропортов (IATA -> русское имя) ----------
AIRPORTS = {
    # Китай
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
    "Riz": "Жичжао",
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
    "YIC": "Ичунь (Цзянси)",
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
    "XNT": "Синтай",
    "AVA": "Аньшунь",
    "ACX": "Синъи",
    "KWE": "Гуйян",
    "TEN": "Тунжэнь",
    "HXD": "Дэлинха",
    "HMI": "Хами",
    "KRL": "Корла",
    "KCA": "Куча",
    "IQM": "Цемо",
    "YIN": "Инин",
    "NLT": "Наймань",
    "HTN": "Хотан",
    "AKU": "Аксу",
    "AAT": "Алтай",
    "TCG": "Тачэн",
    "KJI": "Канас",
    "FYN": "Фу Юнь",
    "ZYI": "Цзуньи",
    "WMT": "Вэйнин",
    "LPF": "Люпаньшуй",
    "BFJ": "Бицзе",
    "HZH": "Липин",
    "KJH": "Кайли",
    "TXN": "Хуаншань",
    "JIQ": "Цяньцзян",
    "CQW": "Ваньчжоу",
    "XSB": "Шахджаханпур",
    # Россия
    "SVO": "Шереметьево",
    "SVO1": "Шереметьево-1",
    "SVO2": "Шереметьево-2",
    "DME": "Домодедово",
    "VKO": "Внуково",
    "LED": "Пулково",
    "KHV": "Хабаровск",
    "VVO": "Владивосток",
    "IKT": "Иркутск",
    "OVB": "Новосибирск (Толмачёво)",
    "KJA": "Красноярск",
    "UFA": "Уфа",
    "KZN": "Казань",
    "PEZ": "Пенза",
    "KUF": "Самара",
    "ROV": "Ростов-на-Дону",
    "AER": "Сочи",
    "MRV": "Минеральные Воды",
    "EGO": "Белгород",
    "VOZ": "Воронеж",
    "LPK": "Липецк",
    "TBW": "Тамбов",
    "BCX": "Белорецк",
    "UUA": "Бугульма",
    "JOK": "Йошкар-Ола",
    "CSY": "Чебоксары",
    "KSZ": "Котлас",
    "VKT": "Воркута",
    "USK": "Усинск",
    "PEX": "Печора",
    "SCT": "Сахалин (Южно-Сахалинск)",
    "UUS": "Южно-Сахалинск",
    "PKC": "Петропавловск-Камчатский",
    "GDX": "Магадан",
    "DYR": "Анадырь",
    "PVS": "Провидения",
    "BQG": "Богородское",
    "TJM": "Тюмень",
    "SVX": "Екатеринбург (Кольцово)",
    "CEK": "Челябинск",
    "MQF": "Магнитогорск",
    "NBC": "Нижнекамск (Бегишево)",
    "KGP": "Когалым",
    "NFG": "Нижневартовск",
    "SGC": "Сургут",
    "HMA": "Ханты-Мансийск",
    "NYM": "Надым",
    "SLY": "Салехард",
    "NOJ": "Ноябрьск",
    "TQL": "Тарко-Сале",
    "RAT": "Радужный",
    "URJ": "Урай",
    "IJK": "Ижевск",
    "KMW": "Кострома",
    "RYB": "Рыбинск",
    "IWA": "Иваново",
    "VGD": "Вологда",
    "VLU": "Великие Луки",
    "PSK": "Псков",
    "KLF": "Калуга",
    "RVZ": "Рассказово",
    "OSF": "Остафьево",
    "BKA": "Быково",
    "MOW": "Москва (обобщённо)",
    "ZIA": "Жуковский",
    "URS": "Курск",
    "URO": "Орёл",
    "KLD": "Тверь (Мигалово)",
    "RYZ": "Рязань",
    "NNM": "Нарьян-Мар",
    "VUS": "Великий Устюг",
    "CEE": "Череповец",
    "KVX": "Киров",
    "KRR": "Краснодар",
    "EIK": "Ейск",
    "AAQ": "Анапа",
    "TGK": "Таганрог",
    "ESL": "Элиста",
    "OGZ": "Владикавказ",
    "GRV": "Грозный",
    "MCX": "Махачкала",
    "NAL": "Нальчик",
    "STW": "Ставрополь",
    "ASF": "Астрахань",
    "VOG": "Волгоград",
    "SOK": "Саратов",
    "RTW": "Саратов (Центральный)",
    "ULV": "Ульяновск",
    "UIK": "Усть-Илимск",
    "BTK": "Братск",
    "NZR": "Улан-Удэ",
    "HTA": "Чита",
    "BQS": "Благовещенск",
    "NER": "Нерюнгри",
    "MJZ": "Мирный",
    "OLZ": "Олёкминск",
    "LKN": "Ленск",
    "PYJ": "Полярный",
    "IXT": "Пасани",
    "TOD": "Тируваннамалай",
}

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def parse_etd(etd_str):
    """Преобразует ETD: '21st' -> '21го числа', '18 MAY' -> '18 мая'"""
    if not etd_str:
        return "неизвестно"
    etd_str = etd_str.strip()
    # Убираем st, nd, rd, th
    etd_clean = re.sub(r'(st|nd|rd|th)', '', etd_str, flags=re.I)
    # Месяцы
    months = {
        "JAN":"января", "FEB":"февраля", "MAR":"марта", "APR":"апреля",
        "MAY":"мая", "JUN":"июня", "JUL":"июля", "AUG":"августа",
        "SEP":"сентября", "OCT":"октября", "NOV":"ноября", "DEC":"декабря"
    }
    for eng, rus in months.items():
        if eng in etd_clean.upper():
            etd_clean = etd_clean.upper().replace(eng, rus)
            return etd_clean.capitalize()
    # Если просто число
    if etd_clean.isdigit():
        return f"{etd_clean}го числа"
    return etd_clean

def parse_frequency(freq_str):
    """Преобразует D12467 -> '5 раз/нед', Daily -> 'ежедневно'"""
    if not freq_str:
        return "расписание не указано"
    freq_str = freq_str.strip().upper()
    if freq_str == "DAILY":
        return "ежедневно"
    match = re.search(r'D([1-7]+)', freq_str)
    if match:
        days = len(set(match.group(1)))
        return f"{days} раз/нед"
    return freq_str

def parse_route(route_str):
    """PKX-SVO1 -> 'Пекин (Дасин)-Шереметьево1'"""
    if not route_str:
        return "маршрут не указан"
    parts = route_str.split('-')
    if len(parts) == 2:
        orig = AIRPORTS.get(parts[0].upper(), parts[0])
        dest = AIRPORTS.get(parts[1].upper(), parts[1])
        return f"{orig}-{dest}"
    return route_str

def extract_rate_and_extra_from_line(line):
    """Из строки возвращает (rate, extra_fee)"""
    rate = None
    extra = 0.0
    # Ищем базовый тариф: число перед USD/KG или /KG
    match = re.search(r'(\d+(?:\.\d+)?)\s*USD\s*/\s*KG', line, re.I)
    if not match:
        match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*KG', line)
    if match:
        rate = float(match.group(1))
    # Ищем доп. фиксированную сумму: +159USD
    match_extra = re.search(r'\+\s*(\d+)\s*USD', line, re.I)
    if match_extra:
        extra = float(match_extra.group(1))
    return rate, extra

def extract_airline_code(line):
    """Извлекает код авиакомпании из строки"""
    words = line.split()
    for word in words:
        if word.upper() in AIRLINES:
            return word.upper()
    return None

def extract_route(line):
    """Ищет XXX-XXXX (аэропорты)"""
    match = re.search(r'([A-Z]{3})-([A-Z0-9]{3,4})', line)
    if match:
        return match.group(0)
    return None

def extract_frequency(line):
    """Ищет D1234567 или Daily/DAILY"""
    match = re.search(r'\b(D[1-7]+)\b', line, re.I)
    if match:
        return match.group(1).upper()
    if re.search(r'\bDAILY\b', line, re.I):
        return "Daily"
    return None

def extract_etd(line):
    """Ищет ETD 21st или ETD 18 MAY, или просто 21st/18 MAY"""
    match = re.search(r'ETD\s+(\d+(?:st|nd|rd|th)?\s*(?:[A-Z]+)?)', line, re.I)
    if match:
        return match.group(1)
    # Если нет ETD, ищем число с st/nd/rd/th или месяц
    match2 = re.search(r'\b(\d+(?:st|nd|rd|th)?\s*(?:[A-Z]{3,})?)\b', line)
    if match2 and not match2.group(0).isdigit():
        return match2.group(0)
    return None

def parse_common_fees(fees_block, origin_airport, weight):
    """Из блока общих сборов возвращает сумму"""
    total = 0.0
    if not fees_block:
        return total

    # AWB: USD35/BL
    match = re.search(r'AWB:\s*USD(\d+(?:\.\d+)?)/BL', fees_block, re.I)
    if match:
        total += float(match.group(1))
    # CC: USD40/BL
    match = re.search(r'CC:\s*USD(\d+(?:\.\d+)?)/BL', fees_block, re.I)
    if match:
        total += float(match.group(1))
    # HC: USD30
    match = re.search(r'HC:\s*USD(\d+(?:\.\d+)?)(?:/BL)?', fees_block, re.I)
    if match:
        total += float(match.group(1))
    # Pick up fee: USD60 TO PVG или USD65 TO PKX/CAN
    if origin_airport:
        # Ищем точное совпадение TO XXX
        pattern = rf'Pick up fee:.*?USD(\d+(?:\.\d+)?)\s*TO\s+.*?\b{origin_airport}\b'
        match = re.search(pattern, fees_block, re.I | re.DOTALL)
        if match:
            total += float(match.group(1))
        else:
            # Возможно аэропорты перечислены через слэш: PKX/CAN
            pattern2 = rf'Pick up fee:.*?USD(\d+(?:\.\d+)?)\s*TO\s+([A-Z/]+)'
            m2 = re.search(pattern2, fees_block, re.I)
            if m2:
                airports_str = m2.group(2).upper()
                if origin_airport in airports_str.split('/'):
                    total += float(m2.group(1))
    # back board fee USD0.05/KG
    match = re.search(r'back board fee\s*USD(\d+(?:\.\d+)?)/KG', fees_block, re.I)
    if match:
        total += float(match.group(1)) * weight
    # Label fee USD0.05/KG (Min USD25/BL)
    match = re.search(r'Label fee\s*USD(\d+(?:\.\d+)?)/KG\s*\(Min\s*USD(\d+)/BL', fees_block, re.I)
    if match:
        per_kg = float(match.group(1))
        min_val = float(match.group(2))
        val = per_kg * weight
        total += max(val, min_val)
    # Customs: 50/BL
    match = re.search(r'Customs:\s*(\d+(?:\.\d+)?)/BL', fees_block, re.I)
    if match:
        total += float(match.group(1))
    # Doc: 20/BL
    match = re.search(r'Doc:\s*(\d+(?:\.\d+)?)/BL', fees_block, re.I)
    if match:
        total += float(match.group(1))
    # TC: 0.1/KG, Min 25/Shpt
    match = re.search(r'TC:\s*(\d+(?:\.\d+)?)/KG,\s*Min\s*(\d+)/Shpt', fees_block, re.I)
    if match:
        per_kg = float(match.group(1))
        min_val = float(match.group(2))
        val = per_kg * weight
        total += max(val, min_val)
    return total

def process_offer(offer_line, common_fees_block, weight):
    """Обрабатывает одну строку с авиакомпанией. Возвращает итоговую строку или None"""
    airline_code = extract_airline_code(offer_line)
    if not airline_code:
        return None
    airline_name = AIRLINES.get(airline_code, airline_code)

    route_str = extract_route(offer_line)
    if not route_str:
        return None
    route_pretty = parse_route(route_str)
    origin_airport = route_str.split('-')[0].upper()

    freq = extract_frequency(offer_line)
    if not freq:
        return None
    freq_pretty = parse_frequency(freq)

    etd = extract_etd(offer_line)
    if not etd:
        return None
    etd_pretty = parse_etd(etd)

    rate, extra_in_line = extract_rate_and_extra_from_line(offer_line)
    if rate is None:
        return None

    total = rate * weight + extra_in_line
    total += parse_common_fees(common_fees_block, origin_airport, weight)

    total_rounded = round(total)
    result = f"{total_rounded} долларов {airline_name}, {route_pretty}, {freq_pretty}, места с {etd_pretty}"
    return result

def split_into_offers_and_common_fees(full_text):
    """Разделяет текст на список строк-офферов и блок общих сборов"""
    lines = full_text.strip().splitlines()
    offers = []
    common_lines = []
    in_common = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(AWB|CC|HC|Pick up fee|back board fee|Customs|Doc|TC|Label fee)', line, re.I):
            in_common = True
        if in_common:
            common_lines.append(line)
        else:
            offers.append(line)
    common_block = "\n".join(common_lines)
    return offers, common_block

# ================= ОБРАБОТЧИКИ БОТА =================
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
            # Показываем, какую строку не смогли разобрать
            results.append(f"❌ Не удалось разобрать: {offer[:100]}...")
    if results:
        await update.message.reply_text("\n\n".join(results))
    else:
        await update.message.reply_text("⚠️ Ни одной ставки не обработано. Возможно, не хватает данных (маршрут, частота, ETD, тариф).")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weight", set_weight))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

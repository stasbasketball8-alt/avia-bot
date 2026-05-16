import re
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================= НАСТРОЙКИ =================
# ВАЖНО: ВСТАВЬТЕ СЮДА ВАШ ТОКЕН ОТ @BotFather
BOT_TOKEN = "8250112079:AAHEkW9AyhgeAXfMhP_SjmW_X-FTh4vlTL0"

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

# ---------- Справочник аэропортов ----------
AIRPORTS = {
    "PKX": "Пекин (Дасин)", "PEK": "Пекин (Столичный)", "PVG": "Шанхай (Пудун)",
    "SHA": "Шанхай (Хунцяо)", "CAN": "Гуанчжоу", "SZX": "Шэньчжэнь",
    "CTU": "Чэнду", "CKG": "Чунцин", "XIY": "Сиань", "HGH": "Ханчжоу",
    "NKG": "Нанкин", "KMG": "Куньмин", "XMN": "Сямынь", "TAO": "Циндао",
    "CSX": "Чанша", "URC": "Урумчи", "DLC": "Далянь", "FOC": "Фучжоу",
    "HRB": "Харбин", "SHE": "Шэньян", "WUH": "Ухань", "KWL": "Гуйлинь",
    "NGB": "Нинбо", "SJW": "Шицзячжуан", "TNA": "Цзинань", "HFE": "Хэфэй",
    "KHN": "Наньчан", "ZUH": "Чжухай", "LHW": "Ланьчжоу", "INC": "Иньчуань",
    "HET": "Хух-Хото", "BAV": "Баотоу", "WXN": "Ваньчжоу", "JJN": "Цюаньчжоу",
    "NNG": "Наньнин", "SWA": "Шаньтоу", "YNZ": "Яньчэн", "YNT": "Яньтай",
    "WEH": "Вэйхай", "ENH": "Эньши", "LYI": "Линьи", "XUZ": "Сюйчжоу",
    "WEF": "Вэйфан", "DOY": "Дунъин", "JNG": "Цзинин", "HYN": "Тайчжоу",
    "HSN": "Чжоушань", "LYG": "Ляньюньган", "NTG": "Наньтун", "YTY": "Янчжоу",
    "CZX": "Чанчжоу", "WUX": "Уси", "HZA": "Хэцзэ", "JHG": "Цзинхун",
    "LJG": "Лицзян", "DIG": "Шангри-Ла", "ZAT": "Чжаотун", "LUM": "Манши",
    "BSD": "Баошань", "TCZ": "Тэнчун", "LXA": "Лхаса", "YIC": "Ичунь",
    "KOW": "Ганьчжоу", "YIH": "Ичан", "BFU": "Бэнбу", "FUG": "Фуян",
    "AQG": "Аньцин", "JXA": "Цзиси", "JGD": "Цзягэдаци", "NZH": "Маньчжоули",
    "HLD": "Хайлар", "XIL": "Силинь-Хото", "TGO": "Тунляо", "NZL": "Чжаланьтунь",
    "YIE": "Аршань", "ERL": "Эрэн-Хото", "DSN": "Дондшэн", "HDG": "Ханьдань",
    "CIH": "Чанчжи", "WUT": "Синьчжоу", "LLV": "Люйлян", "YGH": "Юнцзи",
    "AOG": "Аньшань", "DDG": "Даньдун", "JNZ": "Цзиньчжоу", "CHG": "Чаоян",
    "XFN": "Сянъян", "HPG": "Шэньнунцзя", "HUZ": "Хуэйчжоу", "FUO": "Фошань",
    "MXZ": "Мэйчжоу", "ZHA": "Чжаньцзян", "BHY": "Бэйхай", "LYA": "Лоян",
    "NNY": "Наньян", "WZU": "Вэйчжоу", "DYG": "Чжанцзяцзе", "HJJ": "Хуайхуа",
    "CGD": "Чандэ", "HNY": "Хэнъян", "LLF": "Юнчжоу", "LCX": "Ляньчэн",
    "YBP": "Ибинь", "GYS": "Гуанъюань", "LZO": "Лучжоу", "NAO": "Наньчун",
    "DCY": "Даочэн", "JZH": "Цзючжайгоу", "PZI": "Паньчжихуа", "XIC": "Сичан",
    "SVO": "Шереметьево", "SVO1": "Шереметьево-1", "DME": "Домодедово",
    "VKO": "Внуково", "LED": "Пулково", "KHV": "Хабаровск", "VVO": "Владивосток",
    "IKT": "Иркутск", "OVB": "Новосибирск", "KJA": "Красноярск", "UFA": "Уфа",
    "KZN": "Казань", "KUF": "Самара", "ROV": "Ростов-на-Дону", "AER": "Сочи",
    "MRV": "Минеральные Воды", "KRR": "Краснодар", "VOG": "Волгоград",
    "SOK": "Саратов", "ULV": "Ульяновск", "CEK": "Челябинск", "TJM": "Тюмень",
    "SVX": "Екатеринбург", "MQF": "Магнитогорск", "NBC": "Нижнекамск",
    "NFG": "Нижневартовск", "SGC": "Сургут", "HMA": "Ханты-Мансийск",
    "BQS": "Благовещенск", "CGO": "Чжэнчжоу", "UUD": "Улан-Удэ",
    "TFU": "Чэнду (Тяньфу)", "HAK": "Хайкоу",
}
# Все функции парсинга (parse_etd, parse_frequency, parse_route, extract_airline_code... и т.д.)
# Оставляем без изменений, они уже были в вашем предыдущем коде.
# ... (здесь вставьте весь ваш существующий код парсинга, который был у вас ранее) ...

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

# --- ТУТ НАЧИНАЕТСЯ НОВЫЙ КОД ДЛЯ БОДРОСТИ ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 1. Запускаем основного бота в фоновом потоке
    bot_thread = threading.Thread(target=main)
    bot_thread.start()

    # 2. Запускаем маленький Flask-сервер для проверки здоровья
    flask_app = Flask(__name__)

    @flask_app.route('/')
    def health_check():
        return "I'm alive!", 200

    # Запускаем Flask-сервер на порту, который ожидает Koyeb
    flask_app.run(host='0.0.0.0', port=8000)

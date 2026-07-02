import swisseph as swe
from datetime import datetime
import requests

swe.set_ephe_path(None)

SIGN_NAMES = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева', 'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']
SIGN_EMOJI = {'Овен':'♈','Телец':'♉','Близнецы':'♊','Рак':'♋','Лев':'♌','Дева':'♍','Весы':'♎','Скорпион':'♏','Стрелец':'♐','Козерог':'♑','Водолей':'♒','Рыбы':'♓'}
ZODIAC_SIGNS = {'Овен': (3,21,4,19), 'Телец': (4,20,5,20), 'Близнецы': (5,21,6,20), 'Рак': (6,21,7,22), 'Лев': (7,23,8,22), 'Дева': (8,23,9,22), 'Весы': (9,23,10,22), 'Скорпион': (10,23,11,21), 'Стрелец': (11,22,12,21), 'Козерог': (12,22,1,19), 'Водолей': (1,20,2,18), 'Рыбы': (2,19,3,20)}
PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY, 'Венера': swe.VENUS, 'Марс': swe.MARS, 'Юпитер': swe.JUPITER, 'Сатурн': swe.SATURN, 'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

def sign_from_lon(lon): return SIGN_NAMES[int(lon // 30)]
def degree_in_sign(lon): return int(lon % 30)
def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return 'Козерог'

def validate_date(day, month, year):
    if year < 1900 or year > datetime.now().year: raise ValueError(f"Год должен быть 1900-{datetime.now().year}")
    if not (1 <= month <= 12): raise ValueError("Месяц должен быть 1-12")
    if not (1 <= day <= 31): raise ValueError("День должен быть 1-31")
    datetime(year, month, day)
    return True

def validate_time(hour, minute):
    if not (0 <= hour <= 23): raise ValueError("Часы 0-23")
    if not (0 <= minute <= 59): raise ValueError("Минуты 0-59")
    return True

def get_current_time():
    try:
        resp = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=5)
        if resp.status_code == 200:
            return datetime.fromisoformat(resp.json()['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
    except: pass
    return datetime.utcnow()

def calc_natal(day, month, year, hour=12, minute=0, lat=55.75, lon=37.62, city_name='москва', house_system=b'P'):
    from cities import CITY_TIMEZONES, get_timezone
    utc_offset = get_timezone(city_name, lat, lon)
    utc_hour = hour - utc_offset
    if utc_hour < 0: utc_hour += 24
    elif utc_hour >= 24: utc_hour -= 24
    jd = swe.julday(year, month, day, utc_hour + minute / 60.0)
    natal = {}
    for name, pid in PLANETS.items():
        try:
            lon_deg = swe.calc_ut(jd, pid)[0][0] if isinstance(swe.calc_ut(jd, pid), tuple) else swe.calc_ut(jd, pid)[0]
            natal[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg}
        except: continue
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        natal['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon, 'retro': True}
        natal['Кету'] = {'sign': sign_from_lon((rahu_lon + 180) % 360), 'degree': degree_in_sign((rahu_lon + 180) % 360), 'lon': (rahu_lon + 180) % 360, 'retro': True}
    except: pass
    if abs(lat) > 66.5: house_system = b'W'
    try: houses, ascmc = swe.houses(jd, lat, lon, house_system)
    except: houses, ascmc = swe.houses(jd, lat, lon, b'W')
    natal['Асцендент'] = {'sign': sign_from_lon(ascmc[0]), 'degree': degree_in_sign(ascmc[0]), 'lon': ascmc[0]}
    natal['MC'] = {'sign': sign_from_lon(ascmc[1]), 'degree': degree_in_sign(ascmc[1]), 'lon': ascmc[1]}
    natal['houses'] = [{'house_num': i+1, 'sign': sign_from_lon(houses[i]), 'degree': degree_in_sign(houses[i]), 'lon': houses[i]} for i in range(12)]
    return natal

def calc_transits():
    now = get_current_time()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    transits = {}
    for name, pid in PLANETS.items():
        try: transits[name] = {'sign': sign_from_lon(swe.calc_ut(jd, pid)[0][0]), 'degree': degree_in_sign(swe.calc_ut(jd, pid)[0][0]), 'lon': swe.calc_ut(jd, pid)[0][0]}
        except: continue
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        transits['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon}
        transits['Кету'] = {'sign': sign_from_lon((rahu_lon + 180) % 360), 'degree': degree_in_sign((rahu_lon + 180) % 360), 'lon': (rahu_lon + 180) % 360}
    except: pass
    return transits

def get_aspects(planets):
    aspects_list = []
    names = [n for n in planets.keys() if n not in ['Асцендент','MC','houses']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            diff = abs(planets[names[i]]['lon'] - planets[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            asp = None
            if diff <= 5: asp = "соединение"
            elif abs(diff-60) <= 5: asp = "секстиль"
            elif abs(diff-90) <= 6: asp = "квадрат"
            elif abs(diff-120) <= 6: asp = "тригон"
            elif abs(diff-180) <= 6: asp = "оппозиция"
            if asp: aspects_list.append(f"{names[i]} {asp} {names[j]}")
    return aspects_list

def get_aspects_with_angles(natal):
    """Возвращает список аспектов для графической карты"""
    aspects = []
    names = [p for p in natal.keys() if p not in ['houses', 'Асцендент', 'MC', 'Десцендент', 'IC']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            diff = abs(natal[names[i]]['lon'] - natal[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            asp = None
            if diff <= 5: asp = 'соединение'
            elif abs(diff-60) <= 5: asp = 'секстиль'
            elif abs(diff-90) <= 6: asp = 'квадрат'
            elif abs(diff-120) <= 6: asp = 'тригон'
            elif abs(diff-180) <= 6: asp = 'оппозиция'
            if asp: aspects.append((names[i], names[j], asp, diff))
    return aspects

def calc_transit_aspects(natal, transits, orb=2.0):
    aspects = []
    aspect_meanings = {'соединение': {'символ': '☌', 'влияние': 'усиление', 'орбис': 8}, 'оппозиция': {'символ': '☍', 'влияние': 'напряжение', 'орбис': 8}, 'тригон': {'символ': '△', 'влияние': 'гармония', 'орбис': 8}, 'квадрат': {'символ': '□', 'влияние': 'вызов', 'орбис': 7}, 'секстиль': {'символ': '⚹', 'влияние': 'шансы', 'орбис': 5}}
    ideal_angles = {'соединение': 0, 'оппозиция': 180, 'тригон': 120, 'квадрат': 90, 'секстиль': 60}
    for t_name, t_data in transits.items():
        if t_name in ['Раху', 'Кету']: continue
        for n_name, n_data in natal.items():
            if n_name in ['houses', 'Асцендент', 'MC', 'Раху', 'Кету']: continue
            diff = abs(t_data['lon'] - n_data['lon']) % 360
            if diff > 180: diff = 360 - diff
            for asp_name, asp_info in aspect_meanings.items():
                deviation = abs(diff - ideal_angles[asp_name])
                if deviation <= asp_info['орбис']:
                    direction = "точный" if deviation < 0.5 else ("сходящийся" if deviation < orb else "расходящийся")
                    aspects.append({'transit_planet': t_name, 'transit_sign': t_data['sign'], 'natal_planet': n_name, 'natal_sign': n_data['sign'], 'aspect': asp_name, 'symbol': asp_info['символ'], 'angle': round(diff, 1), 'deviation': round(deviation, 1), 'direction': direction, 'influence': asp_info['влияние'], 'transit_house': None})
    for asp in aspects:
        t_lon = transits[asp['transit_planet']]['lon']
        for i, h in enumerate(natal['houses']):
            next_h = natal['houses'][(i+1)%12]
            if h['lon'] <= next_h['lon']:
                if h['lon'] <= t_lon < next_h['lon']: asp['transit_house'] = h['house_num']; break
            else:
                if t_lon >= h['lon'] or t_lon < next_h['lon']: asp['transit_house'] = h['house_num']; break
    aspects.sort(key=lambda x: x['deviation'])
    return aspects

def get_moon_hourly_text(natal, now):
    """Почасовой текст движения Луны"""
    moon_hourly = []
    for h in range(24):
        jd_hour = swe.julday(now.year, now.month, now.day, h + now.minute/60.0)
        moon_lon = swe.calc_ut(jd_hour, swe.MOON)[0][0]
        moon_sign_hour = sign_from_lon(moon_lon)
        moon_house_hour = None
        for house in natal['houses']:
            next_house = natal['houses'][(natal['houses'].index(house) + 1) % 12]
            if house['lon'] <= next_house['lon']:
                if house['lon'] <= moon_lon < next_house['lon']: moon_house_hour = house['house_num']; break
            else:
                if moon_lon >= house['lon'] or moon_lon < next_house['lon']: moon_house_hour = house['house_num']; break
        hour_aspects = []
        for n_name, n_data in natal.items():
            if n_name in ['houses', 'Асцендент', 'MC', 'Раху', 'Кету']: continue
            diff = abs(moon_lon - n_data['lon']) % 360
            if diff > 180: diff = 360 - diff
            asp = None
            if diff <= 2: asp = 'соединение'
            elif abs(diff-60) <= 2: asp = 'секстиль'
            elif abs(diff-90) <= 2: asp = 'квадрат'
            elif abs(diff-120) <= 2: asp = 'тригон'
            elif abs(diff-180) <= 2: asp = 'оппозиция'
            if asp: hour_aspects.append(f"{h:02d}:00 — Луна {asp} с {n_name} ({n_data['sign']})")
        moon_hourly.append({'hour': h, 'sign': moon_sign_hour, 'house': moon_house_hour, 'aspects': hour_aspects})
    
    sign_changes = [f"🌙 В {e['hour']:02d}:00 Луна переходит в {e['sign']}" for i, e in enumerate(moon_hourly[1:], 1) if e['sign'] != moon_hourly[i-1]['sign']]
    house_changes = [f"🏠 В {e['hour']:02d}:00 Луна переходит в {e['house']} дом" for i, e in enumerate(moon_hourly[1:], 1) if e['house'] != moon_hourly[i-1]['house']]
    all_aspects = sorted(set(a for e in moon_hourly for a in e['aspects']))
    
    return f"""
*ТОЧНОЕ ДВИЖЕНИЕ ЛУНЫ НА {now.strftime('%d.%m.%Y')}:*
🌙 Луна в {moon_hourly[0]['sign']} ({moon_hourly[0]['house']} дом)
*Смена знака:* {chr(10).join(sign_changes) if sign_changes else 'Весь день в одном знаке'}
*Смена дома:* {chr(10).join(house_changes) if house_changes else 'Весь день в одном доме'}
*Аспекты:* {chr(10).join(all_aspects[:6]) if all_aspects else 'Нет точных аспектов'}
"""

def get_aspects_text(transit_aspects_data):
    if not transit_aspects_data: return "\n*Нет точных аспектов.*\n"
    text = "\n*ТОЧНЫЕ ТРАНЗИТНЫЕ АСПЕКТЫ:*\n"
    for asp in transit_aspects_data[:8]:
        house_info = f" в {asp['transit_house']} доме" if asp['transit_house'] else ""
        text += f"{asp['symbol']} {asp['transit_planet']} {asp['aspect']} с {asp['natal_planet']} — {asp['influence']}{house_info}\n"
    return text

def get_natal_summary(natal, u):
    return f"""📍 {u['city'].title()} | 🕐 {u['hour']:02d}:{u['minute']:02d}
ASC в {natal['Асцендент']['sign']} | ☀ в {natal['Солнце']['sign']} | 🌙 в {natal['Луна']['sign']}
☿ в {natal['Меркурий']['sign']} | ♀ в {natal['Венера']['sign']} | ♂ в {natal['Марс']['sign']}
☊ в {natal['Раху']['sign']} | ☋ в {natal['Кету']['sign']}"""

def parse_city(city_str):
    from cities import CITIES
    city_key = city_str.lower().strip()
    if city_key in CITIES: return CITIES[city_key][0], CITIES[city_key][1], city_key
    return 55.75, 37.62, 'москва'

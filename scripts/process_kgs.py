#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
КГС (Қазақстан Ғарыш Сапары) — космический мониторинг.
Четыре сырых CSV (лес/недра/свалки/самозахваты) → public/data/kgs_facts.json.

Формат вывода — компактный, как у НБД: общий пул строк `S` + числовые ряды.
Имена полей не повторяются в каждой записи (иначе ~23 МБ на 92k объектов).

Ряд: [t, year, region, sub, status, area, lat, lng, aux, extra, vol]
  t      0=forest 1=nedra 2=waste 3=land_seizure
  region/sub/status/aux/extra — индексы в S (или -1)
  area/lat/lng/vol — числа (или null)
Семантика aux/extra по типу: см. ниже в сборке рядов.

ВАЖНО: колонка `date` во всех файлах — это время выгрузки (sdu_load_date ≈ 2026-04-23),
а НЕ дата события. Единственное honest временное измерение — `god` (год).
"""
import csv, sys, os, json, re, collections
from datetime import datetime

csv.field_size_limit(sys.maxsize)  # geojson-поля огромны

BASE = "/Users/alprasalam/Desktop/Вайбкод кейсы/Кейс по экологии/КГС/"
OUT  = os.path.join(os.path.dirname(__file__), "..", "public", "data", "kgs_facts.json")

# ── Нормализация регионов (forest: "Область Абай"; nedra: "город Астана"; waste: "г. Астана") ──
REGION_NORM = {
    'Восточно-Казхастанская область': 'Восточно-Казахстанская область',
    'Область Абай': 'Абайская область',
    'Область Жетысу': 'Жетысуская область',
    'город Астана': 'Астана', 'г. Астана': 'Астана', 'г.Астана': 'Астана',
    'город Алматы': 'Алматы', 'г. Алматы': 'Алматы', 'г.Алматы': 'Алматы',
    'город Шымкент': 'Шымкент', 'г. Шымкент': 'Шымкент', 'г.Шымкент': 'Шымкент',
}
def norm_region(s):
    s = (s or '').strip()
    return REGION_NORM.get(s, s)

# ── Самозахваты: город → область (для карты-хороплета) ──
CITY_TO_REGION = {
    'Шымкент': 'Шымкент', 'Туркестан': 'Туркестанская область', 'Кентау': 'Туркестанская область',
    'Астана': 'Астана', 'Тараз': 'Жамбылская область', 'Петропавловск': 'Северо-Казахстанская область',
    'Алматы': 'Алматы', 'Кызылорда': 'Кызылординская область', 'Усть-Каменогорск': 'Восточно-Казахстанская область',
    'Костанай': 'Костанайская область', 'Семей': 'Абайская область', 'Уральск': 'Западно-Казахстанская область',
    'Талдыкорган': 'Жетысуская область', 'Караганда': 'Карагандинская область', 'Атырау': 'Атырауская область',
    'Актобе': 'Актюбинская область', 'Актау': 'Мангистауская область', 'Кокшетау': 'Акмолинская область',
    'Жезказган': 'Улытауская область', 'Павлодар': 'Павлодарская область',
    'Жанаозен': 'Мангистауская область', 'Конаев': 'Алматинская область', 'Қонаев': 'Алматинская область',
}

# ── Самозахваты: тип нарушения (латиница→кириллица + опечатки) ──
LAT2CYR = str.maketrans('cCaeopxyAEOPXYHBM', 'сСаеорхуАЕОРХУНВМ')
RESULT_NORM = {
    'Объект строителсьтва': 'Объект строительства',
    'Объект стоительства':  'Объект строительства',
}
def norm_result(s):
    s = (s or '').translate(LAT2CYR).strip()
    s = RESULT_NORM.get(s, s)
    if s == 'ЗУ с нарушениями границ':
        s = 'ЗУ с нарушением границ'
    return s

# ── Недра: класс (убрать ведущий пробел, пустое → «Не указан») ──
def norm_nedra_class(s):
    s = (s or '').strip()
    return s if s else 'Не указан'

# ── Свалки: статус (числовой мусор/пустое → «Статус не указан»; варианты «Утилизирован…» → «Утилизирован») ──
def clean_waste_status(s):
    s = (s or '').strip()
    if s.startswith('Утилизирован'):
        return 'Утилизирован'
    if s in ('Не утилизирован', 'Частная территория', 'Отсутствует'):
        return s
    return 'Статус не указан'

def clean_vid(s):
    s = (s or '').strip()
    return s if s else 'Не указан'

# ── DMS → десятичные градусы:  68° 42' 0,174" E → 68.7000483 ──
DMS_RE = re.compile(r'(\d+)\D+(\d+)\D+([\d,\.]+)\D*([NSEWnsew])')
def parse_dms(s):
    if not s:
        return None
    m = DMS_RE.search(s.strip())
    if not m:
        return None
    deg, minutes, seconds, direction = m.groups()
    try:
        val = float(deg) + float(minutes)/60 + float(seconds.replace(',', '.'))/3600
    except ValueError:
        return None
    if direction.upper() in ('S', 'W'):
        val = -val
    return round(val, 6)

def to_int_year(s):
    s = (s or '').strip()
    return int(s) if s.isdigit() else None

def to_float(s):
    s = (s or '').strip()
    if not s or s.lower() == 'nan':
        return None
    try:
        return round(float(s), 4)
    except ValueError:
        return None

# ── Пул строк ──
S = []
_sidx = {}
def sid(s):
    if s is None or s == '':
        return -1
    i = _sidx.get(s)
    if i is None:
        i = len(S); _sidx[s] = i; S.append(s)
    return i

facts = []
meta = {}
val = {}  # validation counters

def reader(fn):
    return csv.DictReader(open(BASE + fn, newline='', encoding='utf-8'))

# ── FOREST (t=0): aux=лесхоз(lu), extra=-1, vol=obem_m3 ──
print("forest…", flush=True)
regs = set(); years = []
illegal = 0
for row in reader("get_forest_detailed.csv"):
    y = to_int_year(row.get('god')); reg = norm_region(row.get('region'))
    leg = (row.get('is_legal') or '').strip()
    if leg == 'Незаконная': illegal += 1
    regs.add(reg); years.append(y)
    facts.append([0, y, sid(reg), sid(leg), -1, to_float(row.get('ploshad')) or 0,
                  None, None, sid((row.get('lu') or '').strip()), -1, to_float(row.get('obem_m3'))])
yy = [y for y in years if y]
meta['forest'] = {'rows': len(years), 'period': f"{min(yy)}-{max(yy)}", 'regions': len(regs),
                  'note': 'Космический мониторинг лесных рубок. Гранулярность — год.'}
val['forest_illegal'] = illegal

# ── NEDRA (t=1): coords из x/y ──
print("nedra…", flush=True)
regs = set(); years = []; new_n = 0
for row in reader("get_nedra_detailed.csv"):
    y = to_int_year(row.get('god')); reg = norm_region(row.get('region'))
    cls = norm_nedra_class(row.get('mining_class'))
    if cls == 'Появившиеся в этом году': new_n += 1
    regs.add(reg); years.append(y)
    facts.append([1, y, sid(reg), sid(cls), -1, to_float(row.get('area')) or 0,
                  parse_dms(row.get('y')), parse_dms(row.get('x')), -1, -1, None])
yy = [y for y in years if y]
meta['nedra'] = {'rows': len(years), 'period': f"{min(yy)}-{max(yy)}", 'regions': len(regs),
                 'note': 'Космический мониторинг карьеров и недропользования. Все регионы.'}
val['nedra_new'] = new_n

# ── WASTE (t=2): aux=район(district), extra=организация ──
print("waste…", flush=True)
regs = set(); years = []; not_util = 0
for row in reader("get_waste_detailed.csv"):
    y = to_int_year(row.get('god')); reg = norm_region(row.get('region'))
    st = clean_waste_status(row.get('statustext'))
    if st == 'Не утилизирован': not_util += 1
    regs.add(reg); years.append(y)
    facts.append([2, y, sid(reg), sid(clean_vid(row.get('vid_othod'))), sid(st),
                  to_float(row.get('area')) or 0, parse_dms(row.get('y')), parse_dms(row.get('x')),
                  sid((row.get('district') or '').strip()), sid((row.get('organization') or '').strip()), None])
yy = [y for y in years if y]
meta['waste'] = {'rows': len(years), 'period': f"{min(yy)}-{max(yy)}", 'regions': len(regs),
                 'note': 'Несанкционированные свалки, выявленные со спутника. Все регионы.'}
val['waste_not_util'] = not_util

# ── LAND SEIZURE (t=3): регион через CITY_TO_REGION; aux=город, extra=объект ──
print("land…", flush=True)
regs = set(); cities = set(); years = []; y2025 = 0; y2024 = 0
for row in reader("get_land_seizure_detailed.csv"):
    y = to_int_year(row.get('god'))
    city = (row.get('city') or '').strip()
    reg = CITY_TO_REGION.get(city, city)
    res = norm_result(row.get('result'))
    if y == 2025: y2025 += 1
    if y == 2024: y2024 += 1
    regs.add(reg); cities.add(city); years.append(y)
    facts.append([3, y, sid(reg), sid(res), -1, None,
                  parse_dms(row.get('y')), parse_dms(row.get('x')),
                  sid(city), sid((row.get('object') or '').strip()), None])
yy = [y for y in years if y]
meta['land_seizure'] = {'rows': len(years), 'period': f"{min(yy)}-{max(yy)}", 'regions': len(regs),
                        'cities': len(cities),
                        'note': 'Самозахваты земель — короткий период наблюдения (2024-2025), привязка к городам.'}
val['land_2025'] = y2025; val['land_2024'] = y2024

out = {
    'cols': ['t', 'year', 'region', 'sub', 'status', 'area', 'lat', 'lng', 'aux', 'extra', 'vol'],
    'types': ['forest', 'nedra', 'waste', 'land_seizure'],
    'S': S,
    'facts': facts,
    'metadata': meta,
    'generated': datetime.now().isoformat(timespec='seconds'),
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

print("\n── ИТОГО ──")
print(f"facts: {len(facts):,} | строк в пуле S: {len(S):,}")
print(f"VALIDATION  forest_illegal={val['forest_illegal']} (ждём 316) | "
      f"nedra_new={val['nedra_new']} (555) | waste_not_util={val['waste_not_util']} (7677) | "
      f"land_2025={val['land_2025']} (3315), land_2024={val['land_2024']}")
print("metadata:", json.dumps(meta, ensure_ascii=False))
print("→", os.path.abspath(OUT))

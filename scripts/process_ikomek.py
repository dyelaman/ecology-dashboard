#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iKomek — per-call компактный датасет для кросс-фильтрации на главной.

Источник: /Users/alprasalam/Desktop/Вайбкод кейсы/Кейс по экологии/выгрузки по ikomek с 2019-04-01/ecology_ikomek.csv
Выход:   public/data/ikomek_compact.json

Структура — копируем паттерн _AC (per-appeal): flat int-массив + словари.
Каждая строка: [ymd, regionIdx, catIdx, charIdx, statusIdx], w=5.

Регионы нормализуются к КОРОТКИМ формам, в которых живёт gReg-селект
(«ВКО», «Астана», «Карагандинская»), чтобы фронт matchил без доп. словарей.
Character сводится к 6 устойчивым группам.
"""
import csv, json, os, sys
from collections import OrderedDict

csv.field_size_limit(sys.maxsize)

SRC = "/Users/alprasalam/Desktop/проекты/Кейс по экологии/выгрузки по ikomek с 2019-04-01/komek_total_data d.csv"
OUT = os.path.join(os.path.dirname(__file__), "..", "public", "data", "ikomek_compact.json")

# ── Регионы → короткие формы (как в #gReg на главной) ──
REGION_NORM = {
    "Восточно-Казахстанская область": "ВКО",
    "Карагандинская область":         "Карагандинская",
    "город Астана":                   "Астана",
    "Область Ұлытау":                 "Улытауская",
    "область Жетісу":                 "Жетысуская",
    "Кызылординская область":         "Кызылординская",
    "Актюбинская область":            "Актюбинская",
    "Область Абай":                   "Абайская",
    "Костанайская область":           "Костанайская",
    "Западно-Казахстанская область":  "ЗКО",
    "Жамбылская область":             "Жамбылская",
    "Северо-Казахстанская область":   "СКО",
    "Туркестанская область":          "Туркестанская",
}
def norm_region(s):
    s = (s or "").strip()
    return REGION_NORM.get(s, s)

# ── Character → 6 устойчивых групп ──
# Матчинг с учётом типовых опечаток источника (БЛАГОУСТРЙСТВО, Благоустройтсво).
_BLAGO_KEYS = ("благоустройств", "благоустрйств", "благоустройтсв", "восстановлени")
def norm_character(s):
    s = (s or "").strip()
    low = s.lower()
    # Эко-экспертиза (проверяем первой — если есть «экспертиз», это точно она)
    if "экспертиз" in low:
        return "Государственная экологическая экспертиза"
    # Эко-контроль
    if "эколог" in low and "контрол" in low:
        return "Экологический контроль"
    # Природные ресурсы / вода / экология (расширенный список)
    if ("природно-сырь" in low
        or low.startswith("экология")
        or "другое(использ" in low
        or "водных отношени" in low
        or "водопользован" in low
        or "водных ресурс" in low):
        return "Природные ресурсы и экология"
    # ЖКХ
    if "жкх" in low:
        return "ЖКХ и благоустройство"
    # Благоустройство (с учётом опечаток)
    if any(k in low for k in _BLAGO_KEYS):
        return "Благоустройство"
    if "прогресс" in low:
        return "Прочее"
    return s or "Прочее"

# ── Словари индексов ──
regions, cats, chars, statuses = OrderedDict(), OrderedDict(), OrderedDict(), OrderedDict()
def idx(d, v):
    i = d.get(v)
    if i is None:
        i = len(d); d[v] = i
    return i

rows = []
# Авто-детект separator: старая выгрузка ',' новая '`'
with open(SRC, encoding="utf-8") as _probe:
    _delim = '`' if '`' in _probe.readline() else ','
with open(SRC, encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter=_delim):
        date = (r.get("created_date") or "")[:10]
        if not date or len(date) != 10:
            continue
        try:
            y, m, d = date.split("-")
            ymd = int(y)*10000 + int(m)*100 + int(d)
        except ValueError:
            continue
        if ymd < 20190101 or ymd > 20271231:
            continue
        region = norm_region(r.get("region"))
        cat    = (r.get("category") or "").strip()
        char   = norm_character(r.get("character"))
        status = (r.get("status") or "").strip()
        rows.append([ymd, idx(regions, region), idx(cats, cat), idx(chars, char), idx(statuses, status)])

# Flat-int массив
W = 5
flat = [v for row in rows for v in row]

out = {
    "w": W,
    "n": len(rows),
    "data": flat,
    "regions":  list(regions.keys()),
    "cats":     list(cats.keys()),
    "chars":    list(chars.keys()),
    "statuses": list(statuses.keys()),
    "meta": {
        "total": len(rows),
        "period_min": "2019-04-01",
        "period_max": "2026-04-19",
        "normalized_regions": True,
        "normalized_chars": True,
        "note": "Per-call iKomek dataset для кросс-фильтрации kpiIkom. Регионы в коротких формах под #gReg.",
    },
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

# ── Валидация: контрольные числа ──
print(f"calls={len(rows):,}  regions={len(regions)}  chars={len(chars)}  cats={len(cats)}  statuses={len(statuses)}")
print(f"→ {os.path.abspath(OUT)}  ({os.path.getsize(OUT)/1024:.1f} KB raw)")

print("\nКонтрольные числа (из CSV):")
years_count = {}
for r in rows:
    yy = r[0]//10000
    years_count[yy] = years_count.get(yy, 0) + 1
for y in sorted(years_count):
    print(f"  год {y}: {years_count[y]:,}")
reg_list = list(regions.keys())
def reg_cnt(name):
    if name not in reg_list:
        return 0
    j = reg_list.index(name)
    return sum(1 for r in rows if r[1] == j)
for nm in ["ВКО", "Карагандинская", "Астана", "Улытауская", "Жетысуская", "Кызылординская", "Актюбинская", "Абайская"]:
    print(f"  {nm}: {reg_cnt(nm):,}")

"""
Агрегация выгрузок НБД СОС (период 2025-01-01 → 2026-12-31):
  - ecology_air_emissions_2025.csv   (4.9 ГБ, 22.3 млн строк)
  - ecology_fire_emissions_2025.csv  (343 МБ,  1.3 млн строк)
  - ecology_water_emissions_2025.csv (243 МБ,    923 К строк)
  - ecology_emission_sources.csv     (справочник)
  - ecology_organizations.csv        (справочник)

Поточное чтение через csv.DictReader, агрегаты в памяти, на выходе один
JSON public/data/nbd_2025.json.

Очистка данных:
  · фильтр тестовой орг «Тест АСМ» и аналогичных служебных записей
  · нормализация опечатки «Восточно-Казхастанская» → «Восточно-Казахстанская»
  · отсечение мусорных дат (вне 2025-01-01…2026-12-31)
  · справочники тоже чистятся от TEST/ТЕСТ записей

Структура nbd_2025.json:
  air/fire/water:
    top_substances:[{name,total,measurements,exceed}]  · top-25
    top_orgs:      [{name,total,measurements,exceed}]  · top-30
    top_regions:   [{name,total,measurements,exceed}]
    monthly:       [{ym,total,measurements,exceed}]
  air.exceed_stats: {total_rows, ratio_filled, exceed_count,
                     pct_of_all, pct_of_measured, ratio_coverage_pct}
  air.exceed: {by_org[], by_region[], by_substance[], monthly[]}
  water.ph:  {n, avg, out_of_range_n, out_of_range_pct, monthly[]}
  metadata:  {air,water,fire: {rows, regions, orgs, period, coverage_note}}
"""
import csv, json, os, sys, time
from collections import defaultdict
from datetime import datetime

SRC = "/Users/alprasalam/Desktop/Вайбкод кейсы/Кейс по экологии/НБД СОС актуальное"
AIR   = f"{SRC}/ecology_air_emissions_2025.csv"
FIRE  = f"{SRC}/ecology_fire_emissions_2025.csv"
WATER = f"{SRC}/ecology_water_emissions_2025.csv"
SRCS  = f"{SRC}/ecology_emission_sources.csv"
ORGS  = f"{SRC}/ecology_organizations.csv"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "data")
OUT_DIR = os.path.normpath(OUT_DIR)
OUT_PATH       = os.path.join(OUT_DIR, "nbd_2025.json")
OUT_FACTS_PATH = os.path.join(OUT_DIR, "nbd_facts.json")

# ── Глобальный аккумулятор фактов для кросс-фильтрации ──────────────────────
# Ключ: (env, month, region, org, substance) → агрегаты.
# Заполняется внутри aggregate() параллельно с обычными агрегатами.
FACTS = defaultdict(lambda: {
    "measurements": 0,
    "ratio_filled": 0,   # air
    "exceed":       0,   # air
    "conc_sum":     0.0, # air
    "conc_count":   0,   # air
    "ph_count":     0,   # water
    "ph_out":       0,   # water
    "gas_sum":      0.0, # fire
    "gas_count":    0,   # fire
})

# ── A4: реальный валидный период данных ─────────────────────────────────────
DATE_MIN = "2025-01-01"
DATE_MAX = "2026-12-31"

# ── A1: фильтрация тестовых организаций ─────────────────────────────────────
# «Тест АСМ» (id=1 в справочнике организаций) даёт ~1.49 млн фейковых строк
# в выгрузке air (≈6.8% всех замеров). Также есть `TEST/ТЕСТ` в источниках.
TEST_ORGS = {
    "тест асм", "тест acm", "тест", "test", "test асм",
}

def is_test_org(org_name):
    if not org_name:
        return False
    clean = org_name.strip().lower().strip('"').strip()
    if clean in TEST_ORGS: return True
    if clean.startswith("тест ") or clean.startswith("test "): return True
    if clean in ("тест", "test"): return True
    return False

# ── A2: нормализация регионов (с case-insensitive ключами) ──────────────────
# Опечатка «Восточно-Казхастанская» (без 'а') разбивает ВКО на два региона.
REGION_NORM = {
    "восточно-казхастанская область":  "Восточно-Казахстанская область",
    "восточно-казхастанская":          "Восточно-Казахстанская область",
    "г. алматы":                       "Алматы",
    "г. астана":                       "Астана",
    "г. шымкент":                      "Шымкент",
}

def normalize_region(s):
    if not s: return s
    clean = s.strip()
    return REGION_NORM.get(clean.lower(), clean)

# ── A4: валидация дат ───────────────────────────────────────────────────────
def is_valid_date(date_str):
    if not date_str or len(date_str) < 10: return False
    dt = date_str[:10]
    return DATE_MIN <= dt <= DATE_MAX

# ── helpers ─────────────────────────────────────────────────────────────────
def f(v):
    if v is None or v == "": return None
    try: return float(v)
    except Exception: return None

def topn(d, n, value_key="total"):
    items = [{"name": k, **v} for k, v in d.items()]
    items.sort(key=lambda x: x.get(value_key, 0) or 0, reverse=True)
    return items[:n]

def monthly_sorted(d):
    return [{"ym": k, **v} for k, v in sorted(d.items())]


def aggregate(csv_path, label, kind):
    """kind: 'air' | 'fire' | 'water'. Поточно читает CSV → агрегаты."""
    by_sub = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    by_org = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    by_reg = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    monthly = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})

    # water — pH stats
    ph_n = 0; ph_sum = 0.0; ph_out_of_range = 0
    ph_monthly = defaultdict(lambda: {"sum": 0.0, "n": 0, "out": 0})

    # air — счётчики для honest exceed_stats (A3)
    air_total_rows = 0
    air_ratio_filled = 0
    air_exceed_count = 0

    # счётчики отфильтрованных
    skipped_date = 0; skipped_test = 0
    regions_set = set(); orgs_set = set()

    t0 = time.time()
    rows_seen = 0
    period_min = "9999-99-99"; period_max = "0000-00-00"

    print(f"  → {label}", flush=True)
    size_mb = os.path.getsize(csv_path) / 1024 / 1024
    print(f"     {size_mb:,.0f} МБ, читаю поточно…", flush=True)

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            rows_seen += 1
            if rows_seen % 500000 == 0:
                el = time.time() - t0
                rate = rows_seen / el if el else 0
                print(f"     [{label}] {rows_seen:>10,} строк · {el:>5.0f}c · {rate:>7,.0f} р/с", flush=True)

            # ── фильтр 1: дата ───────────────────────────────────────────
            dt = (row.get("registered_date") or "")[:10]
            if not is_valid_date(dt):
                skipped_date += 1
                continue

            # ── фильтр 2: тестовая орг ───────────────────────────────────
            org = (row.get("organization_name") or "").strip()
            if is_test_org(org):
                skipped_test += 1
                continue

            # ── после фильтров ───────────────────────────────────────────
            ym = dt[:7]
            if dt < period_min: period_min = dt
            if dt > period_max: period_max = dt

            sub = (row.get("emission_type") or "").strip()
            reg = normalize_region(row.get("region", ""))
            if reg: regions_set.add(reg)
            if org: orgs_set.add(org)

            if kind == "air":
                air_total_rows += 1
                emission = f(row.get("emission"))
                ratio = f(row.get("air_excess_ratio"))
                conc  = f(row.get("pollutant_concentration"))
                val = emission if emission and emission > 0 else 0.0
                is_exceed = 0
                if ratio is not None:
                    air_ratio_filled += 1
                    if ratio > 1.0:
                        is_exceed = 1
                        air_exceed_count += 1
                # FACTS — компактная сборка для кросс-фильтрации
                fk = FACTS[("air", ym, reg or "", org or "", sub or "")]
                fk["measurements"] += 1
                if ratio is not None:
                    fk["ratio_filled"] += 1
                    if ratio > 1.0: fk["exceed"] += 1
                if conc is not None:
                    fk["conc_sum"] += conc; fk["conc_count"] += 1
            elif kind == "fire":
                gas = f(row.get("volumetric_gas_consumption"))
                val = gas or 0.0
                is_exceed = 0
                fk = FACTS[("fire", ym, reg or "", org or "", sub or "")]
                fk["measurements"] += 1
                if gas is not None:
                    fk["gas_sum"] += gas; fk["gas_count"] += 1
            else:  # water
                val = f(row.get("waste_water_flow")) or 0.0
                ph = f(row.get("hydrogen_index"))
                fk = FACTS[("water", ym, reg or "", org or "", sub or "")]
                fk["measurements"] += 1
                if ph is not None and 0 < ph < 14:
                    ph_n += 1; ph_sum += ph
                    out = 1 if (ph < 6 or ph > 9) else 0
                    ph_out_of_range += out
                    m = ph_monthly[ym]
                    m["sum"] += ph; m["n"] += 1; m["out"] += out
                    fk["ph_count"] += 1
                    if ph < 6 or ph > 9: fk["ph_out"] += 1
                is_exceed = 0

            if sub:
                a = by_sub[sub]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            if org:
                a = by_org[org]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            if reg:
                a = by_reg[reg]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            m = monthly[ym]; m["total"] += val; m["measurements"] += 1; m["exceed"] += is_exceed

    el = time.time() - t0
    kept = rows_seen - skipped_date - skipped_test
    print(f"     ✓ {label}: всего CSV {rows_seen:,} · отфильтровано (даты={skipped_date:,}, тест={skipped_test:,}) · оставлено {kept:,}  ({el:,.0f}c)", flush=True)

    # У water в `total` встречаются отрицательные значения (Сточные воды) — для топов
    # надёжнее сортировать по measurements (как и у fire).
    sort_key = "measurements" if kind in ("fire", "water") else "total"
    out = {
        "rows": kept,
        "skipped_date": skipped_date,
        "skipped_test": skipped_test,
        "period_from": period_min if period_min != "9999-99-99" else None,
        "period_to":   period_max if period_max != "0000-00-00" else None,
        "regions_n":   len(regions_set),
        "orgs_n":      len(orgs_set),
        "top_substances": topn(by_sub, 25, sort_key),
        "top_orgs":       topn(by_org, 30, sort_key),
        "top_regions":    sorted(
            [{"name": k, **v} for k, v in by_reg.items()],
            key=lambda x: x["measurements"], reverse=True,
        ),
        "monthly": monthly_sorted(monthly),
    }

    if kind == "air":
        # ── A3: честные exceed_stats ─────────────────────────────────────
        out["exceed_stats"] = {
            "total_rows":         air_total_rows,
            "ratio_filled":       air_ratio_filled,
            "exceed_count":       air_exceed_count,
            "pct_of_all":         round(air_exceed_count / air_total_rows * 100, 2) if air_total_rows else 0,
            "pct_of_measured":    round(air_exceed_count / air_ratio_filled * 100, 2) if air_ratio_filled else 0,
            "ratio_coverage_pct": round(air_ratio_filled / air_total_rows * 100, 2) if air_total_rows else 0,
        }
        # Срезы превышений по орг/региону/веществу/месяцу
        ex_by_sub = sorted(
            [{"name": k, "exceed": v["exceed"], "measurements": v["measurements"]}
             for k, v in by_sub.items() if v["exceed"] > 0],
            key=lambda x: x["exceed"], reverse=True)[:20]
        ex_by_org = sorted(
            [{"name": k, "exceed": v["exceed"], "measurements": v["measurements"]}
             for k, v in by_org.items() if v["exceed"] > 0],
            key=lambda x: x["exceed"], reverse=True)[:25]
        ex_by_reg = sorted(
            [{"name": k, "exceed": v["exceed"], "measurements": v["measurements"]}
             for k, v in by_reg.items() if v["exceed"] > 0],
            key=lambda x: x["exceed"], reverse=True)
        ex_monthly = [{"ym": m["ym"], "exceed": m["exceed"], "measurements": m["measurements"]}
                      for m in out["monthly"]]
        out["exceed"] = {
            "total":        air_exceed_count,
            "measurements": air_total_rows,
            "share_pct":    out["exceed_stats"]["pct_of_all"],  # backwards-compat
            "by_substance": ex_by_sub,
            "by_org":       ex_by_org,
            "by_region":    ex_by_reg,
            "monthly":      ex_monthly,
        }
    if kind == "water":
        avg_ph = (ph_sum / ph_n) if ph_n else None
        out["ph"] = {
            "n": ph_n,
            "avg": round(avg_ph, 3) if avg_ph is not None else None,
            "out_of_range_n":   ph_out_of_range,
            "out_of_range_pct": round(ph_out_of_range / ph_n * 100, 2) if ph_n else 0,
            "monthly": [
                {"ym": k, "avg": round(v["sum"]/v["n"], 3) if v["n"] else None,
                 "n": v["n"], "out": v["out"]}
                for k, v in sorted(ph_monthly.items())
            ],
        }
    return out


def load_lookup(csv_path, fields):
    """Загружает справочник с фильтром тестовых записей (A1)."""
    out = []; skipped = 0
    try:
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                name = row.get("name_ru", "") or row.get("short_name_ru", "")
                if is_test_org(name) or row.get("id") == "1" and is_test_org(name):
                    skipped += 1; continue
                d = {f: row.get(f, "") for f in fields}
                # нормализуем регион в справочнике тоже
                if "region_name" in d:
                    d["region_name"] = normalize_region(d.get("region_name", ""))
                out.append(d)
    except Exception as e:
        print(f"  ⚠ {csv_path}: {e}")
    if skipped:
        print(f"     отфильтровано тестовых записей: {skipped}")
    return out


# ── A5: метаданные о покрытии (дисклеймеры для фронта) ──────────────────────
COVERAGE_NOTES = {
    "air":   "Плановые замеры стационарных источников промпредприятий",
    "water": "Сточные воды крупных промпредприятий — не отражает качество воды по всему Казахстану",
    "fire":  "Факельные выбросы только 2 организаций (NCOC/Кашаган + GAS PROCESSING COMPANY) в Атырауской и Актюбинской областях",
}


def main():
    t0 = time.time()
    print("НБД СОС — агрегация выгрузок (период 2025-01-01 → 2026-12-31)")
    print("Очистка: фильтр Тест АСМ + нормализация регионов + отсечение мусорных дат")
    print("=" * 70)

    print("\n[1/3] AIR (4.9 ГБ)…")
    air = aggregate(AIR, "air", "air")

    print("\n[2/3] FIRE (343 МБ)…")
    fire = aggregate(FIRE, "fire", "fire")

    print("\n[3/3] WATER (243 МБ)…")
    water = aggregate(WATER, "water", "water")

    print("\nСправочники (с фильтром TEST/ТЕСТ)…")
    sources = load_lookup(SRCS,
        ["id", "serial_number", "name_ru", "region_name", "collector_point_name"])
    orgs = load_lookup(ORGS,
        ["id", "name_ru", "short_name_ru", "region_name"])

    # ── A5: metadata ─────────────────────────────────────────────────────
    metadata = {}
    for kind, agg in [("air", air), ("water", water), ("fire", fire)]:
        metadata[kind] = {
            "rows":           agg["rows"],
            "regions":        agg["regions_n"],
            "orgs":           agg["orgs_n"],
            "period":         f"{agg['period_from']} — {agg['period_to']}",
            "coverage_note":  COVERAGE_NOTES[kind],
            "skipped_test":   agg["skipped_test"],
            "skipped_date":   agg["skipped_date"],
        }
    metadata["sources_n"] = len(sources)
    metadata["orgs_n"]    = len(orgs)
    metadata["date_filter"] = f"{DATE_MIN} → {DATE_MAX}"
    metadata["concentration_unit_note"] = "Единицы измерения pollutant_concentration требуют уточнения у источника"

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metadata":     metadata,
        "air":          air,
        "fire":         fire,
        "water":        water,
        "sources":      sources,
        "orgs":         orgs,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    # ── Часть A: компактный массив фактов для кросс-фильтрации фронта ──────
    schema = ["env","month","region","org","substance","measurements",
              "ratio_filled","exceed","conc_sum","conc_count",
              "ph_count","ph_out","gas_sum","gas_count"]
    facts_array = []
    for (env, month, region, org, substance), fk in FACTS.items():
        facts_array.append([
            env, month, region, org, substance,
            fk["measurements"],
            fk["ratio_filled"],
            fk["exceed"],
            round(fk["conc_sum"], 2),
            fk["conc_count"],
            fk["ph_count"],
            fk["ph_out"],
            round(fk["gas_sum"], 4),
            fk["gas_count"],
        ])
    # стабильный порядок: env → period → measurements desc
    facts_array.sort(key=lambda r: (r[0], r[1], -r[5]))
    facts_out = {
        "schema":    schema,
        "facts":     facts_array,
        "metadata":  metadata,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(OUT_FACTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(facts_out, fh, ensure_ascii=False, separators=(",", ":"))
    sz_facts = os.path.getsize(OUT_FACTS_PATH) / 1024

    sz = os.path.getsize(OUT_PATH) / 1024
    el = time.time() - t0
    print("=" * 70)
    print(f"✓ Готово за {el/60:.1f} мин · {OUT_PATH} ({sz:,.0f} КБ)")
    print(f"  nbd_facts.json: {len(facts_array):,} комбинаций · {sz_facts:,.0f} КБ")
    print(f"  AIR   : {air['rows']:>11,} строк · {air['period_from']} → {air['period_to']} · {air['regions_n']} рег. · {air['orgs_n']} орг.")
    print(f"  FIRE  : {fire['rows']:>11,} строк · {fire['period_from']} → {fire['period_to']} · {fire['regions_n']} рег. · {fire['orgs_n']} орг.")
    print(f"  WATER : {water['rows']:>11,} строк · {water['period_from']} → {water['period_to']} · {water['regions_n']} рег. · {water['orgs_n']} орг.")
    es = air["exceed_stats"]
    print(f"\n  Превышения ПДК (воздух):")
    print(f"    {es['exceed_count']:,} превышений")
    print(f"    {es['pct_of_measured']}% от {es['ratio_filled']:,} замеров с заполненным коэф.")
    print(f"    {es['pct_of_all']}% от {es['total_rows']:,} всех замеров")
    print(f"    покрытие коэф. ПДК: {es['ratio_coverage_pct']}%")
    if water.get("ph"):
        p = water["ph"]
        print(f"\n  pH сточных вод:")
        print(f"    avg={p['avg']} · вне 6–9: {p['out_of_range_n']:,} ({p['out_of_range_pct']}% от {p['n']:,})")


if __name__ == "__main__":
    main()

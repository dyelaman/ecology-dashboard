"""
Агрегация свежих выгрузок НБД СОС (2025-09 → 2026-05):
  - ecology_air_emissions_2025.csv   (4.9 ГБ, 22.3 млн строк)
  - ecology_fire_emissions_2025.csv  (343 МБ,  1.3 млн строк)
  - ecology_water_emissions_2025.csv (243 МБ,    923 К строк)
  - ecology_emission_sources.csv     (справочник)
  - ecology_organizations.csv        (справочник)

Поточное чтение через csv.DictReader, агрегаты в памяти, на выходе один
JSON public/data/nbd_2025.json.
Формат разрезов един для air/fire/water:
  top_substances:[{name,total,measurements}]  · top-20
  top_orgs:      [{name,total,measurements}]  · top-30
  top_regions:   [{name,total,measurements}]
  monthly:       [{ym,total,measurements}]
  air-only:
    exceed: {by_org[], by_region[], by_substance[], total, share_pct, monthly[]}
  water-only:
    ph: {avg, n, out_of_range_n, monthly[]}
"""
import csv, json, os, sys, time
from collections import defaultdict

SRC = "/Users/alprasalam/Desktop/daniyal"
AIR   = f"{SRC}/ecology_air_emissions_2025.csv"
FIRE  = f"{SRC}/ecology_fire_emissions_2025.csv"
WATER = f"{SRC}/ecology_water_emissions_2025.csv"
SRCS  = f"{SRC}/ecology_emission_sources.csv"
ORGS  = f"{SRC}/ecology_organizations.csv"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "data")
OUT_DIR = os.path.normpath(OUT_DIR)
OUT_PATH = os.path.join(OUT_DIR, "nbd_2025.json")

# Нормализация регионов — bug в данных: «Восточно-Казхастанская область»
REGION_NORM = {
    "Восточно-Казхастанская область": "Восточно-Казахстанская область",
    "г. Алматы": "Алматы",
    "г. Астана": "Астана",
    "г. Шымкент": "Шымкент",
}

def norm_region(s):
    s = (s or "").strip()
    return REGION_NORM.get(s, s)

def f(v):
    """К float, или None если пусто/нечисло."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None

def topn(d, n, value_key="total"):
    items = [{"name": k, **v} for k, v in d.items()]
    items.sort(key=lambda x: x.get(value_key, 0) or 0, reverse=True)
    return items[:n]

def monthly_sorted(d):
    return [{"ym": k, **v} for k, v in sorted(d.items())]


def aggregate(csv_path, label, kind):
    """kind: 'air' | 'fire' | 'water'.
    Поточно читает CSV и возвращает 5 словарей агрегатов.
    """
    by_sub = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    by_org = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    by_reg = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})
    monthly = defaultdict(lambda: {"total": 0.0, "measurements": 0, "exceed": 0})

    # water: pH stats
    ph_n = 0
    ph_sum = 0.0
    ph_out_of_range = 0
    ph_monthly = defaultdict(lambda: {"sum": 0.0, "n": 0, "out": 0})

    t0 = time.time()
    rows = 0
    period_min = "9999-99-99"
    period_max = "0000-00-00"

    print(f"  → {label}", flush=True)
    size_mb = os.path.getsize(csv_path) / 1024 / 1024
    print(f"     {size_mb:,.0f} МБ, читаю поточно…", flush=True)

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            rows += 1
            if rows % 500000 == 0:
                el = time.time() - t0
                rate = rows / el if el else 0
                print(f"     [{label}] {rows:>10,} строк · {el:>5.0f}c · {rate:>7,.0f} р/с", flush=True)

            dt = (row.get("registered_date") or "")[:10]
            if not dt or len(dt) < 10:
                continue
            # Отсекаем мусорные даты (видели 1970-01-01 и 2127-01-19 в air)
            if dt < "2024-01-01" or dt > "2027-12-31":
                continue
            ym = dt[:7]
            if dt < period_min: period_min = dt
            if dt > period_max: period_max = dt

            sub = (row.get("emission_type") or "").strip()
            org = (row.get("organization_name") or "").strip()
            reg = norm_region(row.get("region"))

            if kind == "air":
                emission = f(row.get("emission"))
                excess = f(row.get("air_excess_ratio"))
                val = emission if emission and emission > 0 else 0.0
                is_exceed = 1 if (excess is not None and excess > 1.0) else 0
            elif kind == "fire":
                val = f(row.get("volumetric_gas_consumption")) or 0.0
                is_exceed = 0
            else:  # water
                val = f(row.get("waste_water_flow")) or 0.0
                ph = f(row.get("hydrogen_index"))
                if ph is not None and 0 < ph < 14:
                    ph_n += 1
                    ph_sum += ph
                    out = 1 if (ph < 6 or ph > 9) else 0
                    ph_out_of_range += out
                    m = ph_monthly[ym]
                    m["sum"] += ph; m["n"] += 1; m["out"] += out
                is_exceed = 0

            if sub:
                a = by_sub[sub]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            if org:
                a = by_org[org]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            if reg:
                a = by_reg[reg]; a["total"] += val; a["measurements"] += 1; a["exceed"] += is_exceed
            m = monthly[ym]; m["total"] += val; m["measurements"] += 1; m["exceed"] += is_exceed

    el = time.time() - t0
    print(f"     ✓ {label}: {rows:,} строк за {el:,.0f}c", flush=True)

    # У water в `total` встречаются отрицательные значения (Сточные воды) — для топов
    # надёжнее сортировать по measurements (как и у fire).
    sort_key = "measurements" if kind in ("fire", "water") else "total"
    out = {
        "rows": rows,
        "period_from": period_min if period_min != "9999-99-99" else None,
        "period_to": period_max if period_max != "0000-00-00" else None,
        "top_substances": topn(by_sub, 25, sort_key),
        "top_orgs":       topn(by_org, 30, sort_key),
        "top_regions":    sorted(
            [{"name": k, **v} for k, v in by_reg.items()],
            key=lambda x: x["measurements"], reverse=True,
        ),
        "monthly": monthly_sorted(monthly),
    }

    if kind == "air":
        # Превышения нормативов — отдельный срез
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
        total_exceed = sum(v["exceed"] for v in by_sub.values())
        total_meas = sum(v["measurements"] for v in by_sub.values())
        out["exceed"] = {
            "total": total_exceed,
            "measurements": total_meas,
            "share_pct": round(total_exceed / total_meas * 100, 2) if total_meas else 0,
            "by_substance": ex_by_sub,
            "by_org": ex_by_org,
            "by_region": ex_by_reg,
            "monthly": ex_monthly,
        }
    if kind == "water":
        avg_ph = (ph_sum / ph_n) if ph_n else None
        out["ph"] = {
            "n": ph_n,
            "avg": round(avg_ph, 3) if avg_ph is not None else None,
            "out_of_range_n": ph_out_of_range,
            "out_of_range_pct": round(ph_out_of_range / ph_n * 100, 2) if ph_n else 0,
            "monthly": [
                {"ym": k, "avg": round(v["sum"]/v["n"], 3) if v["n"] else None,
                 "n": v["n"], "out": v["out"]}
                for k, v in sorted(ph_monthly.items())
            ],
        }
    return out


def load_lookup(csv_path, key_field, fields):
    out = []
    try:
        with open(csv_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                d = {f: row.get(f, "") for f in fields}
                out.append(d)
    except Exception as e:
        print(f"  ⚠ {csv_path}: {e}")
    return out


def main():
    t0 = time.time()
    print("НБД СОС — агрегация выгрузок 2025-09 → 2026-05")
    print("=" * 60)

    print("\n[1/3] AIR (4.9 ГБ, может занять 10-15 мин)…")
    air = aggregate(AIR, "air", "air")

    print("\n[2/3] FIRE (343 МБ)…")
    fire = aggregate(FIRE, "fire", "fire")

    print("\n[3/3] WATER (243 МБ)…")
    water = aggregate(WATER, "water", "water")

    print("\nСправочники…")
    sources = load_lookup(SRCS, "id",
        ["id", "serial_number", "name_ru", "region_name", "collector_point_name"])
    orgs = load_lookup(ORGS, "id",
        ["id", "name_ru", "short_name_ru", "region_name"])

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "air": air,
        "fire": fire,
        "water": water,
        "sources": sources,
        "orgs": orgs,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    sz = os.path.getsize(OUT_PATH) / 1024
    el = time.time() - t0
    print("=" * 60)
    print(f"✓ Готово за {el/60:.1f} мин · {OUT_PATH} ({sz:,.0f} КБ)")
    print(f"  AIR  : {air['rows']:>11,} строк · {air['period_from']} → {air['period_to']}")
    print(f"  FIRE : {fire['rows']:>11,} строк · {fire['period_from']} → {fire['period_to']}")
    print(f"  WATER: {water['rows']:>11,} строк · {water['period_from']} → {water['period_to']}")
    print(f"  Превышения по воздуху: {air['exceed']['total']:,} ({air['exceed']['share_pct']}% от {air['exceed']['measurements']:,} замеров)")
    if water.get("ph"):
        p = water["ph"]
        print(f"  pH: avg={p['avg']} · вне 6–9: {p['out_of_range_n']:,} ({p['out_of_range_pct']}% от {p['n']:,})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_region.py — региональные данные в НАЦИОНАЛЬНОМ формате.

    python3 scripts/build_region.py --region aktobe

Критерий: национальный public/index.html, положенный рядом с regions/<slug>/data/,
показывает регион без единой правки кода. Поэтому имена файлов и структура —
как в public/data/.

Две стратегии по файлу:
  A. Тяжёлые пред-агрегаты (summary.json, preview.json, appeals_compact,
     appeals_raion) — ПЕРЕСОБИРАЮТСЯ национальными билдерами process_data.py
     на отфильтрованном по региону сыром df (гарантия формата + trap #3 сайдкар).
  B. Готовые JSON (ikomek_compact, taza_*, kgs_facts, nbd_facts, pek) —
     ФИЛЬТРУЮТСЯ построчно; словари не переиндексируются (trap #1), производные
     срезы пересобираются из отфильтрованных фактов (trap #2).
  C. Нерегионализируемые (air/emergency/accum — нет region-размерности в
     источнике) — копируются национальными, это помечается в отчёте.

Границы: public/index.html и public/data/ не трогаются.
"""
import argparse, json, os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAT  = os.path.join(ROOT, "public", "data")

def kb(path): return f"{os.path.getsize(path)/1024:,.0f} КБ"
def load(name):
    with open(os.path.join(NAT, name), encoding="utf-8") as f: return json.load(f)
def write(out_dir, name, obj):
    p = os.path.join(out_dir, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    return p

def matches(s, pats):
    if not isinstance(s, str): return False
    low = s.lower()
    return any(p in low for p in pats)

REPORT = []
def rep(name, n, path, note=""):
    REPORT.append((name, n, os.path.getsize(path)/1024, note))


# ── A. Обращения: summary + preview + compact + сайдкар (нац. билдеры) ────────
def build_appeals_chain(cfg, out_dir):
    import process_data as P
    pats = cfg["region_patterns"]
    P.OUT_DIR = out_dir
    P.CHUNKS_DIR = os.path.join(out_dir, "chunks")
    os.makedirs(P.CHUNKS_DIR, exist_ok=True)

    df = P.filter_ecology(P.read_csv(P.APPEALS_CSV, "Обращения"))
    df = df[df["region"].astype(str).apply(lambda s: matches(s, pats))].copy()
    appeals_data = P.process_appeals(df)                       # summary.appeals (регион.)
    preview      = P.make_preview(df, n=500)                    # регион мал → 500 строк хватает
    # Чанки НЕ генерируем: это оптимизация ленивой подгрузки под 343k нац. строк.
    # У региона (7.7k) весь набор уже в appeals_compact; чанки дали бы +18 МБ дублей.
    # Пустой manifest — чтобы loadChunkForFilters не пытался тянуть чанки.
    os.makedirs(P.CHUNKS_DIR, exist_ok=True)
    with open(os.path.join(P.CHUNKS_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"reg": {}, "cat": {}, "type": {}, "year": {}}, f, ensure_ascii=False)
    P.make_appeals_compact(df, appeals_data["top_orgs"])       # appeals_compact + appeals_raion

    dfi = P.read_csv(P.IKOMEK_CSV, "iKomek")
    dfi = dfi[dfi["region"].astype(str).apply(lambda s: matches(s, pats))].copy()
    ikomek_data = P.process_ikomek(dfi)                        # summary.ikomek (регион.)

    # emergency нерегионализируем (в EMERG_CSV нет region) → берём национальную сводку
    try:    emerg = load("summary.json")["emergency"]
    except Exception: emerg = {}

    summary = {"generated": None, "appeals": appeals_data, "ikomek": ikomek_data, "emergency": emerg}
    # generated без Date (детерминизм) — ставим из nat summary
    try: summary["generated"] = load("summary.json").get("generated")
    except Exception: pass
    sp = write(out_dir, "summary.json", summary)
    pp = write(out_dir, "preview.json", preview)
    rep("summary.json",  appeals_data["total"], sp)
    rep("preview.json",  len(preview), pp)
    rep("appeals_compact.json", None, os.path.join(out_dir, "appeals_compact.json"))
    rep("appeals_raion.json",   None, os.path.join(out_dir, "appeals_raion.json"), "✓ выровнен (trap #3)")
    return appeals_data["total"]


# ── B. Компакт-фильтр (словари целиком, фильтруем только data) ────────────────
def filter_compact(js, region_field_idx, pats, extra_dict_keys):
    w, data, regs = js["w"], js["data"], js["regions"]
    ok = {i for i, r in enumerate(regs) if matches(r, pats)}
    rows = [data[i*w:(i+1)*w] for i in range(js["n"]) if data[i*w+region_field_idx] in ok]
    out = dict(js)                       # словари не трогаем (trap #1)
    out["n"] = len(rows)
    out["data"] = [v for r in rows for v in r]
    return out, len(rows)


def build_ikomek(cfg, out_dir):
    js = load("ikomek_compact.json")     # w=5: [ymd,region,cat,char,status]
    out, n = filter_compact(js, 1, cfg["region_patterns"], None)
    p = write(out_dir, "ikomek_compact.json", out); rep("ikomek_compact.json", n, p)
    return n


def build_taza(cfg, out_dir):
    pats = cfg["region_patterns"]
    # taza_compact — w=9, region idx 1
    tc = load("taza_compact.json")
    regs = tc["regions"]; ok = {i for i, r in enumerate(regs) if matches(r, pats)}
    w, data = tc["w"], tc["data"]
    keep_idx = [i for i in range(tc["n"]) if data[i*w+1] in ok]     # индексы строк
    out_tc = dict(tc); out_tc["n"] = len(keep_idx)
    out_tc["data"] = [v for i in keep_idx for v in data[i*w:(i+1)*w]]
    p = write(out_dir, "taza_compact.json", out_tc); rep("taza_compact.json", len(keep_idx), p)

    # taza_table — параллельные массивы, порядок 1:1 с taza_compact → те же keep_idx
    tt = load("taza_table.json")
    out_tt = {"n": len(keep_idx), "fields": tt["fields"]}
    for k in tt["fields"]:
        if k in tt and isinstance(tt[k], list) and len(tt[k]) == tt["n"]:
            out_tt[k] = [tt[k][i] for i in keep_idx]
        elif k in tt:
            out_tt[k] = tt[k]
    p = write(out_dir, "taza_table.json", out_tt); rep("taza_table.json", len(keep_idx), p, "✓ выровнен")

    # taza_kz — сводка/карта. Пересобираем по-минимуму: фильтруем region-срезы если есть.
    tk = load("taza_kz.json")
    out_tk = dict(tk)
    if isinstance(tk.get("by_region"), dict):
        out_tk["by_region"] = {k: v for k, v in tk["by_region"].items() if matches(k, pats)}
    p = write(out_dir, "taza_kz.json", out_tk); rep("taza_kz.json", len(keep_idx), p, "срез by_region")
    return len(keep_idx)


# ── КГС: S целиком, фильтруем facts, пересобираем metadata ────────────────────
def build_kgs(cfg, out_dir):
    pats = cfg["region_patterns"]
    K = load("kgs_facts.json")
    S, facts, types = K["S"], K["facts"], K["types"]
    ix = {c: i for i, c in enumerate(K["cols"])}
    reg_ok = {i for i, s in enumerate(S) if isinstance(s, str) and matches(s, pats)}
    fkeep = [f for f in facts if f[ix["region"]] in reg_ok]
    # metadata пересобираем по типам из отфильтрованных фактов (trap #2)
    meta = {}
    for tname in types:
        tf = [f for f in fkeep if types[f[ix["t"]]] == tname]
        yrs = sorted({f[ix["year"]] for f in tf if f[ix["year"]]})
        regs = {S[f[ix["region"]]] for f in tf if isinstance(f[ix["region"]], int) and f[ix["region"]] >= 0}
        old = (K.get("metadata") or {}).get(tname, {})
        meta[tname] = {"rows": len(tf),
                       "period": f"{yrs[0]}-{yrs[-1]}" if yrs else "",
                       "regions": len(regs), "note": old.get("note", "")}
    out = dict(K); out["facts"] = fkeep; out["metadata"] = meta
    p = write(out_dir, "kgs_facts.json", out); rep("kgs_facts.json", len(fkeep), p, "metadata пересчитан")

    # kgs.json (маленький, {forest,land,nedra,waste}) — фильтруем by-region внутри
    try:
        kj = load("kgs.json"); out_kj = {}
        for t, blk in kj.items():
            if isinstance(blk, dict) and isinstance(blk.get("by_region"), list):
                nb = dict(blk); nb["by_region"] = [r for r in blk["by_region"] if matches(str(r[0] if isinstance(r, list) else r.get("region","")), pats)]
                out_kj[t] = nb
            else: out_kj[t] = blk
        write(out_dir, "kgs.json", out_kj)
    except Exception: shutil.copy(os.path.join(NAT, "kgs.json"), os.path.join(out_dir, "kgs.json"))

    # kgs_map.json — точки, фильтруем по region-полю если есть, иначе по координатам
    try:
        km = load("kgs_map.json"); out_km = {}
        b = cfg["map"]["bounds"] if "map" in cfg else None
        for t, arr in km.items():
            if isinstance(arr, list):
                out_km[t] = [p for p in arr if isinstance(p, dict) and p.get("lat") and p.get("lon")
                             and (not b or (b["latMin"] <= p["lat"] <= b["latMax"] and b["lngMin"] <= p["lon"] <= b["lngMax"]))]
            else: out_km[t] = arr
        write(out_dir, "kgs_map.json", out_km)
    except Exception: shutil.copy(os.path.join(NAT, "kgs_map.json"), os.path.join(out_dir, "kgs_map.json"))
    return len(fkeep)


# ── НБД: фильтруем facts/orgs/sources, пересобираем срезы каждой среды ─────────
def _recompute_env(env_blk, pats):
    from collections import defaultdict
    ef = [r for r in env_blk["facts"] if matches(r.get("region", ""), pats)]
    by_region = defaultdict(lambda: {"measurements": 0, "excess": 0, "orgs": set(), "sources": set()})
    by_org    = defaultdict(lambda: {"region": "", "measurements": 0, "excess": 0, "short": "", "short_kz": ""})
    by_poll   = defaultdict(lambda: {"measurements": 0, "excess": 0})
    by_month  = defaultdict(lambda: {"measurements": 0, "excess": 0})
    for r in ef:
        m = r.get("n_measurements", 0) or 0; x = r.get("n_excess", 0) or 0
        reg, org, src, pol, mon = r.get("region",""), r.get("org",""), r.get("source",""), r.get("pollutant",""), r.get("month","")
        br = by_region[reg]; br["measurements"] += m; br["excess"] += x; br["orgs"].add(org); br["sources"].add(src)
        bo = by_org[org]; bo["region"] = reg; bo["measurements"] += m; bo["excess"] += x
        by_poll[pol]["measurements"] += m; by_poll[pol]["excess"] += x
        bm = by_month[mon]; bm["measurements"] += m; bm["excess"] += x
    out = dict(env_blk)
    out["facts"] = ef
    out["by_region"] = [{"region": k, "measurements": v["measurements"], "excess": v["excess"],
                         "orgs": len(v["orgs"]), "sources": len(v["sources"])}
                        for k, v in sorted(by_region.items(), key=lambda kv: -kv[1]["measurements"])]
    out["by_org"] = [{"name": k, "region": v["region"], "measurements": v["measurements"], "excess": v["excess"],
                      "short": v["short"], "short_kz": v["short_kz"]}
                     for k, v in sorted(by_org.items(), key=lambda kv: -kv[1]["measurements"])]
    out["by_pollutant"] = [{"name": k, "measurements": v["measurements"], "excess": v["excess"]}
                           for k, v in sorted(by_poll.items(), key=lambda kv: -kv[1]["measurements"])]
    out["by_month"] = {k: v for k, v in sorted(by_month.items())}
    key = "top_burners" if "top_burners" in env_blk else "incidents"
    if key in env_blk:
        out[key] = [r for r in env_blk[key] if matches(r.get("region", ""), pats)]
    return out


def build_nbd(cfg, out_dir):
    pats = cfg["region_patterns"]
    N = load("nbd_facts.json")
    ri = N["schema"].index("region")
    out = dict(N)
    out["facts"] = [f for f in N["facts"] if matches(f[ri], pats)]
    out["organizations"] = [o for o in N["organizations"] if matches(o.get("region", ""), pats)]
    out["sources"] = [s for s in N["sources"] if matches(s.get("region", ""), pats)]
    for env in ("air", "water", "fire"):
        if env in N: out[env] = _recompute_env(N[env], pats)
    cov = N.get("coverage", {})
    by_region = {k: v for k, v in cov.get("by_region", {}).items() if matches(k, pats)}
    silent = [s for s in cov.get("silent_orgs_all", []) if matches(s.get("region", ""), pats)]
    out["coverage"] = {"by_region": by_region, "silent_orgs_all": silent}
    p = write(out_dir, "nbd_facts.json", out); rep("nbd_facts.json", len(out["facts"]), p,
        f"{len(out['organizations'])} орг, срезы пересчитаны (trap #2)")

    # nbd_2025 — легаси-сводка, фильтруем by_region-подобные срезы
    try:
        n25 = load("nbd_2025.json"); o25 = dict(n25)
        for k, v in n25.items():
            if isinstance(v, dict) and isinstance(v.get("by_region"), list):
                nv = dict(v); nv["by_region"] = [r for r in v["by_region"]
                    if matches(str((r[0] if isinstance(r, list) else r.get("region","")) or ""), pats)]
                o25[k] = nv
        write(out_dir, "nbd_2025.json", o25)
    except Exception: shutil.copy(os.path.join(NAT, "nbd_2025.json"), os.path.join(out_dir, "nbd_2025.json"))
    return len(out["organizations"])


def build_pek(cfg, out_dir):
    pats = cfg["region_patterns"]
    try:
        P = load("pek_objects.json")
        out = dict(P)
        if isinstance(P.get("objects"), list):
            out["objects"] = [o for o in P["objects"] if matches(str(o.get("region", "") or o.get("region_name", "")), pats)]
            out["total"] = len(out["objects"])
        if isinstance(P.get("clusters"), dict):
            out["clusters"] = {k: v for k, v in P["clusters"].items() if matches(k, pats)}
        p = write(out_dir, "pek_objects.json", out); rep("pek_objects.json", out.get("total", 0), p)
    except Exception as e:
        shutil.copy(os.path.join(NAT, "pek_objects.json"), os.path.join(out_dir, "pek_objects.json"))
        rep("pek_objects.json", None, os.path.join(out_dir, "pek_objects.json"), "копия нац. (fallback)")


# ── Аварийные выбросы: точки с координатами → фильтр по границам региона ──────
def build_emergency(cfg, out_dir):
    b = cfg["map"]["bounds"]
    try:
        E = load("emergency_emissions.json")
        if isinstance(E, list):
            reg = [p for p in E if isinstance(p, dict) and p.get("lat") and p.get("lon")
                   and b["latMin"] <= p["lat"] <= b["latMax"] and b["lngMin"] <= p["lon"] <= b["lngMax"]]
            p = write(out_dir, "emergency_emissions.json", reg)
            rep("emergency_emissions.json", len(reg), p, "фильтр по координатам области")
            return
    except Exception: pass
    shutil.copy(os.path.join(NAT, "emergency_emissions.json"), os.path.join(out_dir, "emergency_emissions.json"))
    rep("emergency_emissions.json", None, os.path.join(out_dir, "emergency_emissions.json"), "нац. (fallback)")


# ── C. Нерегионализируемые (нац. пред-агрегаты без region) — копируем ──────────
NATIONAL_COPY = ["air_emissions.json", "fire_emissions.json",
                 "water_emissions.json", "waste_accumulation.json"]
def copy_national(out_dir):
    for f in NATIONAL_COPY:
        src = os.path.join(NAT, f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out_dir, f))
            rep(f, None, os.path.join(out_dir, f), "нац. (нет region-размерности)")


def build_config(cfg, out_dir):
    dc = {
        "scope": "region", "title": cfg["title"], "subtitle": cfg["subtitle"],
        "geo_level": cfg["geo_level"], "show_region_selector": cfg["show_region_selector"],
        "map_center": cfg["map_center"], "map_zoom": cfg["map_zoom"],
        "region_label": cfg["region_label"], "hidden_tabs": cfg.get("hidden_tabs", []),
    }
    p = write(out_dir, "dashboard_config.json", dc); rep("dashboard_config.json", None, p)


def verify(out_dir):
    A = json.load(open(os.path.join(out_dir, "appeals_compact.json")))
    R = json.load(open(os.path.join(out_dir, "appeals_raion.json")))
    assert R["n"] == A["n"], f"сайдкар рассинхрон: {R['n']} != {A['n']}"
    assert len(R["idx"]) == A["n"], "длина idx != n"
    return A["n"], R["n"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    args = ap.parse_args()
    cfg_path = os.path.join(ROOT, "regions", args.region, "config.json")
    if not os.path.exists(cfg_path): sys.exit(f"✗ нет конфига: {cfg_path}")
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    cfg.setdefault("map", {"bounds": {"latMin": 45, "latMax": 52, "lngMin": 53, "lngMax": 62}})
    out_dir = os.path.join(ROOT, "regions", args.region, "data")
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n═══ Регион: {cfg['title']} ({args.region}) ═══")
    print(f"Матч по подстроке: {cfg['region_patterns']}\n")

    n_app = build_appeals_chain(cfg, out_dir)
    build_ikomek(cfg, out_dir)
    build_taza(cfg, out_dir)
    build_kgs(cfg, out_dir)
    build_nbd(cfg, out_dir)
    build_pek(cfg, out_dir)
    build_emergency(cfg, out_dir)
    copy_national(out_dir)
    build_config(cfg, out_dir)

    vn, rn = verify(out_dir)
    total = sum(sz for _, _, sz, _ in REPORT)
    print(f"\n{'файл':<28}{'записей':>10}   вес")
    print("─" * 60)
    for name, n, sz, note in REPORT:
        ns = f"{n:,}" if isinstance(n, int) else "—"
        print(f"{name:<28}{ns:>10}   {sz:,.0f} КБ   {note}")
    print("─" * 60)
    print(f"{'Итого':<28}{'':<10}   {total/1024:.2f} МБ")
    print(f"\n✓ Сайдкар выровнен: idx={rn:,} == compact n={vn:,}")
    print(f"✓ Регион собран → {out_dir}\n")


if __name__ == "__main__":
    main()

"""
process_nbd_2025.py — v2 (после 2026-06-05).

Раньше скрипт читал raw 4.8 ГБ ecology_air_emissions_2025.csv и агрегировал
в памяти за ~10 минут. Теперь ClickHouse возвращает готовые
month×region×org×source×pollutant агрегаты, что упрощает pipeline до
секунд и расширяет аналитику.

Источники (все в "НБД СОС актуальное/"):
  • mepr_nbdsos_air_emissions_aggr_1.csv    (2.5 МБ, 11 394 строки)
  • mepr_nbdsos_water_emissions_aggr.csv    (152 КБ, 544 строки)
  • mepr_nbdsos_fire_emissions_aggr.csv     (148 КБ, 626 строк)
  • ecology_organizations.csv               (справочник: 83 строки)
  • ecology_emission_sources.csv            (справочник: 243 строки)

Разделитель в агрегатах и справочниках — точка с запятой (;).

Выход:
  • public/data/nbd_facts.json — НОВАЯ расширенная структура v2:
      _meta, organizations[], sources[], air/water/fire (facts+aggregates+incidents),
      coverage (by_region, silent_orgs_all)
  • public/data/nbd_2025.json  — ЛЕГАСИ-формат для существующего UI
      (top_substances, top_orgs, top_regions, monthly per env + metadata).

Очистка:
  • Тестовые орг/источники (имя содержит «тест» или «test»)
  • Нормализация регионов (опечатка «Восточно-Казхастанская», «г. Алматы»→«Алматы» и т.д.)
"""
import csv, json, os, sys
from collections import defaultdict
from datetime import datetime

# ── Пути ──────────────────────────────────────────────────────────────────
SRC = "/Users/alprasalam/Desktop/проекты/Кейс по экологии/НБД СОС актуальное"
AIR_AGGR   = f"{SRC}/mepr_nbdsos_air_emissions dd.csv"
WATER_AGGR = f"{SRC}/mepr_nbdsos_water_emissions dd.csv"
FIRE_AGGR  = f"{SRC}/mepr_nbdsos_fire_emissions d.csv"
ORGS_CSV   = f"{SRC}/ecology_organizations.csv"
SRCS_CSV   = f"{SRC}/ecology_emission_sources.csv"

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "data"))
OUT_FACTS  = os.path.join(OUT_DIR, "nbd_facts.json")
OUT_LEGACY = os.path.join(OUT_DIR, "nbd_2025.json")

# ── Нормализация регионов ─────────────────────────────────────────────────
REGION_NORM = {
    'Восточно-Казхастанская область': 'Восточно-Казахстанская область',
    'г. Алматы':   'Алматы',
    'г. Шымкент':  'Шымкент',
    'г. Астана':   'Астана',
    'г.Алматы':    'Алматы',
    'г.Шымкент':   'Шымкент',
    'г.Астана':    'Астана',
    'Город Алматы':  'Алматы',
    'Город Шымкент': 'Шымкент',
    'Город Астана':  'Астана',
    'город Алматы':  'Алматы',
    'город Шымкент': 'Шымкент',
    'город Астана':  'Астана',
}
def norm_region(s):
    s = (s or '').strip()
    return REGION_NORM.get(s, s)

def is_test_name(name):
    low = (name or '').lower()
    return 'тест' in low or 'test ' in low or low.startswith('test')

# ── Парсеры значений ──────────────────────────────────────────────────────
def parse_float(v):
    if v is None: return None
    s = str(v).strip()
    if not s or s.lower() in ('nan','none'): return None
    try: return float(s)
    except ValueError: return None

def parse_int(v):
    if v is None: return 0
    s = str(v).strip()
    if not s: return 0
    try: return int(float(s))
    except ValueError: return 0

# ── Чтение справочников ───────────────────────────────────────────────────
def read_orgs():
    rows = []
    skipped = 0
    with open(ORGS_CSV, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            name = (r.get('name_ru') or '').strip()
            if not name or is_test_name(name):
                skipped += 1
                continue
            rows.append({
                'id': parse_int(r.get('id')),
                'name': name,
                'name_kz': (r.get('name_kz') or '').strip(),
                'short': (r.get('short_name_ru') or name).strip(),
                'short_kz': (r.get('short_name_kz') or r.get('name_kz') or '').strip(),
                'region': norm_region(r.get('region_name')),
            })
    return rows, skipped

def read_sources():
    rows = []
    skipped = 0
    with open(SRCS_CSV, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            name = (r.get('name_ru') or '').strip()
            if not name or is_test_name(name):
                skipped += 1
                continue
            # short_name отсутствует у источников — обрезаем name до 50 символов
            short = name[:50] + ('…' if len(name) > 50 else '')
            rows.append({
                'id': parse_int(r.get('id')),
                'serial': (r.get('serial_number') or '').strip(),
                'name': name,
                'short': short,
                'collector': (r.get('collector_point_name') or '').strip(),
                'region': norm_region(r.get('region_name')),
            })
    return rows, skipped

# ── Чтение агрегатов ──────────────────────────────────────────────────────
def read_aggregate(path, num_cols):
    """
    num_cols: dict {col_name: 'int' | 'float'}
    Возвращает list of dicts с базовыми полями + кастомными.
    """
    rows = []
    skipped = 0
    # Авто-детект separator: ClickHouse-выгрузки могут быть ';' (июнь) или '`' (июль+)
    with open(path, encoding='utf-8') as f:
        first_line = f.readline()
    delim = '`' if '`' in first_line else ';'
    with open(path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter=delim)
        for r in reader:
            month = (r.get('month') or '').strip()[:7]  # YYYY-MM
            if not month or len(month) != 7:
                skipped += 1
                continue
            region = norm_region(r.get('region'))
            org = (r.get('org') or '').strip()
            source = (r.get('source') or '').strip()
            pollutant = (r.get('pollutant') or '').strip()
            if is_test_name(org) or is_test_name(source):
                skipped += 1
                continue
            base = {
                'month': month,
                'region': region,
                'org': org,
                'source': source,
                'pollutant': pollutant,
                'n_measurements': parse_int(r.get('n_measurements')),
            }
            for col, typ in num_cols.items():
                v = r.get(col)
                base[col] = parse_int(v) if typ == 'int' else parse_float(v)
            rows.append(base)
    return rows, skipped

# ── Главная функция ───────────────────────────────────────────────────────
def main():
    print('═══ NBD СОС v2 (из ClickHouse-агрегатов) ═══')
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. Справочники
    orgs, orgs_skipped = read_orgs()
    sources, srcs_skipped = read_sources()
    print(f'[NBD] Organizations: {len(orgs)} (отфильтровано тестовых: {orgs_skipped})')
    print(f'[NBD] Sources:       {len(sources)} (отфильтровано тестовых: {srcs_skipped})')

    # 2. Агрегаты по 3-м средам
    AIR_COLS = {
        'n_excess': 'int',
        'avg_emissions_g_s': 'float',
        'max_emissions_g_s': 'float',
        'p95_emissions_g_s': 'float',
        'avg_excess_ratio':  'float',
        'max_excess_ratio':  'float',
        'avg_concentration': 'float',
        'max_concentration': 'float',
    }
    WATER_COLS = {
        'n_excess': 'int',
        'avg_ph': 'float', 'min_ph': 'float', 'max_ph': 'float',
        'avg_turbidity': 'float', 'max_turbidity': 'float',
        'avg_conductivity': 'float', 'max_conductivity': 'float',
        'avg_temperature': 'float', 'max_temperature': 'float',
        'avg_flow': 'float', 'max_flow': 'float',
    }
    FIRE_COLS = {
        'n_active': 'int',
        'avg_gas_flow': 'float',
        'max_gas_flow': 'float',
        'sum_gas_flow': 'float',
        'avg_density':  'float',
    }
    air,   air_skipped   = read_aggregate(AIR_AGGR,   AIR_COLS)
    water, water_skipped = read_aggregate(WATER_AGGR, WATER_COLS)
    fire,  fire_skipped  = read_aggregate(FIRE_AGGR,  FIRE_COLS)

    def total_meas(rows): return sum(r['n_measurements'] for r in rows)
    def total_field(rows, fld): return sum(r.get(fld, 0) or 0 for r in rows)

    air_meas = total_meas(air);   air_exc = total_field(air, 'n_excess')
    wat_meas = total_meas(water); wat_exc = total_field(water, 'n_excess')
    fir_meas = total_meas(fire);  fir_act = total_field(fire, 'n_active')
    pct = lambda n,d: f'{(n/d*100 if d else 0):.1f}%'

    print(f'[NBD] AIR aggregate:   {len(air):>5} rows, {air_meas:>12,} measurements, {air_exc:>10,} excess ({pct(air_exc,air_meas)})')
    print(f'[NBD] WATER aggregate: {len(water):>5} rows, {wat_meas:>12,} measurements, {wat_exc:>10,} excess ({pct(wat_exc,wat_meas)})')
    print(f'[NBD] FIRE aggregate:  {len(fire):>5} rows, {fir_meas:>12,} measurements, {fir_act:>10,} active ({pct(fir_act,fir_meas)})')

    # 3. Aggregates per env
    def per_env(rows, exceed_field, top_org_n=30, top_poll_n=25):
        by_region = defaultdict(lambda: {'orgs':set(), 'sources':set(), 'measurements':0, 'excess':0})
        by_org    = defaultdict(lambda: {'region':'', 'measurements':0, 'excess':0})
        by_poll   = defaultdict(lambda: {'measurements':0, 'excess':0})
        by_month  = defaultdict(lambda: {'measurements':0, 'excess':0})
        for r in rows:
            br = by_region[r['region']]
            br['orgs'].add(r['org']); br['sources'].add(r['source'])
            br['measurements'] += r['n_measurements']
            br['excess']       += r.get(exceed_field, 0) or 0
            bo = by_org[r['org']]
            bo['region'] = r['region']
            bo['measurements'] += r['n_measurements']
            bo['excess']       += r.get(exceed_field, 0) or 0
            bp = by_poll[r['pollutant']]
            bp['measurements'] += r['n_measurements']
            bp['excess']       += r.get(exceed_field, 0) or 0
            bm = by_month[r['month']]
            bm['measurements'] += r['n_measurements']
            bm['excess']       += r.get(exceed_field, 0) or 0

        by_region_list = sorted(
            [{'region':k, **{kk:vv for kk,vv in v.items() if kk not in ('orgs','sources')},
              'orgs': len(v['orgs']), 'sources': len(v['sources'])}
             for k,v in by_region.items()],
            key=lambda x: -x['excess']
        )
        by_org_list  = sorted([{'name':k, **v} for k,v in by_org.items()],   key=lambda x: -x['excess'])[:top_org_n]
        by_poll_list = sorted([{'name':k, **v} for k,v in by_poll.items()],  key=lambda x: -x['excess'])[:top_poll_n]
        by_month_d   = {k: v for k,v in sorted(by_month.items())}
        return {'by_region':by_region_list, 'by_org':by_org_list, 'by_pollutant':by_poll_list, 'by_month':by_month_d}

    air_aggs   = per_env(air,   'n_excess')
    water_aggs = per_env(water, 'n_excess')
    fire_aggs  = per_env(fire,  'n_active')

    # 4. Прикрепить short-имена к топ-органам (из справочника)
    org_by_name = {o['name']: o for o in orgs}
    def attach_short(by_org_list):
        for r in by_org_list:
            o = org_by_name.get(r['name'])
            if o:
                r['short'] = o['short']
                r['short_kz'] = o.get('short_kz', '')
            else:
                # Не нашли — берём первые 30 символов как заглушку
                r['short'] = r['name'][:30] + ('…' if len(r['name']) > 30 else '')
                r['short_kz'] = ''
    attach_short(air_aggs['by_org'])
    attach_short(water_aggs['by_org'])
    attach_short(fire_aggs['by_org'])

    # 5. Incidents / top burners
    def incident_row(r):
        return {
            'month': r['month'], 'region': r['region'],
            'org': r['org'], 'org_short': org_by_name.get(r['org'], {}).get('short', r['org'][:30]),
            'source': r['source'], 'pollutant': r['pollutant'],
            'n_measurements': r['n_measurements'],
        }
    air_incidents = sorted(
        [{**incident_row(r),
          'n_excess': r['n_excess'],
          'max_excess_ratio': r.get('max_excess_ratio') or 0,
          'max_concentration': r.get('max_concentration') or 0}
         for r in air if (r.get('n_excess') or 0) > 0 and r.get('max_excess_ratio')],
        key=lambda x: -x['max_excess_ratio']
    )[:100]
    water_incidents = sorted(
        [{**incident_row(r),
          'n_excess': r['n_excess'],
          'max_turbidity': r.get('max_turbidity') or 0,
          'min_ph': r.get('min_ph') or 0,
          'max_ph': r.get('max_ph') or 0}
         for r in water if (r.get('n_excess') or 0) > 0],
        key=lambda x: -x['max_turbidity']
    )[:100]
    fire_top_burners = sorted(
        [{**incident_row(r),
          'n_active': r['n_active'],
          'sum_gas_flow': r.get('sum_gas_flow') or 0,
          'max_gas_flow': r.get('max_gas_flow') or 0}
         for r in fire if r.get('sum_gas_flow')],
        key=lambda x: -x['sum_gas_flow']
    )[:50]

    # 6. Coverage analytics
    # cutoff = 6 месяцев назад от MAX(month) во всех 3 наборах
    all_months = [r['month'] for r in air] + [r['month'] for r in water] + [r['month'] for r in fire]
    max_month = max(all_months) if all_months else '2026-01'
    y, m = int(max_month[:4]), int(max_month[5:7])
    cm = m - 6; cy = y
    while cm <= 0: cm += 12; cy -= 1
    cutoff = f'{cy:04d}-{cm:02d}'

    # Активность по последним месяцам
    recent_orgs = set()
    org_last_month = defaultdict(str)
    src_seen = set()
    for rows_set in (air, water, fire):
        for r in rows_set:
            if r['month'] >= cutoff: recent_orgs.add(r['org'])
            if r['month'] > org_last_month[r['org']]: org_last_month[r['org']] = r['month']
            src_seen.add(r['source'])

    enriched_orgs = []
    for o in orgs:
        enriched_orgs.append({
            **o,
            'active': o['name'] in recent_orgs,
            'last_month': org_last_month.get(o['name']) or None,
        })
    enriched_sources = [{**s, 'active': s['name'] in src_seen} for s in sources]

    silent_orgs_all = sorted(
        [{'name':o['name'], 'short':o['short'], 'region':o['region'],
          'last_seen': org_last_month.get(o['name']) or None}
         for o in orgs if o['name'] not in recent_orgs],
        key=lambda x: (x['last_seen'] or '', x['region'])
    )

    # Coverage by region
    region_orgs    = defaultdict(set)
    region_sources = defaultdict(set)
    for o in orgs:    region_orgs[o['region']].add(o['name'])
    for s in sources: region_sources[s['region']].add(s['name'])
    cov_by_region = {}
    all_regions = set(region_orgs.keys()) | set(region_sources.keys())
    for region in all_regions:
        total_o = region_orgs[region]
        active_o = total_o & recent_orgs
        silent_o = total_o - recent_orgs
        total_s = region_sources[region]
        active_s = total_s & src_seen
        cov_by_region[region] = {
            'orgs_total':    len(total_o),
            'orgs_active':   len(active_o),
            'orgs_silent':   len(silent_o),
            'silent_orgs_names': sorted(list(silent_o))[:10],
            'sources_total':  len(total_s),
            'sources_active': len(active_s),
        }

    # 7. Сборка nbd_facts.json (v2 schema + LEGACY top-level schema/facts для
    #    обратной совместимости с _loadNbdFacts/getFilteredNbdFacts в UI).
    #    Legacy facts — flat per-(env×month×region×org×substance), агрегирует
    #    по всем sources (старый формат не знал про source).
    LEGACY_SCHEMA = ['env','month','region','org','substance','measurements',
                     'ratio_filled','exceed','conc_sum','conc_count',
                     'ph_count','ph_out','gas_sum','gas_count']
    legacy_facts_map = defaultdict(lambda: [0]*9)  # 9 числовых: meas,ratio,exc,csum,ccnt,phcnt,phout,gsum,gcnt
    def push_legacy(env_name, rows, exceed_field):
        for r in rows:
            key = (env_name, r['month'], r['region'], r['org'], r['pollutant'])
            v = legacy_facts_map[key]
            n = r['n_measurements'] or 0
            v[0] += n                                     # measurements
            v[1] += n                                     # ratio_filled (proxy)
            v[2] += r.get(exceed_field, 0) or 0           # exceed
            ac = r.get('avg_concentration')
            if ac is not None:
                v[3] += ac * n                            # conc_sum (восстановлен)
                v[4] += n                                 # conc_count
            ap = r.get('avg_ph')
            if ap is not None:
                v[5] += n                                 # ph_count
            v[6] += r.get('n_excess', 0) or 0             # ph_out (для water)
            gf = r.get('sum_gas_flow') or 0
            if gf:
                v[7] += gf                                # gas_sum
                v[8] += n                                 # gas_count
    push_legacy('air',   air,   'n_excess')
    push_legacy('water', water, 'n_excess')
    push_legacy('fire',  fire,  'n_active')
    legacy_facts = [
        [k[0], k[1], k[2], k[3], k[4], v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8]]
        for k, v in legacy_facts_map.items()
    ]

    facts_out = {
        # ── LEGACY (для существующего UI) ──
        'schema': LEGACY_SCHEMA,
        'facts': legacy_facts,
        'metadata': {
            'air': {'rows': air_meas, 'orgs': len({r['org'] for r in air}),
                    'regions': len({r['region'] for r in air}),
                    'period': f"{min([r['month'] for r in air] or ['']) or '—'} → {max([r['month'] for r in air] or ['']) or '—'}",
                    'coverage_note': 'Плановые замеры стационарных источников промпредприятий'},
            'water':{'rows': wat_meas, 'orgs': len({r['org'] for r in water}),
                    'regions': len({r['region'] for r in water}),
                    'period': f"{min([r['month'] for r in water] or ['']) or '—'} → {max([r['month'] for r in water] or ['']) or '—'}",
                    'coverage_note': 'Сточные воды крупных промпредприятий'},
            'fire': {'rows': fir_meas, 'orgs': len({r['org'] for r in fire}),
                    'regions': len({r['region'] for r in fire}),
                    'period': f"{min([r['month'] for r in fire] or ['']) or '—'} → {max([r['month'] for r in fire] or ['']) or '—'}",
                    'coverage_note': 'Факельные выбросы'},
            'sources_n': len(sources), 'orgs_n': len(orgs),
            'date_filter': '2025-01-01 → 2026-12-31',
        },
        # ── НОВОЕ v2 ──
        '_meta': {
            'generated': datetime.now().isoformat(timespec='seconds'),
            'schema_version': 2,
            'period_air':   {'min': min([r['month'] for r in air] or ['']), 'max': max([r['month'] for r in air] or [''])},
            'period_water': {'min': min([r['month'] for r in water] or ['']), 'max': max([r['month'] for r in water] or [''])},
            'period_fire':  {'min': min([r['month'] for r in fire] or ['']), 'max': max([r['month'] for r in fire] or [''])},
            'coverage_cutoff': cutoff,
            'aggregate_source': 'ClickHouse pre-aggregated (mepr_nbdsos_*_aggr CSV)',
        },
        'organizations': enriched_orgs,
        'sources': enriched_sources,
        'air': {
            'facts':       air,
            'by_region':   air_aggs['by_region'],
            'by_org':      air_aggs['by_org'],
            'by_pollutant':air_aggs['by_pollutant'],
            'by_month':    air_aggs['by_month'],
            'incidents':   air_incidents,
        },
        'water': {
            'facts':       water,
            'by_region':   water_aggs['by_region'],
            'by_org':      water_aggs['by_org'],
            'by_pollutant':water_aggs['by_pollutant'],
            'by_month':    water_aggs['by_month'],
            'incidents':   water_incidents,
        },
        'fire': {
            'facts':       fire,
            'by_region':   fire_aggs['by_region'],
            'by_org':      fire_aggs['by_org'],
            'by_pollutant':fire_aggs['by_pollutant'],
            'by_month':    fire_aggs['by_month'],
            'top_burners': fire_top_burners,
        },
        'coverage': {
            'by_region': cov_by_region,
            'silent_orgs_all': silent_orgs_all,
        }
    }
    with open(OUT_FACTS, 'w', encoding='utf-8') as f:
        json.dump(facts_out, f, ensure_ascii=False, separators=(',', ':'))

    # 8. Легаси nbd_2025.json — формат, совместимый с текущим UI renderNbd2025()
    def env_legacy(env_rows, env_aggs, exceed_field, top_substances_label='top_substances'):
        top_subs = [{'name': r['name'], 'measurements': r['measurements'], 'exceed': r['excess']}
                    for r in env_aggs['by_pollutant']]
        top_orgs = [{'name': r['name'], 'short': r.get('short',''), 'region': r.get('region',''),
                     'measurements': r['measurements'], 'exceed': r['excess']}
                    for r in env_aggs['by_org']]
        top_regs = [{'name': r['region'], 'measurements': r['measurements'], 'exceed': r['excess'],
                     'orgs': r['orgs'], 'sources': r['sources']}
                    for r in env_aggs['by_region']]
        monthly = [{'ym': m, 'measurements': v['measurements'], 'exceed': v['excess']}
                   for m, v in env_aggs['by_month'].items()]
        return {top_substances_label: top_subs, 'top_orgs': top_orgs, 'top_regions': top_regs, 'monthly': monthly}

    legacy = {
        'air':   env_legacy(air,   air_aggs,   'n_excess'),
        'water': env_legacy(water, water_aggs, 'n_excess'),
        'fire':  env_legacy(fire,  fire_aggs,  'n_active'),
        'metadata': {
            'air':   {'rows': air_meas,  'orgs': len({r['org'] for r in air}),   'regions': len({r['region'] for r in air}),
                      'period': f"{facts_out['_meta']['period_air']['min']} → {facts_out['_meta']['period_air']['max']}",
                      'coverage_note': 'Плановые замеры стационарных источников промпредприятий'},
            'water': {'rows': wat_meas,  'orgs': len({r['org'] for r in water}), 'regions': len({r['region'] for r in water}),
                      'period': f"{facts_out['_meta']['period_water']['min']} → {facts_out['_meta']['period_water']['max']}",
                      'coverage_note': 'Сточные воды крупных промпредприятий'},
            'fire':  {'rows': fir_meas,  'orgs': len({r['org'] for r in fire}),  'regions': len({r['region'] for r in fire}),
                      'period': f"{facts_out['_meta']['period_fire']['min']} → {facts_out['_meta']['period_fire']['max']}",
                      'coverage_note': 'Факельные выбросы'},
            'sources_n': len(sources),
            'orgs_n':    len(orgs),
            'date_filter': '2025-01-01 → 2026-12-31',
            'concentration_unit_note': 'Единицы pollutant_concentration уточнить у источника',
        }
    }
    # water.ph — поле которое старый UI читает (опционально, считаем простую агрегацию)
    ph_vals = [r['avg_ph'] for r in water if r.get('avg_ph') is not None]
    if ph_vals:
        out_of_range = sum(1 for v in ph_vals if v < 6.5 or v > 8.5)
        legacy['water']['ph'] = {
            'n': len(ph_vals),
            'avg': round(sum(ph_vals)/len(ph_vals), 3),
            'out_of_range_n': out_of_range,
            'out_of_range_pct': round(out_of_range/len(ph_vals)*100, 1),
        }
    with open(OUT_LEGACY, 'w', encoding='utf-8') as f:
        json.dump(legacy, f, ensure_ascii=False, separators=(',', ':'))

    # 9. Отчёт
    n_active = len(recent_orgs)
    n_silent = len(silent_orgs_all)
    print()
    print(f'[NBD] Active orgs (recent ≥ {cutoff}): {n_active} / {len(orgs)}  ({n_silent} silent)')
    n_active_src = sum(1 for s in enriched_sources if s['active'])
    print(f'[NBD] Active sources: {n_active_src} / {len(sources)}')
    print(f'[NBD] Coverage regions: {len(cov_by_region)}')
    print()
    print(f'[NBD] Written nbd_facts.json: {os.path.getsize(OUT_FACTS)/1024:.1f} KB (schema_v2)')
    print(f'[NBD] Written nbd_2025.json (legacy compat): {os.path.getsize(OUT_LEGACY)/1024:.1f} KB')


if __name__ == '__main__':
    main()

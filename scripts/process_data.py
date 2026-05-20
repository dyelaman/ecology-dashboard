#!/usr/bin/env python3
"""
Обработка данных по экологическим обращениям и iKomek.
Генерирует JSON-файлы для eco-dashboard.

Запуск:
    python3 scripts/process_data.py
"""

import json
import os
import re
import sys
from datetime import datetime

import pandas as pd

# ── ПУТИ ─────────────────────────────────────────────────────────────────────
APPEALS_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по обращениям с 2021-07-01/ecology_eobr_subissues.csv"
IKOMEK_CSV   = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по ikomek с 2019-04-01/ecology_ikomek.csv"
PEK_CSV      = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_pekobject.csv"
EMERG_CSV    = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_emergency_emission.csv"
AIR_MONTHLY_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_air_emission_measurement_data_month_substances.csv"
AIR_DEVICES_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_air_emission_measurement_data_top_devices_sum.csv"
AIR_SUM_CSV      = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_air_emission_measurement_data_SUM_substances.csv"
AIR_EMERG_FL_CSV = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_emergency_emission_air_fact_vs_limit.csv"
AIR_EMERG_M_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_emergency_emission_air_month_fact_limit.csv"
KGS_FOREST_CSV = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/get_forest_detailed.csv"
KGS_LAND_CSV   = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/get_land_seizure_detailed.csv"
KGS_NEDRA_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/get_nedra_detailed.csv"
KGS_WASTE_CSV  = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/get_waste_detailed.csv"
ACCUM_WASTE_CSV= "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/accumulation_waste.csv"
FIRE_CSV       = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/view_fire_emissions_full.csv"
WATER_CSV      = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/view_water_emissions_full.csv"
# Таза Казахстан
TAZA_DIR = "/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по Таза Казахстан"
TAZA_REQUESTS_CSV   = f"{TAZA_DIR}/requests_share_202604281652.csv"
TAZA_REGIONS_CSV    = f"{TAZA_DIR}/region_share_202604281649.csv"
TAZA_CATS_CSV       = f"{TAZA_DIR}/request_category_share_202604281650.csv"
TAZA_COMPLAINTS_CSV = f"{TAZA_DIR}/report_complaint_share_202604281650.csv"
TAZA_SAT_CSV        = f"{TAZA_DIR}/report_satisfaction_share_202604281650.csv"
OUT_DIR     = os.path.join(os.path.dirname(__file__), "..", "public", "data")
CHUNKS_DIR  = os.path.join(OUT_DIR, "chunks")

# ── МАППИНГ СТАТУСОВ ──────────────────────────────────────────────────────────
STATUS_MAP = {
    "Завершено":              "done",
    "Завершено с просрочкой": "latedone",
    "В работе":               "work",
    "В работе с просрочкой":  "late",
}

# Маппинг: CSV регион → ключ дашборда (GeoJSON / REAL_ECO)
REGION_MAP = {
    "Акмолинская область":            "Акмолинская",
    "Актюбинская область":            "Актюбинская",
    "Алматинская область":            "Алматинская обл.",
    "Атырауская область":             "Атырауская",
    "Восточно-Казахстанская область": "ВКО",
    "Жамбылская область":             "Жамбылская",
    "Западно-Казахстанская область":  "ЗКО",
    "Карагандинская область":         "Карагандинская",
    "Костанайская область":           "Костанайская",
    "Кызылординская область":         "Кызылординская",
    "Мангистауская область":          "Мангистауская",
    "Павлодарская область":           "Павлодарская",
    "Северо-Казахстанская область":   "СКО",
    "Туркестанская область":          "Туркестанская",
    "г. Астана":                      "Астана",
    "г.Алматы":                       "Алматы",
    "г.Шымкент":                      "Шымкент",
    "область Абай":                   "Абайская",
    "область Жетісу":                 "Жетысуская",
    "область Ұлытау":                 "Улытауская",
}

# Укороченные названия категорий обращений
CATEGORY_SHORT = {
    "ИСПОЛЬЗОВАНИЕ ПРИРОДНО-СЫРЬЕВЫХ, ЗЕМЕЛЬНЫХ И ВОДНЫХ РЕСУРСОВ, ЭКОЛОГИЯ И УТИЛИЗАЦИЯ": "Экология и природные ресурсы",
    "Использование природно-сырьевых, земельных и водных ресурсов, недропользование, экология и утилизация": "Экология и недропользование",
    "ЧРЕЗВЫЧАЙНЫЕ СИТУАЦИИ": "Чрезвычайные ситуации",
    "ЗДРАВООХРАНЕНИЕ, САНИТАРИЯ И ГИГИЕНА": "Здравоохранение и санитария",
    "ПРОМЫШЛЕННОСТЬ И ЭНЕРГЕТИКА": "Промышленность и энергетика",
    "ЖИЛИЩНО-КОММУНАЛЬНОЕ ХОЗЯЙСТВО": "ЖКХ",
    "Строительство, промышленность, транспорт и коммуникации, жилищно-коммунальное хозяйство, бытовое обслуживание населения": "Строительство и ЖКХ",
    "ЛИЦЕНЗИРОВАНИЕ, РАЗРЕШИТЕЛЬНЫЕ СИСТЕМЫ, ТЕХРЕГУЛИРОВАНИЕ": "Лицензирование и техрегулирование",
}

# Укороченные названия подкатегорий
SUBISSUE_SHORT = {
    "Вопросы охраны водных ресурсов": "Охрана водных ресурсов",
    "Экологический контроль объектов окружающей среды": "Экологический контроль",
    "Лесное и охотничье хозяйство": "Лесное и охотничье хозяйство",
    "Выполнение производителями (импортерами) требований по уплате платы за организацию сбора, транспортировки, переработки, обезвреживания, использования и (или) утилизации отходов": "Утилизация и переработка отходов",
    "Безопасность на водоемах": "Безопасность на водоемах",
    "Адаптация к изменению климата": "Адаптация к изменению климата",
    "Вопросы санитарно-эпидемиологического благополучия населения": "Санитарно-эпидемиологическое благополучие",
    "Экологические проблемы": "Экологические проблемы",
}

# Нормализация поля character из iKomek (слияние дублей)
IKOMEK_CHAR_MAP = {
    "Использование природно-сырьевых ресурсов, экология":         "Экология и природные ресурсы",
    "Использование природно-сырьевых ресурсов и экология":        "Экология и природные ресурсы",
    "ЭКОЛОГИЯ":                                                    "Экология и природные ресурсы",
    "благоустройство дворовой территории":                         "Благоустройство",
    "ЖКХ и благоустройство":                                       "Благоустройство и ЖКХ",
    "Осуществление государственного экологического контроля":      "Экологический контроль",
}

# Порядок месяцев для сортировки
MONTH_ORDER = {
    "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
    "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
    "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12,
}

# ── ECOLOGY WHITELIST ─────────────────────────────────────────────────────────
# Отсекаем нерелевантные категории/подкатегории — оставляем только экологию.
ECOLOGY_FILTER = {
    "fullCategories": [
        "ИСПОЛЬЗОВАНИЕ ПРИРОДНО-СЫРЬЕВЫХ, ЗЕМЕЛЬНЫХ И ВОДНЫХ РЕСУРСОВ, ЭКОЛОГИЯ И УТИЛИЗАЦИЯ",
        "Использование природно-сырьевых, земельных и водных ресурсов, недропользование, экология и утилизация",
    ],
    "filteredCategories": {
        "ЧРЕЗВЫЧАЙНЫЕ СИТУАЦИИ": {
            "issues": [
                "Профилактика, предупреждение и ликвидация ЧС",
                "Чрезвычайные ситуации",
                "Вопросы в сфере промышленной безопасности",
            ],
            "excludeSubissues": ["Безопасность на водоемах"],
        },
        "ЗДРАВООХРАНЕНИЕ, САНИТАРИЯ И ГИГИЕНА": {
            "issues": ["Вопросы санитарного и эпидемиологического контроля"],
        },
        "ПРОМЫШЛЕННОСТЬ И ЭНЕРГЕТИКА": {
            "issues": [
                "Недропользование", "Углеводородное сырье", "Возобновляемые источники энергии",
                "Контроль и надзор в области использования атомной и электроэнергии", "Геология",
                "Отрасли промышленности", "Электроэнергетика",
            ],
            "subissueRules": {
                "Электроэнергетика": ["Деятельность энергопредприятий в сфере электроэнергетики"],
                "Отрасли промышленности": [
                    "Химическая и нефтехимическая промышленность",
                    "Черная металлургия", "Цветная металлургия",
                ],
            },
        },
        "ЖИЛИЩНО-КОММУНАЛЬНОЕ ХОЗЯЙСТВО": {
            "issues": [
                "Тепло-, водо-, газоснабжение, освещение, канализация, лифтовое хозяйство, благоустройство и озеленение",
            ],
        },
        "Строительство, промышленность, транспорт и коммуникации, жилищно-коммунальное хозяйство, бытовое обслуживание населения": {
            "issues": [
                "Промышленность",
                "Тепло-, водо-, газоснабжение, освещение, канализация, лифтовое хозяйство, благоустройство и озеленение, телефонизация и радиофикация",
            ],
        },
        "ЛИЦЕНЗИРОВАНИЕ, РАЗРЕШИТЕЛЬНЫЕ СИСТЕМЫ, ТЕХРЕГУЛИРОВАНИЕ": {
            "issues": ["Разрешительные системы", "Лицензирование"],
        },
        "ОКАЗАНИЕ ГОСУДАРСТВЕННЫХ УСЛУГ, ЛИЦЕНЗИРОВАНИЕ И ТЕХНИЧЕСКОЕ РЕГУЛИРОВАНИЕ": {
            "issues": ["Разрешительные системы", "Лицензирование"],
        },
        "СЕЛЬСКОЕ ХОЗЯЙСТВО": {
            "issues": ["Безопасность в сфере сельского хозяйства"],
        },
        "СЕЛЬСКОЕ ХОЗЯЙСТВО И ЗЕМЕЛЬНЫЕ ОТНОШЕНИЯ": {
            "issues": [
                "Безопасность в сфере сельского хозяйства",
                "Вопросы земли и землепользования",
                "Сельскохозяйственная деятельность",
            ],
        },
        "ВОПРОСЫ ЗЕМЛИ И ЗЕМЛЕПОЛЬЗОВАНИЯ": {
            "issues": ["Соблюдение законодательства в сфере земельных отношений"],
        },
    },
    "excludeCategories": [
        "Раздел до 01.08.2021",
        "В рассмотрении",
        "АДМИНИСТРАТИВНЫЕ ПРАВОНАРУШЕНИЯ, ОБЩЕСТВЕННАЯ И ДОРОЖНАЯ БЕЗОПАСНОСТЬ",
    ],
}


def filter_ecology(df):
    """Возвращает только обращения по экологически релевантным категориям/подкатегориям."""
    cat = df["category"].fillna("").astype(str)
    iss = df["issue"].fillna("").astype(str)
    sub = df["subissue"].fillna("").astype(str)

    mask = pd.Series(False, index=df.index)

    # 1. Категории целиком
    mask |= cat.isin(ECOLOGY_FILTER["fullCategories"])

    # 2. Категории с фильтром по подкатегориям
    for cat_name, rules in ECOLOGY_FILTER["filteredCategories"].items():
        cat_mask = (cat == cat_name)
        if not cat_mask.any():
            continue
        if "issues" in rules:
            cat_mask &= iss.isin(rules["issues"])
        # exclude по issue ИЛИ subissue (трактуем мягко)
        for ex in rules.get("excludeSubissues", []):
            cat_mask &= ~(iss == ex)
            cat_mask &= ~(sub == ex)
        # правила по конкретным issue → допустимым subissue
        for iss_name, allowed_subs in rules.get("subissueRules", {}).items():
            inside = cat_mask & (iss == iss_name)
            if inside.any():
                cat_mask &= ~inside | sub.isin(allowed_subs)
        mask |= cat_mask

    # 3. Явное исключение
    mask &= ~cat.isin(ECOLOGY_FILTER["excludeCategories"])

    out = df[mask].copy()
    print(f"  Экология-фильтр: {len(out):,} из {len(df):,} обращений ({len(out)/len(df)*100:.1f}%)")
    return out

# ── УТИЛИТЫ ───────────────────────────────────────────────────────────────────
def read_csv(path, label):
    print(f"\nЧитаю {label}...")
    for enc in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            print(f"  OK — {len(df):,} строк, кодировка {enc}")
            return df
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            print(f"  ОШИБКА: файл не найден: {path}")
            sys.exit(1)
    print(f"  ОШИБКА: не удалось прочитать {path}")
    sys.exit(1)

def top_n(series, n=8):
    """Возвращает топ-N значений как список [['название', count], ...]"""
    return [[k, int(v)] for k, v in series.dropna().value_counts().head(n).items()]

def is_true_val(series):
    """Подсчёт 'истинных' значений независимо от формата (Y, 1, true, True)"""
    s = series.dropna().astype(str).str.lower()
    return int(s.isin(["y", "1", "true", "да"]).sum())

# ── ОБРАЩЕНИЯ ────────────────────────────────────────────────────────────────
def process_appeals(df):
    print("\nОбработка обращений...")

    # Нормализация региона
    df["_region"] = df["region"].map(REGION_MAP).fillna(df["region"])

    # Нормализация статуса
    df["_status"] = df["current_working_state"].map(STATUS_MAP).fillna("work")

    total = len(df)
    sc = df["_status"].value_counts()
    done    = int(sc.get("done", 0))
    latedone= int(sc.get("latedone", 0))
    work    = int(sc.get("work", 0))
    late    = int(sc.get("late", 0))
    done_pct = round((done + latedone) / total * 100) if total else 0

    # Дубли / перенаправления
    duplicates   = is_true_val(df["is_duplicate"])   if "is_duplicate"   in df.columns else 0
    forwarded    = is_true_val(df["is_forward"])     if "is_forward"     in df.columns else 0
    ext_forwarded= is_true_val(df["is_ext_forward"]) if "is_ext_forward" in df.columns else 0

    print(f"  Итого: {total:,} | Завершено: {done+latedone:,} ({done_pct}%) | В работе: {work:,} | Просрочено: {late:,}")
    print(f"  Дубли: {duplicates:,} | Перенаправлено: {forwarded:,} | Частично: {ext_forwarded:,}")

    # ── МЭПР KPI ───────────────────────────────────────────────────────────
    org_low = df["org_name"].fillna("").astype(str).str.lower()
    mepr_mask = org_low.str.contains("экологии и природных ресурсов", na=False)
    mepr_total = int(mepr_mask.sum())
    central_name = 'государственное учреждение "министерство экологии и природных ресурсов республики казахстан"'
    mepr_central = int((org_low == central_name).sum())
    if "is_forward" in df.columns:
        fwd_series = df["is_forward"].astype(str).str.lower().isin(["y","1","true","да"])
    else:
        fwd_series = pd.Series(False, index=df.index)
    if "is_ext_forward" in df.columns:
        ext_series = df["is_ext_forward"].astype(str).str.lower().isin(["y","1","true","да"])
    else:
        ext_series = pd.Series(False, index=df.index)
    mepr_fwd_in  = int((mepr_mask & fwd_series).sum())
    mepr_fwd_out = int((mepr_mask & ext_series).sum())
    mepr_kpi = {
        "total":         mepr_total,
        "central":       mepr_central,
        "fwd_in":        mepr_fwd_in,
        "fwd_out":       mepr_fwd_out,
        "all_total":     total,
        "all_forwarded": forwarded,
        "all_ext_fwd":   ext_forwarded,
    }
    print(f"  МЭПР: всего {mepr_total:,} ({mepr_total/total*100:.1f}% от всех) · ЦА {mepr_central:,} · перенапр. ВХ {mepr_fwd_in:,} · ИСХ {mepr_fwd_out:,}")

    # ── По регионам ────────────────────────────────────────────────────────
    print("  Регионы...")
    by_region = {}
    for region, grp in df.groupby("_region", sort=False):
        rsc = grp["_status"].value_counts()
        issues = {k: int(v) for k, v in grp["category"].value_counts().head(8).items()}
        by_region[str(region)] = {
            "total":    len(grp),
            "done":     int(rsc.get("done", 0)),
            "latedone": int(rsc.get("latedone", 0)),
            "work":     int(rsc.get("work", 0)),
            "late":     int(rsc.get("late", 0)),
            "dup":      is_true_val(grp["is_duplicate"]) if "is_duplicate" in grp.columns else 0,
            "fwd":      is_true_val(grp["is_forward"])   if "is_forward"   in grp.columns else 0,
            "ext_fwd":  is_true_val(grp["is_ext_forward"]) if "is_ext_forward" in grp.columns else 0,
            "issues":   issues,
        }
    print(f"  Регионов: {len(by_region)}")
    print(f"  Список: {', '.join(sorted(by_region.keys()))}")

    # ── Категории (с нормализацией и слиянием дублей) ──────────────────────
    df["_category"] = df["category"].map(lambda x: CATEGORY_SHORT.get(str(x), str(x)) if pd.notna(x) else x)
    cat_counts = df["_category"].value_counts().head(8)
    categories = [[k, int(v)] for k, v in cat_counts.items()]

    # ── Топ категория среди жалоб ──────────────────────────────────────────
    complaints_df = df[df["appeal_type"] == "Жалоба"]
    top_complaint_category = None
    if len(complaints_df):
        cc = complaints_df["_category"].value_counts()
        top_complaint_category = {
            "name":  str(cc.index[0]),
            "count": int(cc.iloc[0]),
            "total": int(len(complaints_df)),
        }
        print(f"  Топ категория жалоб: {top_complaint_category['name']} "
              f"({top_complaint_category['count']:,} из {top_complaint_category['total']:,})")

    # ── Типы обращений ─────────────────────────────────────────────────────
    appeal_types = top_n(df["appeal_type"], 8)

    # ── Характер вопроса (issue) ───────────────────────────────────────────
    top_issues = top_n(df["issue"], 20)

    # ── Подкатегории (с укорачиванием) ────────────────────────────────────
    df["_subissue"] = df["subissue"].map(lambda x: SUBISSUE_SHORT.get(str(x), str(x)[:55]) if pd.notna(x) else x)
    top_subissues= top_n(df["_subissue"], 8)
    top_orgs     = top_n(df["org_name"],   50)
    all_orgs     = top_n(df["org_name"],   200)  # для фильтра «Орган-исполнитель»

    # ── Иерархия: категория → характер → подкатегория ─────────────────────
    hierarchy = {}
    grp = (df.dropna(subset=["_category","issue","_subissue"])
             .groupby(["_category","issue","_subissue"])
             .size()
             .reset_index(name="cnt"))
    for _, row in grp.sort_values("cnt", ascending=False).iterrows():
        cat  = str(row["_category"])
        iss  = str(row["issue"])
        sub  = str(row["_subissue"])
        cnt  = int(row["cnt"])
        if cnt < 50:
            continue
        hierarchy.setdefault(cat, {}).setdefault(iss, [])
        if sub not in hierarchy[cat][iss]:
            hierarchy[cat][iss].append(sub)

    # ── Cross-tabulation для кросс-фильтрации ─────────────────────────────
    print("  Cross-tab (категории × регионы × статусы)...")
    cross = {}
    for cat, cat_df in df.groupby("_category"):
        cat = str(cat)
        cat_issues = []
        for iss, iss_df in cat_df.groupby("issue"):
            cat_issues.append([
                str(iss), len(iss_df),
                int((iss_df["_status"].isin(["late","latedone"])).sum()),
                is_true_val(iss_df["is_duplicate"]) if "is_duplicate" in iss_df.columns else 0,
            ])
        cat_issues.sort(key=lambda x: -x[1])
        by_reg = {}
        for reg, reg_df in cat_df.groupby("_region"):
            reg_cat_issues = [[str(i), int(v)] for i, v in reg_df["issue"].value_counts().head(10).items() if pd.notna(i)]
            by_reg[str(reg)] = {
                "total":  len(reg_df),
                "done":   int((reg_df["_status"] == "done").sum()),
                "work":   int((reg_df["_status"] == "work").sum()),
                "late":   int((reg_df["_status"].isin(["late","latedone"])).sum()),
                "issues": reg_cat_issues,
            }
        top_cat_orgs = [[str(o), int(c)] for o, c in cat_df["org_name"].value_counts().head(10).items()]
        cross[cat] = {
            "total": len(cat_df),
            "done":  int((cat_df["_status"] == "done").sum()),
            "work":  int((cat_df["_status"] == "work").sum()),
            "late":  int((cat_df["_status"].isin(["late","latedone"])).sum()),
            "dup":   is_true_val(cat_df["is_duplicate"]) if "is_duplicate" in cat_df.columns else 0,
            "fwd":   is_true_val(cat_df["is_forward"]) if "is_forward" in cat_df.columns else 0,
            "issues": cat_issues[:15],
            "by_region": by_reg,
            "top_orgs": top_cat_orgs,
        }

    issue_cross = {}
    df_ci = df.dropna(subset=["_category","issue"])
    for (cat, iss), ci_df in df_ci.groupby(["_category","issue"]):
        if len(ci_df) < 30:
            continue
        subs = []
        for sub, sub_df in ci_df.dropna(subset=["_subissue"]).groupby("_subissue"):
            subs.append([str(sub), len(sub_df),
                         int((sub_df["_status"].isin(["late","latedone"])).sum())])
        subs.sort(key=lambda x: -x[1])
        sub_col_ic = "_subissue" if "_subissue" in ci_df.columns else ("subissue" if "subissue" in ci_df.columns else None)
        by_reg_ic = {}
        for reg_ic, rdf_ic in ci_df.groupby("_region"):
            if len(rdf_ic) < 5: continue
            reg_subs = []
            if sub_col_ic:
                for sub_ic, sdf_ic in rdf_ic.dropna(subset=[sub_col_ic]).groupby(sub_col_ic):
                    reg_subs.append([str(sub_ic), len(sdf_ic)])
                reg_subs.sort(key=lambda x: -x[1])
            by_reg_ic[str(reg_ic)] = {"total": len(rdf_ic), "subs": reg_subs[:10]}
        key = f"{cat}||{iss}"
        issue_cross[key] = {
            "total":     len(ci_df),
            "done":      int((ci_df["_status"] == "done").sum()),
            "work":      int((ci_df["_status"] == "work").sum()),
            "late":      int((ci_df["_status"].isin(["late","latedone"])).sum()),
            "subs":      subs[:15],
            "by_region": by_reg_ic,
        }
    print(f"  Cross: {len(cross)} категорий, {len(issue_cross)} пар категория×характер")

    # ── Кросс по типу обращения ────────────────────────────────────────────
    by_type_cross = {}
    type_col = "appeal_type" if "appeal_type" in df.columns else ("type_name_ru" if "type_name_ru" in df.columns else None)
    if type_col:
        for type_name, type_df in df.groupby(type_col):
            rsc = type_df["_status"].value_counts()
            type_cats = [[str(c), int(v)] for c, v in type_df["_category"].value_counts().head(8).items()]
            type_issues = [[str(i), int(v)] for i, v in type_df["issue"].value_counts().head(15).items() if pd.notna(i)]
            sub_col = "_subissue" if "_subissue" in type_df.columns else ("subissue" if "subissue" in type_df.columns else None)
            type_subs = [[str(s), int(v)] for s, v in type_df[sub_col].value_counts().head(15).items() if pd.notna(s)] if sub_col else []
            type_regs = {}
            for reg, rdf in type_df.groupby("_region"):
                reg_cats  = [[str(c), int(v)] for c, v in rdf["_category"].value_counts().head(8).items()]
                reg_issues= [[str(i), int(v)] for i, v in rdf["issue"].value_counts().head(10).items() if pd.notna(i)]
                reg_subs  = [[str(s), int(v)] for s, v in rdf[sub_col].value_counts().head(10).items() if pd.notna(s)] if sub_col else []
                type_regs[str(reg)] = {
                    "total":      len(rdf),
                    "done":       int((rdf["_status"] == "done").sum()),
                    "late":       int((rdf["_status"].isin(["late","latedone"])).sum()),
                    "categories": reg_cats,
                    "top_issues": reg_issues,
                    "top_subissues": reg_subs,
                }
            # by_cat: вопросы и статусы по каждой категории для данного типа
            type_by_cat = {}
            for cat_name, cat_type_df in type_df.groupby("_category"):
                rsc_cat = cat_type_df["_status"].value_counts()
                cat_issues = [[str(i), int(v)] for i, v in cat_type_df["issue"].value_counts().head(10).items() if pd.notna(i)]
                cat_subs   = [[str(s), int(v)] for s, v in cat_type_df[sub_col].value_counts().head(10).items() if pd.notna(s)] if sub_col else []
                type_by_cat[str(cat_name)] = {
                    "total": len(cat_type_df),
                    "done":  int(rsc_cat.get("done", 0)),
                    "work":  int(rsc_cat.get("work", 0)),
                    "late":  int(rsc_cat.get("late", 0) + rsc_cat.get("latedone", 0)),
                    "issues": cat_issues,
                    "top_subs": cat_subs,
                }
            by_type_cross[str(type_name)] = {
                "total":        len(type_df),
                "done":         int(rsc.get("done", 0)),
                "late":         int(rsc.get("late", 0) + rsc.get("latedone", 0)),
                "categories":   type_cats,
                "top_issues":   type_issues,
                "top_subissues":type_subs,
                "by_region":    type_regs,
                "by_cat":       type_by_cat,
            }
    print(f"  by_type_cross: {len(by_type_cross)} типов")

    # ── Кросс по году (+ тип внутри года) ────────────────────────────────
    by_year_cross = {}
    if "year" in df.columns:
        for year, year_df in df.groupby("year"):
            year_cats = [[str(c), int(v)] for c, v in year_df["_category"].value_counts().head(8).items()]
            year_regs = {}
            for reg, rdf in year_df.groupby("_region"):
                rsc_yr = rdf["_status"].value_counts()
                year_regs[str(reg)] = {
                    "total": len(rdf),
                    "done":  int(rsc_yr.get("done",0) + rsc_yr.get("latedone",0)),
                    "late":  int(rsc_yr.get("late",0) + rsc_yr.get("latedone",0)),
                }
            # Тип × регион × категория × вопрос внутри года
            by_type_y = {}
            for type_, type_df in year_df.groupby("appeal_type"):
                t_rsc = type_df["_status"].value_counts()
                t_cats = [[str(c), int(v)] for c, v in type_df["_category"].value_counts().head(8).items()]
                # Вопросы по категории (без учёта региона — для каскада)
                t_by_cat = {}
                for cat, cat_df in type_df.groupby("_category"):
                    t_by_cat[str(cat)] = [[str(i), int(v)] for i, v in cat_df["issue"].value_counts().head(8).items() if pd.notna(i)]
                # Регион внутри типа×года
                t_by_reg = {}
                for reg, reg_df in type_df.groupby("_region"):
                    r_rsc = reg_df["_status"].value_counts()
                    r_cats = [[str(c), int(v)] for c, v in reg_df["_category"].value_counts().head(8).items()]
                    t_by_reg[str(reg)] = {
                        "total": len(reg_df),
                        "done":  int(r_rsc.get("done",0) + r_rsc.get("latedone",0)),
                        "late":  int(r_rsc.get("late",0) + r_rsc.get("latedone",0)),
                        "categories": r_cats,
                    }
                by_type_y[str(type_)] = {
                    "total":      len(type_df),
                    "done":       int(t_rsc.get("done",0) + t_rsc.get("latedone",0)),
                    "late":       int(t_rsc.get("late",0) + t_rsc.get("latedone",0)),
                    "categories": t_cats,
                    "by_cat":     t_by_cat,
                    "by_region":  t_by_reg,
                }
            y_rsc = year_df["_status"].value_counts()
            year_key = str(year).strip().split()[0]  # '2021 (с 1 июля)' → '2021'
            by_year_cross[year_key] = {
                "total":      len(year_df),
                "done":       int(y_rsc.get("done",0) + y_rsc.get("latedone",0)),
                "late":       int(y_rsc.get("late",0) + y_rsc.get("latedone",0)),
                "categories": year_cats,
                "by_region":  year_regs,
                "by_type":    by_type_y,
            }
    print(f"  by_year_cross: {len(by_year_cross)} лет")

    # ── Кросс по региону (вопросы/подвопросы внутри каждого региона) ──────
    sub_col_main = "_subissue" if "_subissue" in df.columns else ("subissue" if "subissue" in df.columns else None)
    by_region_issues = {}
    for reg, rdf in df.groupby("_region"):
        ri_issues = [[str(i), int(v)] for i, v in rdf["issue"].value_counts().head(10).items() if pd.notna(i)]
        ri_subs   = [[str(s), int(v)] for s, v in rdf[sub_col_main].value_counts().head(10).items() if pd.notna(s)] if sub_col_main else []
        ri_cats   = [[str(c), int(v)] for c, v in rdf["_category"].value_counts().head(8).items()]
        by_region_issues[str(reg)] = {
            "top_issues":    ri_issues,
            "top_subissues": ri_subs,
            "categories":    ri_cats,
        }
    print(f"  by_region_issues: {len(by_region_issues)} регионов")

    # ── Скорость закрытия ─────────────────────────────────────────────────
    closing_speed = {}
    try:
        df_cl = df[df["finish_dt"].notna() & df["start_dt"].notna()].copy()
        df_cl["_start"] = pd.to_datetime(df_cl["start_dt"], errors="coerce")
        df_cl["_fin"]   = pd.to_datetime(df_cl["finish_dt"], errors="coerce")
        df_cl = df_cl.dropna(subset=["_start","_fin"])
        df_cl["days"] = (df_cl["_fin"] - df_cl["_start"]).dt.days
        df_cl = df_cl[(df_cl["days"] >= 0) & (df_cl["days"] <= 365)]
        if len(df_cl) > 100:
            total_cl = len(df_cl)
            global_med = int(df_cl["days"].median())
            on_time_pct = round(len(df_cl[df_cl["days"] <= 30]) / total_cl * 100, 1)
            # Buckets
            bins   = [0, 7, 14, 30, 90, 366]
            blbls  = ["≤7 дн.", "8–14 дн.", "15–30 дн.", "31–90 дн.", ">90 дн."]
            df_cl["_bkt"] = pd.cut(df_cl["days"], bins=bins, labels=blbls, right=True, include_lowest=True)
            bkt_cnt = df_cl["_bkt"].value_counts()
            buckets = [[l, int(bkt_cnt.get(l,0)), round(bkt_cnt.get(l,0)/total_cl*100,1)] for l in blbls]
            # By region
            by_reg_sp = {}
            for reg, rdf in df_cl.groupby("_region"):
                if len(rdf) < 50: continue
                by_reg_sp[str(reg)] = {"n": len(rdf), "median": int(rdf["days"].median())}
            # By year
            by_yr_sp = {}
            if "year" in df_cl.columns:
                for yr, ydf in df_cl.groupby("year"):
                    yk = str(yr).strip().split()[0]
                    by_yr_sp[yk] = {"median": int(ydf["days"].median()), "n": len(ydf)}
            # By type
            by_tp_sp = {}
            if type_col and type_col in df_cl.columns:
                for tp, tdf in df_cl.groupby(type_col):
                    if len(tdf) < 50: continue
                    by_tp_sp[str(tp)] = {"median": int(tdf["days"].median()), "n": len(tdf)}
            closing_speed = {
                "median_days":  global_med,
                "on_time_pct":  on_time_pct,
                "total_closed": total_cl,
                "buckets":      buckets,
                "by_region":    by_reg_sp,
                "by_year":      by_yr_sp,
                "by_type":      by_tp_sp,
            }
            print(f"  Скорость закрытия: медиана {global_med} дн., {len(by_reg_sp)} регионов, {len(by_yr_sp)} лет")
    except Exception as e:
        print(f"  Скорость закрытия — ошибка: {e}")

    # ── Org cross-tab для drill-down ───────────────────────────────────────
    by_org_cross = {}
    try:
        for org, odf in df.groupby("org_name"):
            if len(odf) < 200: continue
            rsc_o = odf["_status"].value_counts()
            by_org_cross[str(org)] = {
                "total": len(odf),
                "done":  int(rsc_o.get("done", 0)),
                "late":  int(rsc_o.get("late", 0) + rsc_o.get("latedone", 0)),
                "top_cats": [[str(c), int(v)] for c, v in odf["_category"].value_counts().head(5).items()],
                "top_regs": [[str(r), int(v)] for r, v in odf["_region"].value_counts().head(5).items()],
            }
        print(f"  by_org_cross: {len(by_org_cross)} организаций")
    except Exception as e:
        print(f"  by_org_cross — ошибка: {e}")

    # ── Месячный тренд (по start_dt) ───────────────────────────────────────
    monthly = []
    _MO_LABELS = ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]
    if "start_dt" in df.columns:
        df["_dt"]  = pd.to_datetime(df["start_dt"], errors="coerce")
        df["_ym"]  = df["_dt"].dt.to_period("M").astype(str)
        trend = (df[df["_ym"] != "NaT"]
                   .groupby("_ym")
                   .agg(
                       total=("_ym",     "count"),
                       done =("_status", lambda x: x.isin(["done","latedone"]).sum()),
                       late =("_status", lambda x: x.isin(["late","latedone"]).sum()),
                   )
                   .reset_index()
                   .sort_values("_ym"))
        for _, row in trend.iterrows():
            ym = str(row["_ym"])          # "2024-03"
            if len(ym) < 7: continue
            yr  = ym[:4]
            mo  = int(ym[5:7])
            monthly.append({
                "ym":    ym,
                "year":  yr,
                "mo":    mo,
                "label": f"{_MO_LABELS[mo-1]} {yr}",
                "total": int(row["total"]),
                "done":  int(row["done"]),
                "late":  int(row["late"]),
            })

    # ── Месячный тренд по регионам ─────────────────────────────────────────
    monthly_by_region = {}
    if "start_dt" in df.columns and "_ym" in df.columns:
        rtrend = (df[df["_ym"] != "NaT"]
                    .groupby(["_region", "_ym"], sort=False)
                    .agg(
                        total=("_ym",     "count"),
                        done =("_status", lambda x: x.isin(["done","latedone"]).sum()),
                        late =("_status", lambda x: x.isin(["late","latedone"]).sum()),
                    )
                    .reset_index()
                    .sort_values(["_region", "_ym"]))
        for _, row in rtrend.iterrows():
            ym = str(row["_ym"])
            if len(ym) < 7: continue
            reg = str(row["_region"])
            mo  = int(ym[5:7])
            monthly_by_region.setdefault(reg, []).append({
                "ym":    ym,
                "year":  ym[:4],
                "mo":    mo,
                "total": int(row["total"]),
                "done":  int(row["done"]),
                "late":  int(row["late"]),
            })
        print(f"  monthly_by_region: {len(monthly_by_region)} регионов")

    return {
        "total":         total,
        "done":          done,
        "latedone":      latedone,
        "work":          work,
        "late":          late,
        "done_pct":      done_pct,
        "duplicates":    duplicates,
        "forwarded":     forwarded,
        "ext_forwarded": ext_forwarded,
        "by_region":     by_region,
        "categories":    categories,
        "appeal_types":  appeal_types,
        "top_issues":    top_issues,
        "top_subissues": top_subissues,
        "top_orgs":      top_orgs,
        "all_orgs":      all_orgs,
        "monthly":          monthly,
        "monthly_by_region": monthly_by_region,
        "top_complaint_category": top_complaint_category,
        "mepr_kpi": mepr_kpi,
        "hierarchy":      hierarchy,
        "cross":          cross,
        "issue_cross":    issue_cross,
        "by_type_cross":    by_type_cross,
        "by_year_cross":    by_year_cross,
        "by_region_issues": by_region_issues,
        "closing_speed":    closing_speed,
        "by_org_cross":     by_org_cross,
    }

# ── iKOMEK ───────────────────────────────────────────────────────────────────
def process_ikomek(df):
    print("\nОбработка iKomek...")
    total = len(df)
    print(f"  Итого: {total:,}")
    print(f"  Колонки: {list(df.columns)}")

    by_category  = top_n(df["category"],  8) if "category"  in df.columns else []

    # Нормализация и слияние character (объединяем схожие категории)
    if "character" in df.columns:
        df["_char"] = df["character"].map(lambda x: IKOMEK_CHAR_MAP.get(str(x), str(x)) if pd.notna(x) else x)
        char_counts = df["_char"].value_counts().head(6)
        by_character = [[k, int(v)] for k, v in char_counts.items()]
    else:
        by_character = []
    by_status    = top_n(df["status"],    8) if "status"    in df.columns else []

    by_region = {}
    if "region" in df.columns:
        for k, v in df["region"].dropna().value_counts().items():
            by_region[str(k)] = int(v)
        print(f"  Регионов в iKomek: {len(by_region)}")

    # Месячный тренд
    monthly = []
    if "year" in df.columns and "month" in df.columns:
        trend = (df.dropna(subset=["year","month"])
                   .groupby(["year","month"], sort=False)
                   .size()
                   .reset_index(name="count"))
        trend = trend.sort_values(["year","month"])
        for _, row in trend.iterrows():
            monthly.append({
                "year":  str(int(row["year"])),
                "month": int(row["month"]),
                "total": int(row["count"]),
            })

    return {
        "total":        total,
        "by_category":  by_category,
        "by_character": by_character,
        "by_status":    by_status,
        "by_region":    by_region,
        "monthly":      monthly,
    }

# ── PREVIEW ТАБЛИЦА ──────────────────────────────────────────────────────────
def make_preview(df, n=2000):
    print(f"\nФормирую preview-таблицу ({n} записей, стратифицированно)...")
    cols = [
        "reg_number", "start_dt", "appeal_type", "applicant_type",
        "category", "issue", "subissue", "region", "raion",
        "org_name", "current_working_state", "status_overdue",
        "deadline", "finish_dt", "is_duplicate", "is_forward", "is_ext_forward",
    ]
    cols = [c for c in cols if c in df.columns]

    # Стратифицированная выборка: гарантируем покрытие всех статусов
    if "_status" in df.columns:
        dfs = []
        per = n // 5
        # Просроченные — самые важные, берём больше
        late_df = df[df["_status"].isin(["late","latedone"])].sort_values("start_dt", ascending=False, na_position="last").head(per * 2)
        if len(late_df): dfs.append(late_df)
        work_df = df[df["_status"] == "work"].sort_values("start_dt", ascending=False, na_position="last").head(per)
        if len(work_df): dfs.append(work_df)
        done_df = df[df["_status"] == "done"].sort_values("start_dt", ascending=False, na_position="last").head(per)
        if len(done_df): dfs.append(done_df)
        used_idx = pd.concat(dfs).index if dfs else pd.Index([])
        rest_df = df[~df.index.isin(used_idx)].sort_values("start_dt", ascending=False, na_position="last")
        taken = sum(len(d) for d in dfs)
        if n - taken > 0: dfs.append(rest_df.head(n - taken))
        combined = pd.concat(dfs).drop_duplicates()
    else:
        combined = df.sort_values("start_dt", ascending=False, na_position="last")

    preview_df = combined[cols].head(n).fillna("").rename(columns={
        "start_dt":              "created_date",
        "appeal_type":           "type_name_ru",
        "category":              "issue_category_name_ru",
        "current_working_state": "current_working_state",
    })
    # Добавляем сокращённые имена для фильтрации
    preview_df = preview_df.copy()
    preview_df["category_short"] = preview_df["issue_category_name_ru"].map(
        lambda x: CATEGORY_SHORT.get(str(x), str(x))
    )
    preview_df["subissue_short"] = preview_df["subissue"].map(
        lambda x: SUBISSUE_SHORT.get(str(x), str(x)[:55]) if str(x) else ""
    )
    preview = preview_df.to_dict(orient="records")
    return preview

# ── ПЭК ОБЪЕКТЫ ──────────────────────────────────────────────────────────────
CAT_LABELS = {1: "1-я категория", 2: "2-я категория", 3: "3-я категория",
              4: "4-я категория", 5: "5-я категория"}

# Центроиды областей по oblast_id (lat, lon)
OBLAST_CENTROIDS = {
    74595662:  ("Мангистауская",  43.65,  52.00),
    74596699:  ("Алматинская",    43.50,  77.50),
    74598322:  ("Алматы",         43.238, 76.945),
    74599856:  ("Атырауская",     47.10,  51.90),
    74600872:  ("Кызылординская", 44.85,  65.50),
    74604294:  ("СКО",            54.87,  69.15),
    74605535:  ("Шымкент",        42.317, 69.596),
    74606000:  ("Карагандинская", 49.80,  73.10),
    74611241:  ("Туркестанская",  42.30,  68.50),
    74611638:  ("Акмолинская",    51.80,  69.00),
    74613637:  ("Костанайская",   52.30,  63.60),
    74617214:  ("ВКО",            49.97,  82.60),
    74617541:  ("Павлодарская",   52.30,  76.90),
    74617841:  ("Жамбылская",     43.35,  71.40),
    74619818:  ("ЗКО",            51.20,  51.37),
    74619912:  ("Актюбинская",    48.80,  57.20),
    132450570: ("Абайская",       49.50,  81.50),
    132451555: ("Жетысуская",     44.00,  79.50),
    132451997: ("Улытауская",     48.00,  67.00),
    132458420: ("Астана",         51.18,  71.45),
}

def parse_coords(val):
    """Возвращает (lat, lon) или None. Отбрасывает дефолтные целочисленные."""
    try:
        parsed = json.loads(val)
        c = parsed[0].get("coords", [])
        if not c:
            return None
        pt = c[0]
        lat, lon = float(pt[0]), float(pt[1])
        # Отбрасываем целые координаты (дефолт [51,71] и подобные)
        if lat == int(lat) and lon == int(lon):
            return None
        # Проверяем что в пределах Казахстана
        if not (40.0 <= lat <= 56.0 and 49.0 <= lon <= 88.0):
            return None
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None

def process_pek(df):
    print("\nОбработка ПЭК объектов...")

    # Только активные (не удалённые, не inactive)
    active = df[~df["is_deleted"].eq(True) & ~df["inactive"].eq(True)].copy()
    print(f"  Всего: {len(df):,}  →  Активных: {len(active):,}")

    # Истинное число по категориям (все активные)
    by_cat_all = {}
    for _, r in active.iterrows():
        cat_id = int(r["dic_category_id"]) if pd.notna(r.get("dic_category_id")) else None
        k = str(cat_id) if cat_id else "null"
        by_cat_all[k] = by_cat_all.get(k, 0) + 1

    objects = []
    no_gps_rows = []

    for _, r in active.iterrows():
        coords = parse_coords(r["coords"]) if pd.notna(r.get("coords")) else None
        cat_id   = int(r["dic_category_id"]) if pd.notna(r.get("dic_category_id")) else None
        name     = str(r["name_object"]).strip() if pd.notna(r.get("name_object")) else ""
        address  = str(r["address"]).strip()     if pd.notna(r.get("address"))     else ""
        region_raw = address.split(",")[0].strip().title() if address else ""

        if coords is None:
            no_gps_rows.append({"cat": cat_id, "oblast_id": r.get("oblast_id")})
            continue

        lat, lon = coords
        objects.append({
            "id":      int(r["id"]),
            "name":    name,
            "lat":     lat,
            "lon":     lon,
            "cat":     cat_id,
            "cat_lbl": CAT_LABELS.get(cat_id, "Неизвестно"),
            "address": address[:120],
            "region":  region_raw,
        })

    objects.sort(key=lambda x: x["cat"] or 9)

    # Кластеры по регионам для объектов без GPS
    cluster_map = {}
    for row in no_gps_rows:
        oid = row["oblast_id"]
        if pd.isna(oid):
            continue
        oid = int(oid)
        if oid not in OBLAST_CENTROIDS:
            continue
        reg_name, lat, lon = OBLAST_CENTROIDS[oid]
        if reg_name not in cluster_map:
            cluster_map[reg_name] = {"region": reg_name, "lat": lat, "lon": lon, "count": 0, "by_cat": {}}
        cluster_map[reg_name]["count"] += 1
        k = str(row["cat"]) if row["cat"] else "null"
        cluster_map[reg_name]["by_cat"][k] = cluster_map[reg_name]["by_cat"].get(k, 0) + 1

    clusters = sorted(cluster_map.values(), key=lambda x: -x["count"])

    by_cat_gps = {}
    for o in objects:
        k = str(o["cat"])
        by_cat_gps[k] = by_cat_gps.get(k, 0) + 1

    print(f"  С точными координатами: {len(objects):,}")
    print(f"  Без координат (кластеры по регионам): {len(no_gps_rows):,} → {len(clusters)} регионов")
    print(f"  Все активные по категориям: { {CAT_LABELS.get(int(k),'?'): v for k,v in by_cat_all.items() if k!='null'} }")

    return {
        "objects":  objects,
        "clusters": clusters,
        "total":    len(active),
        "by_cat":   by_cat_all,
    }

# ── АВАРИЙНЫЕ ВЫБРОСЫ ────────────────────────────────────────────────────────
def process_emergency(df):
    print("\nОбработка аварийных выбросов...")
    df = df.copy()
    df["CreateDate"] = pd.to_datetime(df["CreateDate"], errors="coerce")

    # Один ReportId = один аварийный инцидент
    reports = df.groupby("ReportId").agg(
        date=("CreateDate", "min"),
        is_closed=("IsClosed", lambda x: bool(x.any())),
        lat=("Lat", "first"),
        lng=("Lng", "first"),
        pollutants=("NameRu", lambda x: list(x.dropna().unique()[:5])),
        actual_vol=("ActualVolume", "sum"),
        limit_vol=("LimitedVolume", "sum"),
        point=("PointName", "first"),
    ).reset_index()

    total = len(reports)
    closed = int(reports["is_closed"].sum())
    print(f"  Инцидентов: {total:,}  |  Закрыто: {closed:,}")

    # Годовой разбив
    reports["year"] = reports["date"].dt.year.fillna(0).astype(int)
    by_year = {str(yr): int(cnt) for yr, cnt in reports["year"].value_counts().sort_index().items() if yr > 0}
    print(f"  По годам: {by_year}")

    # Месячный тренд (период ключ YYYY-MM)
    reports["ym"] = reports["date"].dt.to_period("M").astype(str)
    monthly = [
        {"ym": ym, "total": int(cnt)}
        for ym, cnt in reports.groupby("ym").size().sort_index().items()
    ]

    # Сравнение Jan-Apr текущего и предыдущего года
    cur_year = reports["date"].dt.year.max()
    prev_year = cur_year - 1
    cur_ytd  = int(reports[(reports["year"] == cur_year)  & (reports["date"].dt.month <= 4)].shape[0])
    prev_ytd = int(reports[(reports["year"] == prev_year) & (reports["date"].dt.month <= 4)].shape[0])
    delta_ytd = cur_ytd - prev_ytd
    print(f"  {cur_year} Jan-Apr: {cur_ytd}  vs  {prev_year} Jan-Apr: {prev_ytd}  (Δ {delta_ytd:+d})")

    # Карточки для карты — только с реальными координатами
    map_objects = []
    for _, r in reports.iterrows():
        try:
            lat, lng = float(r["lat"]), float(r["lng"])
        except (TypeError, ValueError):
            continue
        if not (40.0 <= lat <= 56.0 and 49.0 <= lng <= 88.0):
            continue
        # Отбрасываем целые заглушки
        if lat == int(lat) and lng == int(lng):
            continue
        map_objects.append({
            "id":        int(r["ReportId"]),
            "lat":       round(lat, 6),
            "lon":       round(lng, 6),
            "date":      r["date"].strftime("%Y-%m-%d") if pd.notna(r["date"]) else "",
            "closed":    r["is_closed"],
            "pollutants": r["pollutants"],
            "actual":    round(float(r["actual_vol"]), 2) if pd.notna(r["actual_vol"]) else 0,
            "limit":     round(float(r["limit_vol"]),  2) if pd.notna(r["limit_vol"])  else 0,
            "point":     str(r["point"]).strip() if pd.notna(r["point"]) else "",
        })

    print(f"  С координатами для карты: {len(map_objects):,}")

    return {
        "summary": {
            "total":      total,
            "closed":     closed,
            "by_year":    by_year,
            "monthly":    monthly,
            "cur_year":   int(cur_year),
            "cur_ytd":    cur_ytd,
            "prev_ytd":   prev_ytd,
            "delta_ytd":  delta_ytd,
        },
        "map": map_objects,
    }


# ── ВЫБРОСЫ В ВОЗДУХ ─────────────────────────────────────────────────────────
SUBSTANCE_SHORT = {
    "Углерод оксид": "CO",
    "Диоксид азота": "NO₂",
    "Сера диоксид": "SO₂",
    "Оксид азота": "NO",
    "Пыль": "Пыль",
    "Пыль (взвешенные частицы)": "Пыль (PM)",
    "Серная кислота": "H₂SO₄",
    "Cумма оксидов азота": "NOₓ",
    "Сероводород": "H₂S",
    "Фтористый водород": "HF",
    "Аммиак": "NH₃",
    "Метан": "CH₄",
    "Сажа": "Сажа",
    "Пыль SiO2 20%": "Пыль SiO₂ 20%",
    "Пыль SiO2 70-20%": "Пыль SiO₂ 70-20%",
    "Этилбензол (675)": "Этилбензол",
}

POLLUTANT_SHORT = {
    "Смесь углеводородов предельных С1-С5":  "УВ С1-С5",
    "Смесь углеводородов предельных С6-С10": "УВ С6-С10",
    "Смесь углеводородов предельных C6-C10": "УВ С6-С10",
    "Смесь углеводородов предельных C1-C5":  "УВ С1-С5",
    "Углерод оксид (Окись углерода, Угарный газ)": "CO",
    "Оксид углерода (СО)": "CO",
    "Азота (IV) диоксид (Азота диоксид)": "NO₂",
    "Сера диоксид (Ангидрид сернистый, Сернистый газ, Сера (IV) оксид)": "SO₂",
    "Азот (II) оксид (Азота оксид)": "NO",
    "Сероводород (Дигидросульфид)": "H₂S",
    "Углерод (Сажа, Углерод черный)": "Сажа",
    "Метан": "CH₄",
    "Бензол": "Бензол",
    "Метилбензол": "Толуол",
    "Этилбензол": "Этилбензол",
}

def shorten_pollutant(name):
    name = str(name).strip()
    if name in POLLUTANT_SHORT:
        return POLLUTANT_SHORT[name]
    # Берём первое слово/часть до скобки
    short = name.split("(")[0].split("/")[0].strip()
    return short[:35] if len(short) > 35 else short

def process_air_emissions(monthly_df, devices_df, sum_df, emerg_fl_df, emerg_m_df):
    print("\nОбработка выбросов в воздух...")

    # ── Месячный тренд: фильтр отрицательных, топ-5 веществ ─────────────────
    monthly_df = monthly_df.copy()
    monthly_df["month"] = pd.to_datetime(monthly_df["month"]).dt.strftime("%Y-%m")
    monthly_df["total_emissions"] = pd.to_numeric(monthly_df["total_emissions"], errors="coerce")
    monthly_df["substance"] = monthly_df["emission_type_name"].map(
        lambda x: SUBSTANCE_SHORT.get(str(x), str(x))
    )
    # Исключаем Пыль (PM) — переполнение числового типа в НБД СОС (значения ~10^34)
    BROKEN_SUBSTANCES = {"Пыль (взвешенные частицы)", "Пыль (PM)"}
    monthly_df = monthly_df[~monthly_df["emission_type_name"].isin(BROKEN_SUBSTANCES)]
    # Исключаем аномальные месяцы: Jul-Sep 2024 дали переполнение для CO/NO₂/NO/SO₂
    # Порог: месяц считается аномальным если |emissions| > 1e9 (реальные значения < 1e8)
    monthly_df = monthly_df[monthly_df["total_emissions"].abs() <= 1e9]
    clean_m = monthly_df[monthly_df["total_emissions"] > 0]
    top5_names = (clean_m.groupby("substance")["total_emissions"]
                  .sum().sort_values(ascending=False).head(5).index.tolist())
    top5_df = clean_m[clean_m["substance"].isin(top5_names)]
    all_months = sorted(clean_m["month"].unique().tolist())
    monthly_series = []
    for sub in top5_names:
        sub_df = top5_df[top5_df["substance"] == sub].set_index("month")["total_emissions"]
        monthly_series.append({
            "name": sub,
            "data": [round(float(sub_df.get(m, 0)), 2) for m in all_months],
        })
    print(f"  Месяцев: {len(all_months)} | Топ-5: {top5_names}")

    # ── Топ источников — исключаем ТЕСТ ──────────────────────────────────────
    devices_df = devices_df[
        (devices_df["emission_metering_device_id"] != 1) &
        (devices_df["total_emissions"] > 0)
    ].copy()
    devices_df["name_short"] = devices_df["emission_metering_device_name"].str.slice(0, 50)
    top_sources = [
        {"name": row["name_short"], "total": round(float(row["total_emissions"]), 2),
         "measurements": int(row["measurements"])}
        for _, row in devices_df.head(15).iterrows()
    ]
    print(f"  Источников: {len(top_sources)}")

    # ── Итого по веществам: пересчитываем из уже очищенных месячных данных ──
    # (исходный SUM CSV содержит испорченные суммы за Jul-Sep 2024 — не используем)
    sub_agg = (clean_m.groupby("substance")["total_emissions"]
               .agg(total="sum", measurements="count")
               .reset_index())
    sub_agg["avg"] = sub_agg["total"] / sub_agg["measurements"].replace(0, 1)
    total_by_substance = [
        {"name": row["substance"], "total": round(float(row["total"]), 2),
         "measurements": int(row["measurements"]), "avg": round(float(row["avg"]), 4)}
        for _, row in sub_agg.sort_values("total", ascending=False).iterrows()
    ]
    print(f"  Веществ (валидных): {len(total_by_substance)}")

    # ── Аварийные: факт vs лимит по загрязнителю ─────────────────────────────
    emerg_fl_df = emerg_fl_df.copy()
    emerg_fl_df["name_short"] = emerg_fl_df["pollutant_name"].map(shorten_pollutant)
    emerg_by_pollutant = [
        {"name": row["name_short"],
         "actual": round(float(row["total_actual"]), 2),
         "limit":  round(float(row["total_limit"]),  2),
         "measurements": int(row["measurements"]),
         "exceedances":  int(row["exceedances"])}
        for _, row in emerg_fl_df.sort_values("total_actual", ascending=False).head(20).iterrows()
    ]
    total_exceedances = int(emerg_fl_df["exceedances"].sum())
    print(f"  Аварийные загрязнители: {len(emerg_by_pollutant)} | Превышений: {total_exceedances}")

    # ── Аварийные: месячный тренд факт vs лимит ──────────────────────────────
    emerg_m_df = emerg_m_df.copy()
    emerg_m_df["month"] = pd.to_datetime(emerg_m_df["month"]).dt.strftime("%Y-%m")
    emerg_monthly = [
        {"month": row["month"],
         "actual": round(float(row["total_actual"]), 2),
         "limit":  round(float(row["total_limit"]),  2),
         "exceedances": int(row["exceedances"])}
        for _, row in emerg_m_df.sort_values("month").iterrows()
    ]
    total_actual_all = round(float(emerg_m_df["total_actual"].sum()), 2)
    total_limit_all  = round(float(emerg_m_df["total_limit"].sum()),  2)
    print(f"  Аварийных месяцев: {len(emerg_monthly)} | Факт: {total_actual_all:,.0f} | Лимит: {total_limit_all:,.0f}")

    return {
        "monthly_labels": all_months,
        "monthly_series": monthly_series,
        "top_sources": top_sources,
        "total_by_substance": total_by_substance,
        "emergency_by_pollutant": emerg_by_pollutant,
        "emergency_monthly": emerg_monthly,
        "summary": {
            "total_exceedances": total_exceedances,
            "total_actual": total_actual_all,
            "total_limit":  total_limit_all,
        },
    }


# ── КГС: МАППИНГИ ────────────────────────────────────────────────────────────
KGS_REGION_MAP = {
    "Акмолинская область":            "Акмолинская",
    "Актюбинская область":            "Актюбинская",
    "Алматинская область":            "Алматинская обл.",
    "Атырауская область":             "Атырауская",
    "Восточно-Казахстанская область": "ВКО",
    "Жамбылская область":             "Жамбылская",
    "Западно-Казахстанская область":  "ЗКО",
    "Карагандинская область":         "Карагандинская",
    "Костанайская область":           "Костанайская",
    "Кызылординская область":         "Кызылординская",
    "Мангистауская область":          "Мангистауская",
    "Павлодарская область":           "Павлодарская",
    "Северо-Казахстанская область":   "СКО",
    "Туркестанская область":          "Туркестанская",
    "г. Астана":                      "Астана",
    "г.Алматы":                       "Алматы",
    "г.Шымкент":                      "Шымкент",
    "Область Абай":                   "Абайская",
    "область Абай":                   "Абайская",
    "Абайская область":               "Абайская",
    "Область Жетісу":                 "Жетысуская",
    "Жетысуская область":             "Жетысуская",
    "Область Ұлытау":                 "Улытауская",
    "Улытауская область":             "Улытауская",
}

def norm_region(raw):
    r = str(raw).strip()
    return KGS_REGION_MAP.get(r, r)

# ── КГС: ЛЕСА ────────────────────────────────────────────────────────────────
def process_kgs_forest(df):
    print("\nОбработка КГС — Леса...")
    df = df.copy()
    df["ploshad"] = pd.to_numeric(df["ploshad"], errors="coerce").fillna(0)
    df["_region"] = df["region"].map(norm_region)
    df["god"] = df["god"].astype(str)

    total       = len(df)
    legal_cnt   = int((df["is_legal"] == "Законная").sum())
    illegal_cnt = int((df["is_legal"] == "Незаконная").sum())
    area_legal   = round(float(df.loc[df["is_legal"] == "Законная",   "ploshad"].sum()), 1)
    area_illegal = round(float(df.loc[df["is_legal"] == "Незаконная", "ploshad"].sum()), 1)
    print(f"  Всего: {total:,} | Законных: {legal_cnt:,} ({area_legal:,} га) | Незаконных: {illegal_cnt:,} ({area_illegal:,} га)")

    # По годам
    by_year = []
    for yr, grp in sorted(df.groupby("god")):
        by_year.append({
            "year":         yr,
            "legal":        int((grp["is_legal"] == "Законная").sum()),
            "illegal":      int((grp["is_legal"] == "Незаконная").sum()),
            "area_legal":   round(float(grp.loc[grp["is_legal"] == "Законная",   "ploshad"].sum()), 1),
            "area_illegal": round(float(grp.loc[grp["is_legal"] == "Незаконная", "ploshad"].sum()), 1),
        })

    # Топ регионов по незаконным рубкам
    ill_df = df[df["is_legal"] == "Незаконная"]
    top_illegal_regions = [
        [k, int(v)] for k, v in ill_df["_region"].value_counts().head(8).items()
    ]

    # Топ регионов по всем рубкам
    top_regions = [
        [k, round(float(grp["ploshad"].sum()), 1)]
        for k, grp in sorted(df.groupby("_region"), key=lambda x: -x[1]["ploshad"].sum())[:8]
    ]

    return {
        "total":              total,
        "legal":              legal_cnt,
        "illegal":            illegal_cnt,
        "area_legal_ha":      area_legal,
        "area_illegal_ha":    area_illegal,
        "by_year":            by_year,
        "top_regions":        top_regions,
        "top_illegal_regions": top_illegal_regions,
    }

# ── КГС: ЗЕМЛИ ───────────────────────────────────────────────────────────────
LAND_RESULT_NORM = {
    "Объект строительства ":   "Объект строительства",
    "Объект строительства  ":  "Объект строительства",
    "Объект строительства   ": "Объект строительства",
    "Объект строителсьтва":    "Объект строительства",
    "Объект строительcтва":    "Объект строительства",
    "Объект стоительства":     "Объект строительства",
    "ЗУ с нарушениями границ": "ЗУ с нарушением границ",
}

def process_kgs_land(df):
    print("\nОбработка КГС — Земли (самозахваты)...")
    df = df.copy()
    df["_result"] = df["result"].map(lambda x: LAND_RESULT_NORM.get(str(x).strip(), str(x).strip()))
    df["city"]    = df["city"].map(lambda x: str(x).strip())
    df["god"]     = df["god"].astype(str)

    total = len(df)
    print(f"  Всего: {total:,}")

    by_result = [[k, int(v)] for k, v in df["_result"].value_counts().head(8).items()]
    by_city   = [[k, int(v)] for k, v in df["city"].value_counts().head(10).items()]
    by_year   = [{"year": yr, "count": int(cnt)}
                 for yr, cnt in sorted(df.groupby("god").size().items())]

    return {
        "total":     total,
        "by_result": by_result,
        "by_city":   by_city,
        "by_year":   by_year,
    }

# ── КГС: НЕДРА ───────────────────────────────────────────────────────────────
def process_kgs_nedra(df):
    print("\nОбработка КГС — Недра...")
    df = df.copy()
    df["area"]    = pd.to_numeric(df["area"], errors="coerce").fillna(0)
    df["_region"] = df["region"].map(norm_region)
    df["god"]     = df["god"].astype(str)
    df["_class"]  = df["mining_class"].map(lambda x: str(x).strip())

    total      = len(df)
    total_area = round(float(df["area"].sum()), 1)
    print(f"  Всего: {total:,} | Площадь: {total_area:,} га")

    by_class  = [[k, int(v)] for k, v in df["_class"].value_counts().head(6).items() if k]
    by_region = [[k, int(v)] for k, v in df["_region"].value_counts().head(8).items()]
    by_year   = [
        {"year": yr, "count": int(len(grp)), "area_ha": round(float(grp["area"].sum()), 1)}
        for yr, grp in sorted(df.groupby("god"))
    ]

    return {
        "total":      total,
        "total_area_ha": total_area,
        "by_class":   by_class,
        "by_region":  by_region,
        "by_year":    by_year,
    }

# ── КГС: ОТХОДЫ (несанкционированные свалки) ─────────────────────────────────
WASTE_STATUS_NORM = {
    "Утилизирован (несанкционированные)": "Утилизирован",
    "Не утилизирован":                    "Не утилизирован",
    "Частная территория":                 "Частная территория",
    "Отсутствует":                        "Отсутствует",
}
WASTE_TYPE_NORM = {
    "Твердые бытовые отходы (ТБО)":      "ТБО",
    "Полигон строительных отходов":      "Строительные отходы",
    "Полигон промышленных отходов":      "Промышленные отходы",
    "Другое":                            "Другое",
}

def process_kgs_waste(df):
    print("\nОбработка КГС — Отходы (несанкционированные свалки)...")
    df = df.copy()
    df["area"]     = pd.to_numeric(df["area"], errors="coerce").fillna(0)
    df["_region"]  = df["region"].map(norm_region)
    df["god"]      = df["god"].astype(str)
    df["_status"]  = df["statustext"].map(lambda x: WASTE_STATUS_NORM.get(str(x).strip(), str(x).strip()))
    df["_type"]    = df["vid_othod"].map(lambda x: WASTE_TYPE_NORM.get(str(x).strip(), str(x).strip()))

    total        = len(df)
    cleared      = int((df["_status"] == "Утилизирован").sum())
    uncleared    = int((df["_status"] == "Не утилизирован").sum())
    total_area   = round(float(df["area"].sum()), 2)
    cleared_pct  = round(cleared / total * 100) if total else 0
    print(f"  Всего: {total:,} | Утилизировано: {cleared:,} ({cleared_pct}%) | Не утилизировано: {uncleared:,}")

    by_status  = [[k, int(v)] for k, v in df["_status"].value_counts().head(6).items() if k and k not in ("","6","2","Добавить")]
    by_type    = [[k, int(v)] for k, v in df["_type"].value_counts().head(6).items()   if k and k not in ("","6","2","Добавить")]
    by_region  = [[k, int(v)] for k, v in df["_region"].value_counts().head(10).items()]
    by_year    = [{"year": yr, "total": int(len(grp)), "cleared": int((grp["_status"] == "Утилизирован").sum())}
                  for yr, grp in sorted(df.groupby("god"))]

    return {
        "total":       total,
        "cleared":     cleared,
        "uncleared":   uncleared,
        "cleared_pct": cleared_pct,
        "total_area_ha": total_area,
        "by_status":   by_status,
        "by_type":     by_type,
        "by_region":   by_region,
        "by_year":     by_year,
    }

# ── ФАКЕЛЬНЫЕ ВЫБРОСЫ ────────────────────────────────────────────────────────
FIRE_ORG_SHORT = {
    'ТОВАРИЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "GAS PROCESSING COMPANY"': "GAS PROCESSING COMPANY",
    'ФИЛИАЛ "НОРТ КАСПИАН ОПЕРЕЙТИНГ КОМПАНИ Н.В."': "NCOC (Кашаган)",
}

FIRE_SUBSTANCE_SHORT = {
    "Сероводород (факел)": "H₂S",
    "Углерод оксид-сульфид": "COS",
    "Сероуглерод": "CS₂",
    "Меркаптаны": "Меркаптаны",
    "Этилмеркаптан": "Этилмеркаптан",
    "Метилмеркаптан": "Метилмеркаптан",
    "Пропилмеркаптан": "Пропилмеркаптан",
    "Бутилмеркаптан": "Бутилмеркаптан",
    "Оксид азота": "NO",
}

def _safe_float(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return float("nan")

def process_fire_emissions(df):
    print("\nОбработка факельных выбросов...")
    df = df.copy()
    df["vol"] = df["volumetric_gas_consumption_m3_s"].apply(_safe_float)
    df["registered_at"] = pd.to_datetime(df["registered_at"], errors="coerce")
    df["month"] = df["registered_at"].dt.to_period("M").astype(str)
    df["substance"] = df["emission_type"].map(lambda x: FIRE_SUBSTANCE_SHORT.get(str(x), str(x)))
    df["org_short"] = df["organization_name"].map(lambda x: FIRE_ORG_SHORT.get(str(x), str(x)[:40]))

    total_records = len(df)
    n_orgs = df["organization_name"].nunique()
    n_sources = df["source_name"].nunique()
    date_from = df["registered_at"].min().strftime("%Y-%m")
    date_to = df["registered_at"].max().strftime("%Y-%m")

    # Дедублируем: каждый момент×источник даёт одну flow-rate строку (N веществ ссылаются на одно значение)
    # Оставляем только уникальные (время, орг, источник) для агрегации объёмов
    unique_r = (df.drop_duplicates(subset=["registered_at", "organization_name", "source_name"])
                  .query("vol > 0"))

    # Месячный тренд — среднее значение потока, переводим в м³/ч (* 3600)
    monthly_agg = unique_r.groupby("month").agg(
        avg_flow=("vol", "mean"),
        max_flow=("vol", "max"),
        readings=("vol", "count"),
    ).reset_index()
    monthly_labels = sorted(monthly_agg["month"].tolist())
    idx = monthly_agg.set_index("month")
    monthly_avg_flow = [round(float(idx["avg_flow"].get(m, 0)) * 3600, 2) for m in monthly_labels]
    monthly_max_flow = [round(float(idx["max_flow"].get(m, 0)) * 3600, 2) for m in monthly_labels]

    # По веществам (сумма vol из всех строк, но делим на кол-во уникальных веществ чтобы не дублить)
    fire_clean = df[df["vol"] > 0]
    by_sub_raw = fire_clean.groupby("substance")["vol"].sum().sort_values(ascending=False)
    by_substance = [[k, round(float(v), 2)] for k, v in by_sub_raw.items()]

    # По организации — средний поток
    by_org = [
        {"name": FIRE_ORG_SHORT.get(k, k[:40]), "avg_flow_m3h": round(float(v) * 3600, 2)}
        for k, v in unique_r.groupby("organization_name")["vol"].mean().sort_values(ascending=False).items()
    ]

    # По месяцам в разрезе организаций
    by_org_monthly = []
    for org, grp in unique_r.groupby("organization_name"):
        short = FIRE_ORG_SHORT.get(str(org), str(org)[:40])
        m_series = grp.groupby("month")["vol"].mean()
        by_org_monthly.append({
            "name": short,
            "data": [round(float(m_series.get(m, 0)) * 3600, 2) for m in monthly_labels],
        })

    print(f"  Записей: {total_records:,} | Уникальных замеров: {len(unique_r):,}")
    print(f"  Организаций: {n_orgs} | Источников: {n_sources}")
    print(f"  Период: {date_from} → {date_to}")

    return {
        "summary": {
            "total_records": total_records,
            "organizations": n_orgs,
            "sources": n_sources,
            "date_from": date_from,
            "date_to": date_to,
        },
        "monthly_labels": monthly_labels,
        "monthly_avg_flow": monthly_avg_flow,
        "monthly_max_flow": monthly_max_flow,
        "by_org_monthly": by_org_monthly,
        "by_substance": by_substance,
        "by_org": by_org,
    }


# ── СТОЧНЫЕ ВОДЫ ─────────────────────────────────────────────────────────────
# Битые датчики:
#  - Карагандинская (Рудник Саяк): pH 99.5% = 0 — датчик не работал
#  - СКО Севказэнерго ПТЭЦ-2: flow<0, turbidity застряла на 3400 NTU, pH=0 — неисправен
#  - ГКП Очистные сооружения (СКО): ВАЛИДНЫЕ данные — оставляем, фильтруем flow>0
WATER_BAD_REGIONS = {"Карагандинская область"}
WATER_BAD_ORGS = {"АО \"Севказэнерго\" ПТЭЦ-2"}
WATER_REGION_MAP = {
    **KGS_REGION_MAP,
    "Восточно-Казхастанская область": "ВКО",   # опечатка в данных
}

WATER_ORG_SHORT = {
    'ТОО "Казцинк" Риддерский горно-обогатительный комплекс':                            "Казцинк Риддер ГОК",
    'ТОО "Казцинк" Риддерский металлургический комплекс':                               "Казцинк Риддер МК",
    'АО "Усть-Каменогорский титано-магневый комбинат"':                                 "УК Титано-магн. комб.",
    'ТОО Усть-Каменогорск ТЭЦ':                                                         "УК ТЭЦ",
    'Товарищество с ограниченной ответственностью "Согринская ТЭЦ"':                    "Согринская ТЭЦ",
    'Филал АО "Алюминий Казахстана" Краснооктябрьское Бокситовое Рудоуправление (КБРУ)': "АК КБРУ",
    'АКЦИОНЕРНОЕ ОБЩЕСТВО "АТЫРАУСКАЯ ТЕПЛОЭЛЕКТРОЦЕНТРАЛЬ"':                           "Атырауская ТЭЦ",
    'ТОО "Казцинк" Усть-Каменогорский металлургический комплекс':                       "Казцинк УК МК",
    'ТОО "Казцинк" Горно-обогатительный комплекс Алтай':                                "Казцинк ГОК Алтай",
    'АО Ульбинский металлургический завод':                                              "Ульбинский МЗ",
    'АКЦИОНЕРНОЕ ОБЩЕСТВО "МАЙКУБЕН-ВЕСТ"':                                             "Майкубен-Вест",
    'ТОО "Богатырь Комир"':                                                             "Богатырь Комир",
    'ТОО "BM MINING"':                                                                  "BM MINING",
    'ТОВАРИЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "КОМАРОВСКОЕ ГОРНОЕ ПРЕДПРИЯТИЕ"':    "Комаровское ГП",
    'ТОВАРИЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РИДДЕР-ПОЛИМЕТАЛЛ"':                 "Риддер-Полиметалл",
    'ТОО "Востокцветмет"':                                                              "Востокцветмет",
    'ГКП на ПХВ «Очистные, водоотводные и водопропускные сооружения» ':                "Очистные сооружения",
    'АО "Севказэнерго" ПТЭЦ-2':                                                         "Севказэнерго ПТЭЦ-2",
    'АКЦИОНЕРНОЕ ОБЩЕСТВО "МАЙКУБЕН-ВЕСТ"':                                             "Майкубен-Вест",
    'АО Жамбылская ГРЭС им. Т.И. Батурова':                                            "Жамбылская ГРЭС",
    'ТОО "ALTYN SHYGHYS"':                                                              "ALTYN SHYGHYS",
    'АО "Севказэнерго" ПТЭЦ-2':                                                         "Севказэнерго ПТЭЦ-2",
    'Донской горно-обогатительный комбинат - филиал АО ТНК КазХром':                   "Донской ГОК (КазХром)",
    'Рудник Саяк ТОО Корпорация Казахмыс ПО Балхашцветмет':                            "Рудник Саяк",
}

def process_water_emissions(df):
    print("\nОбработка сточных вод...")
    df = df.copy()

    # Исправляем смешанные типы
    for col in ["waste_water_flow_m3_h", "ph", "turbidity_ntu", "waste_water_temperature_c", "electrical_conductivity_us_cm"]:
        df[col] = df[col].apply(_safe_float)

    df["registered_at"] = pd.to_datetime(df["registered_at"], errors="coerce")
    df["month"] = df["registered_at"].dt.to_period("M").astype(str)

    # ── Исключаем орг/регионы с битыми датчиками ─────────────────────────────
    n_before = len(df)
    df = df[~df["region"].isin(WATER_BAD_REGIONS)]
    df = df[~df["organization_name"].isin(WATER_BAD_ORGS)]
    df = df[~df["organization_name"].str.contains("Тест", na=False)]
    # Исключаем период калибровки (до июня 2024 — pH≈0, мизерный поток)
    df = df[df["registered_at"] >= "2024-06-01"]
    # Фильтруем явные невалидные значения
    df = df[df["waste_water_flow_m3_h"] > 0]   # 0 = датчик не пишет; отрицательные = обратный ток у битых датчиков
    df = df[(df["ph"] > 0) & (df["ph"] <= 14)]  # pH=0.0 = датчик не откалиброван
    df = df[df["turbidity_ntu"] >= 0]

    print(f"  Исходных: {n_before:,} → Чистых: {len(df):,}")

    df["_region"] = df["region"].map(lambda x: WATER_REGION_MAP.get(str(x), str(x)))

    total_records = len(df)
    n_orgs = df["organization_name"].nunique()
    n_sources = df["source_name"].nunique()
    date_from = df["registered_at"].min().strftime("%Y-%m")
    date_to = df["registered_at"].max().strftime("%Y-%m")

    ph_normal = int(((df["ph"] >= 6) & (df["ph"] <= 9)).sum())
    ph_normal_pct = round(100 * ph_normal / len(df)) if len(df) else 0
    ph_acidic_pct = round(100 * int((df["ph"] < 6).sum()) / len(df)) if len(df) else 0
    ph_alkaline_pct = round(100 * int((df["ph"] > 9).sum()) / len(df)) if len(df) else 0

    # Месячный тренд
    m_agg = df.groupby("month").agg(
        flow_mean=("waste_water_flow_m3_h", "mean"),
        ph_mean=("ph", "mean"),
        turbidity_mean=("turbidity_ntu", "mean"),
        records=("waste_water_flow_m3_h", "count"),
    ).reset_index()
    monthly_labels = sorted(m_agg["month"].tolist())
    idx = m_agg.set_index("month")
    monthly_flow = [round(float(idx["flow_mean"].get(m, 0)), 1) for m in monthly_labels]
    monthly_ph = [round(float(idx["ph_mean"].get(m, 0)), 2) for m in monthly_labels]
    monthly_turb = [round(float(idx["turbidity_mean"].get(m, 0)), 1) for m in monthly_labels]

    # По регионам
    by_region = []
    for reg, grp in df.groupby("_region"):
        ph_n = int(((grp["ph"] >= 6) & (grp["ph"] <= 9)).sum())
        by_region.append({
            "name": str(reg),
            "flow_mean": round(float(grp["waste_water_flow_m3_h"].mean()), 1),
            "ph_mean": round(float(grp["ph"].mean()), 2),
            "ph_normal_pct": round(100 * ph_n / len(grp)) if len(grp) else 0,
            "turb_mean": round(float(grp["turbidity_ntu"].mean()), 1),
            "records": len(grp),
        })
    by_region.sort(key=lambda x: -x["flow_mean"])

    # Топ-10 организаций по среднему потоку
    by_org = []
    for org, grp in df.groupby("organization_name"):
        short = WATER_ORG_SHORT.get(str(org), str(org)[:45])
        ph_n = int(((grp["ph"] >= 6) & (grp["ph"] <= 9)).sum())
        by_org.append({
            "name": short,
            "flow_mean": round(float(grp["waste_water_flow_m3_h"].mean()), 1),
            "ph_mean": round(float(grp["ph"].mean()), 2),
            "ph_normal_pct": round(100 * ph_n / len(grp)) if len(grp) else 0,
        })
    by_org.sort(key=lambda x: -x["flow_mean"])
    by_org = by_org[:12]

    print(f"  Организаций: {n_orgs} | Источников: {n_sources} | Регионов: {df['_region'].nunique()}")
    print(f"  Период: {date_from} → {date_to} | pH в норме: {ph_normal_pct}%")

    return {
        "summary": {
            "total_records": total_records,
            "organizations": n_orgs,
            "sources": n_sources,
            "date_from": date_from,
            "date_to": date_to,
            "ph_normal_pct": ph_normal_pct,
            "ph_acidic_pct": ph_acidic_pct,
            "ph_alkaline_pct": ph_alkaline_pct,
        },
        "monthly_labels": monthly_labels,
        "monthly_flow": monthly_flow,
        "monthly_ph": monthly_ph,
        "monthly_turbidity": monthly_turb,
        "by_region": by_region,
        "by_org": by_org,
    }


# ── НАКОПЛЕННЫЕ ОТХОДЫ (НБД СОС) ─────────────────────────────────────────────
def process_accumulation_waste(df):
    print("\nОбработка накопленных отходов (НБД СОС)...")
    df = df[df["aw.is_deleted"] == False].copy()
    df["create_dt"] = pd.to_datetime(df["aw.create_date"], errors="coerce")

    # Чистим объёмы: убираем отрицательные и физически невозможные значения
    VLIM = 1e9
    for col in ["aw.generated_volume", "aw.transferred_volume", "aw.end_balance", "aw.storage_limit"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].where((df[col] >= 0) & (df[col] < VLIM), other=0)

    n_reports = int(df["aw.report_id"].nunique())
    n_sites   = int(df["waste_place_storage_id"].dropna().nunique())

    # ── KPI generated/transferred: только месячные (основная частота, без двойного счёта) ──
    monthly = df[df["freq_measurement_name"] == "месяц"].copy()
    total_gen   = float(monthly["aw.generated_volume"].sum())
    total_trans = float(monthly["aw.transferred_volume"].sum())
    util_pct    = round(total_trans / total_gen * 100, 1) if total_gen > 0 else 0

    # ── KPI accumulated (end_balance): последнее показание на каждое место хранения ──
    # end_balance — точечный показатель, нельзя суммировать все замеры
    has_site = df[df["waste_place_storage_id"].notna()].copy()
    latest_per_site = has_site.sort_values("create_dt").groupby("waste_place_storage_id").last()
    total_accum = float(latest_per_site["aw.end_balance"].sum())

    print(f"  Строк: {len(df):,} | Отчётов: {n_reports:,} | Мест хранения: {n_sites:,}")
    print(f"  Образовано (месячн.): {total_gen/1e6:.0f} млн т | Передано: {total_trans/1e6:.0f} млн т | Утилизация: {util_pct}%")
    print(f"  Накоплено (последний замер/место): {total_accum/1e6:.0f} млн т")

    # ── КВАРТАЛЬНЫЙ ТРЕНД (только месячные замеры) ────────────────────────────
    monthly["q"] = monthly["create_dt"].dt.to_period("Q").astype(str)
    trend_raw = monthly[monthly["q"] >= "2024Q1"].groupby("q").agg(
        generated=("aw.generated_volume", "sum"),
        transferred=("aw.transferred_volume", "sum"),
    ).reset_index()
    quarterly_trend = [
        {"q": row["q"],
         "generated":   round(row["generated"]  / 1e6, 2),
         "transferred": round(row["transferred"] / 1e6, 2)}
        for _, row in trend_raw.iterrows()
        if row["q"] <= "2026Q1"
    ]

    # ── ТОП ВИДОВ ОТХОДОВ: последний замер на место × вид отхода ────────────────
    # Последнее показание end_balance для каждой пары (место × вид)
    has_site2 = df[df["waste_place_storage_id"].notna()].copy()
    latest_by_type = (has_site2.sort_values("create_dt")
                                .groupby(["waste_place_storage_id","waste_name"])
                                .last()
                                .reset_index())
    top_types_raw = latest_by_type.groupby("waste_name")["aw.end_balance"].sum().sort_values(ascending=False).head(12)
    top_types = [
        [str(k)[:80], round(float(v) / 1e6, 1)]
        for k, v in top_types_raw.items() if float(v) > 1e4
    ]

    # ── ЗАПОЛНЕННОСТЬ МЕСТ ХРАНЕНИЯ ──────────────────────────────────────────
    # Берём последнее чтение для каждого места хранения
    valid_lim = df[(df["aw.storage_limit"] > 0.1) & (df["waste_place_storage_id"].notna())].copy()
    valid_lim = valid_lim.sort_values("create_dt")
    latest    = valid_lim.groupby("waste_place_storage_id").last().reset_index()
    latest    = latest[latest["aw.storage_limit"] > 0]
    latest["fill_pct"] = (latest["aw.end_balance"] / latest["aw.storage_limit"] * 100).clip(0, 200).round(1)
    top_fill_df = latest.nlargest(12, "fill_pct")[["waste_place_storage","fill_pct","aw.end_balance","aw.storage_limit"]]
    top_fill = [
        {"name": str(r["waste_place_storage"])[:60],
         "fill_pct": float(r["fill_pct"]),
         "bal_t": round(float(r["aw.end_balance"]), 1),
         "lim_t": round(float(r["aw.storage_limit"]), 1)}
        for _, r in top_fill_df.iterrows()
        if float(r["fill_pct"]) > 0
    ]

    print(f"  Топ видов: {len(top_types)} | Мест с данными заполненности: {len(latest):,}")

    return {
        "kpi": {
            "total_accumulated_mt": round(total_accum / 1e6, 1),
            "total_generated_mt":   round(total_gen   / 1e6, 1),
            "total_transferred_mt": round(total_trans  / 1e6, 1),
            "utilization_pct":      util_pct,
            "n_reports":            n_reports,
            "n_sites":              n_sites,
        },
        "quarterly_trend": quarterly_trend,
        "top_types":        top_types,
        "top_fill":         top_fill,
    }


# ── DRILL-DOWN CHUNKS ────────────────────────────────────────────────────────
def _slugify(s, max_len=44):
    s = re.sub(r'[^\w]', '_', str(s).lower().strip())
    s = re.sub(r'_+', '_', s).strip('_')
    return s[:max_len]

def make_chunks(df, limit=500):
    """Генерирует JSON-чанки по регионам/категориям/типам/годам для drill-down таблицы."""
    print(f"\nГенерация drill-down чанков...")
    os.makedirs(CHUNKS_DIR, exist_ok=True)

    base_cols = [
        "reg_number", "start_dt", "appeal_type", "applicant_type",
        "category", "issue", "subissue", "region", "raion",
        "org_name", "current_working_state", "status_overdue",
        "deadline", "finish_dt", "is_duplicate", "is_forward", "is_ext_forward",
    ]
    cols = [c for c in base_cols if c in df.columns]

    def to_rows(sub_df, n=limit):
        out = (sub_df.sort_values("start_dt", ascending=False, na_position="last")
                     .head(n)[cols].fillna("")
                     .rename(columns={
                         "start_dt":    "created_date",
                         "appeal_type": "type_name_ru",
                         "category":    "issue_category_name_ru",
                     })).copy()
        out["category_short"] = out["issue_category_name_ru"].map(
            lambda x: CATEGORY_SHORT.get(str(x), str(x))
        )
        out["subissue_short"] = out["subissue"].map(
            lambda x: SUBISSUE_SHORT.get(str(x), str(x)[:55]) if str(x) else ""
        )
        return out.to_dict(orient="records")

    manifest = {"reg": {}, "cat": {}, "type": {}, "year": {}}
    count = 0

    # По регионам
    if "_region" in df.columns:
        for reg, grp in df.groupby("_region"):
            slug = f"reg_{_slugify(reg)}.json"
            with open(os.path.join(CHUNKS_DIR, slug), "w", encoding="utf-8") as f:
                json.dump(to_rows(grp), f, ensure_ascii=False)
            manifest["reg"][str(reg)] = slug
            count += 1

    # По категориям (short names — те же значения что в gCatF)
    if "_category" in df.columns:
        for cat, grp in df.groupby("_category"):
            if len(grp) < 30:
                continue
            slug = f"cat_{_slugify(cat)}.json"
            with open(os.path.join(CHUNKS_DIR, slug), "w", encoding="utf-8") as f:
                json.dump(to_rows(grp), f, ensure_ascii=False)
            manifest["cat"][str(cat)] = slug
            count += 1

    # По типам обращений
    if "appeal_type" in df.columns:
        for atype, grp in df.groupby("appeal_type"):
            if len(grp) < 50:
                continue
            slug = f"type_{_slugify(atype)}.json"
            with open(os.path.join(CHUNKS_DIR, slug), "w", encoding="utf-8") as f:
                json.dump(to_rows(grp), f, ensure_ascii=False)
            manifest["type"][str(atype)] = slug
            count += 1

    # По годам (лимит выше — полезно видеть все обращения за год)
    if "start_dt" in df.columns:
        df2 = df.copy()
        df2["_year_s"] = pd.to_datetime(df2["start_dt"], errors="coerce").dt.year.astype("Int64").astype(str)
        for year, grp in df2.groupby("_year_s"):
            if not year or year in ("nan", "<NA>", "NA"):
                continue
            slug = f"year_{year}.json"
            with open(os.path.join(CHUNKS_DIR, slug), "w", encoding="utf-8") as f:
                json.dump(to_rows(grp, n=1000), f, ensure_ascii=False)
            manifest["year"][str(year)] = slug
            count += 1

    with open(os.path.join(CHUNKS_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    reg_count  = len(manifest["reg"])
    cat_count  = len(manifest["cat"])
    type_count = len(manifest["type"])
    year_count = len(manifest["year"])
    print(f"  Чанков: {count} (регионы: {reg_count}, категории: {cat_count}, типы: {type_count}, годы: {year_count})")
    print(f"  Манифест: {CHUNKS_DIR}/manifest.json")
    return manifest


def make_appeals_compact(df, top_orgs):
    """Компактный per-appeal датасет для клиентской фильтрации по дню/месяцу."""
    print("\nКомпактный per-appeal датасет...")
    import numpy as np
    dt = pd.to_datetime(df["start_dt"], errors="coerce")
    mask = dt.notna()
    d = df[mask].copy()
    dt = dt[mask]
    ymd = (dt.dt.year * 10000 + dt.dt.month * 100 + dt.dt.day).astype("int64")

    regions = sorted(d["_region"].dropna().astype(str).unique().tolist())
    cats    = sorted(d["_category"].dropna().astype(str).unique().tolist())
    types   = sorted(d["appeal_type"].dropna().astype(str).unique().tolist())
    issues  = sorted(d["issue"].dropna().astype(str).unique().tolist())
    subs    = sorted(d["_subissue"].dropna().astype(str).unique().tolist())
    # Топ-200 организаций — для поддержки фильтра «Орган-исполнитель»
    top_orgs_full = top_n(df["org_name"], 200)
    org_list = [str(o) for o, _ in top_orgs_full]
    OTHER = len(org_list)

    ri = {v: i for i, v in enumerate(regions)}
    ci = {v: i for i, v in enumerate(cats)}
    ti = {v: i for i, v in enumerate(types)}
    ii = {v: i for i, v in enumerate(issues)}
    si = {v: i for i, v in enumerate(subs)}
    oi = {v: i for i, v in enumerate(org_list)}
    st = {"work": 0, "done": 1, "late": 2, "latedone": 3}

    reg_i = d["_region"].astype(str).map(ri).fillna(0).astype("int64")
    cat_i = d["_category"].astype(str).map(ci).fillna(0).astype("int64")
    typ_i = d["appeal_type"].astype(str).map(ti).fillna(0).astype("int64")
    iss_i = d["issue"].astype(str).map(ii).fillna(0).astype("int64")
    sub_i = d["_subissue"].astype(str).map(si).fillna(0).astype("int64")
    org_i = d["org_name"].astype(str).map(lambda o: oi.get(o, OTHER)).astype("int64")
    st_i  = d["_status"].astype(str).map(st).fillna(0).astype("int64")

    def truthy(col):
        if col in d.columns:
            return d[col].astype(str).str.lower().isin(["y", "1", "true", "да"]).astype("int64")
        return pd.Series(0, index=d.index, dtype="int64")
    flags = truthy("is_duplicate") + truthy("is_forward") * 2 + truthy("is_ext_forward") * 4

    mat = np.column_stack([
        ymd.values, reg_i.values, cat_i.values, typ_i.values,
        st_i.values, iss_i.values, sub_i.values, org_i.values, flags.values,
    ]).astype("int64")

    out = {
        "n": int(mat.shape[0]),
        "w": 9,
        "fields": ["ymd", "region", "cat", "type", "status", "issue", "sub", "org", "flags"],
        "regions": regions, "cats": cats, "types": types,
        "issues": issues, "subs": subs, "orgs": org_list + ["Прочие исполнители"],
        "data": mat.ravel().tolist(),
    }
    path = os.path.join(OUT_DIR, "appeals_compact.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  appeals_compact.json → {os.path.getsize(path)/1024:,.0f} KB ({out['n']:,} обращений)")


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df_appeals    = read_csv(APPEALS_CSV,    "Обращения")
    df_appeals    = filter_ecology(df_appeals)
    df_ikomek     = read_csv(IKOMEK_CSV,     "iKomek")
    df_pek        = read_csv(PEK_CSV,        "ПЭК объекты")
    df_emerg      = read_csv(EMERG_CSV,      "Аварийные выбросы")
    df_air_m      = read_csv(AIR_MONTHLY_CSV,  "Воздух: месячный тренд")
    df_air_dev    = read_csv(AIR_DEVICES_CSV,  "Воздух: топ источников")
    df_air_sum    = read_csv(AIR_SUM_CSV,      "Воздух: итого по веществам")
    df_air_efl    = read_csv(AIR_EMERG_FL_CSV, "Аварийные выбросы воздух: факт/лимит")
    df_air_em     = read_csv(AIR_EMERG_M_CSV,  "Аварийные выбросы воздух: месяц")
    df_kgs_forest = read_csv(KGS_FOREST_CSV,  "КГС: Леса")
    df_kgs_land   = read_csv(KGS_LAND_CSV,    "КГС: Земли")
    df_kgs_nedra  = read_csv(KGS_NEDRA_CSV,   "КГС: Недра")
    df_kgs_waste  = read_csv(KGS_WASTE_CSV,   "КГС: Отходы")
    df_accum_waste= read_csv(ACCUM_WASTE_CSV, "Накопленные отходы")
    df_fire       = read_csv(FIRE_CSV,         "Факельные выбросы")
    df_water      = read_csv(WATER_CSV,        "Сточные воды")

    appeals_data = process_appeals(df_appeals)
    ikomek_data  = process_ikomek(df_ikomek)
    preview      = make_preview(df_appeals)
    make_chunks(df_appeals)
    make_appeals_compact(df_appeals, appeals_data["top_orgs"])
    pek_objects  = process_pek(df_pek)
    emerg_data   = process_emergency(df_emerg)
    air_data     = process_air_emissions(df_air_m, df_air_dev, df_air_sum, df_air_efl, df_air_em)
    kgs_forest   = process_kgs_forest(df_kgs_forest)
    kgs_land     = process_kgs_land(df_kgs_land)
    kgs_nedra    = process_kgs_nedra(df_kgs_nedra)
    kgs_waste    = process_kgs_waste(df_kgs_waste)
    fire_data    = process_fire_emissions(df_fire)
    water_data   = process_water_emissions(df_water)
    waste_accum  = process_accumulation_waste(df_accum_waste)

    summary = {
        "generated": datetime.now().isoformat(),
        "appeals":   appeals_data,
        "ikomek":    ikomek_data,
        "emergency": emerg_data["summary"],
    }

    summary_path  = os.path.join(OUT_DIR, "summary.json")
    preview_path  = os.path.join(OUT_DIR, "preview.json")
    pek_path      = os.path.join(OUT_DIR, "pek_objects.json")
    emerg_path    = os.path.join(OUT_DIR, "emergency_emissions.json")
    air_path      = os.path.join(OUT_DIR, "air_emissions.json")
    kgs_path      = os.path.join(OUT_DIR, "kgs.json")
    fire_path     = os.path.join(OUT_DIR, "fire_emissions.json")
    water_path    = os.path.join(OUT_DIR, "water_emissions.json")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(preview_path, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)

    with open(pek_path, "w", encoding="utf-8") as f:
        json.dump(pek_objects, f, ensure_ascii=False)

    with open(emerg_path, "w", encoding="utf-8") as f:
        json.dump(emerg_data["map"], f, ensure_ascii=False)

    with open(air_path, "w", encoding="utf-8") as f:
        json.dump(air_data, f, ensure_ascii=False, indent=2)

    kgs_data = {"forest": kgs_forest, "land": kgs_land, "nedra": kgs_nedra, "waste": kgs_waste}
    with open(kgs_path, "w", encoding="utf-8") as f:
        json.dump(kgs_data, f, ensure_ascii=False, indent=2)

    with open(fire_path, "w", encoding="utf-8") as f:
        json.dump(fire_data, f, ensure_ascii=False, indent=2)

    with open(water_path, "w", encoding="utf-8") as f:
        json.dump(water_data, f, ensure_ascii=False, indent=2)

    waste_path = os.path.join(OUT_DIR, "waste_accumulation.json")
    with open(waste_path, "w", encoding="utf-8") as f:
        json.dump(waste_accum, f, ensure_ascii=False, indent=2)

    taza_data = process_taza_kz()
    taza_path = os.path.join(OUT_DIR, "taza_kz.json")
    with open(taza_path, "w", encoding="utf-8") as f:
        json.dump(taza_data, f, ensure_ascii=False, indent=2)

    sz_s  = os.path.getsize(summary_path) // 1024
    sz_p  = os.path.getsize(preview_path) // 1024
    sz_pk = os.path.getsize(pek_path)     // 1024
    sz_em  = os.path.getsize(emerg_path)   // 1024
    sz_air = os.path.getsize(air_path)    // 1024
    sz_kgs = os.path.getsize(kgs_path)    // 1024
    sz_fire = os.path.getsize(fire_path)   // 1024
    sz_w   = os.path.getsize(water_path)   // 1024
    sz_wa  = os.path.getsize(waste_path)   // 1024
    sz_tz  = os.path.getsize(taza_path)   // 1024

    em = emerg_data["summary"]
    print(f"\n{'='*55}")
    print(f"  summary.json             → {sz_s} KB")
    print(f"  preview.json             → {sz_p} KB")
    print(f"  pek_objects.json         → {sz_pk} KB")
    print(f"  emergency_emissions.json → {sz_em} KB")
    print(f"  air_emissions.json       → {sz_air} KB")
    print(f"  kgs.json                 → {sz_kgs} KB")
    print(f"  fire_emissions.json      → {sz_fire} KB")
    print(f"  water_emissions.json     → {sz_w} KB")
    print(f"  waste_accumulation.json  → {sz_wa} KB")
    print(f"{'='*55}")
    print(f"  Обращений:        {appeals_data['total']:,}  ({appeals_data['done_pct']}% завершено)")
    print(f"  iKomek:           {ikomek_data['total']:,}")
    print(f"  ПЭК объектов:     {pek_objects['total']:,}  (GPS: {len(pek_objects['objects']):,}, кластеры: {len(pek_objects['clusters'])} регионов)")
    print(f"  Аварийных выбр.:  {em['total']:,}  (карта: {len(emerg_data['map']):,})")
    print(f"  Воздух источников:{len(air_data['top_sources']):,} | Веществ: {len(air_data['total_by_substance'])}")
    print(f"  Факел орг.:       {fire_data['summary']['organizations']} | Период: {fire_data['summary']['date_from']}→{fire_data['summary']['date_to']}")
    print(f"  Сточные воды:     {water_data['summary']['organizations']} орг | pH норма: {water_data['summary']['ph_normal_pct']}%")
    print(f"  Регионов:         {len(appeals_data['by_region'])}")
    print(f"  КГС Леса:         {kgs_forest['total']:,} (незаконных: {kgs_forest['illegal']:,})")
    print(f"  КГС Земли:        {kgs_land['total']:,}")
    print(f"  КГС Недра:        {kgs_nedra['total']:,} ({kgs_nedra['total_area_ha']:,} га)")
    print(f"  КГС Отходы:       {kgs_waste['total']:,} (утилизировано: {kgs_waste['cleared_pct']}%)")
    print(f"  taza_kz.json             → {sz_tz} KB  ({taza_data['total']:,} заявок, {taza_data['done_pct']}% исп.)")
    print(f"\n  ГОТОВО. Следующий шаг:")
    print(f"  cd ~/Downloads/eco-dashboard && vercel --prod")

def process_taza_kz():
    """Обработка данных системы Таза Казахстан → taza_kz.json"""
    import statistics, collections

    # ── Справочники ──────────────────────────────────────────────────────────
    cats = {}
    try:
        with open(TAZA_CATS_CSV, encoding="utf-8") as f:
            for row in __import__("csv").DictReader(f):
                cats[row["id"]] = row["name_ru"]
    except Exception: pass

    # Строим иерархию регионов: id → {name, parent_id}
    reg_info = {}
    try:
        with open(TAZA_REGIONS_CSV, encoding="utf-8") as f:
            for row in __import__("csv").DictReader(f):
                reg_info[row["id"]] = {"name": row["name_ru"], "parent": row.get("parent_id","") or ""}
    except Exception: pass

    _REG_NORM = {
        "Область Абай": "Абайская область",
        "Абай область": "Абайская область",
        "Абай область дубликат": "Абайская область",
        "Область Жетысу": "Жетысуская область",
        "Область Улытау": "Улытауская область",
    }
    def top_region_name(rid):
        rid = str(rid)
        visited = set()
        while rid and rid not in visited:
            visited.add(rid)
            info = reg_info.get(rid)
            if not info:
                return None
            if not info["parent"]:
                n = info["name"]
                return _REG_NORM.get(n, n)
            rid = info["parent"]
        return None

    # ── Основные заявки ──────────────────────────────────────────────────────
    by_cat    = collections.defaultdict(lambda: {"total":0,"done":0,"overdue":0,"days":[]})
    by_region = collections.defaultdict(lambda: {"total":0,"done":0,"overdue":0,"lat":None,"lon":None})
    monthly   = collections.Counter()
    states    = collections.Counter()
    done_days = []
    total = done = cancelled = in_work = overdue = 0

    import csv, datetime as dt_mod

    with open(TAZA_REQUESTS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            st  = row.get("service_state","")
            ovd = row.get("is_overdue","").lower() in ("true","1")
            cid = row.get("category_id","") or "?"
            rid = str(row.get("region_id",""))
            created = row.get("created_at","")
            done_at = row.get("done_at","")
            states[st] += 1

            if st == "DONE":      done += 1
            elif st == "CANCELLED": cancelled += 1
            elif st in ("WORKING","CREATED","RETURNED_TO_OPERATOR"): in_work += 1
            if ovd: overdue += 1

            by_cat[cid]["total"] += 1
            if st == "DONE":  by_cat[cid]["done"] += 1
            if ovd: by_cat[cid]["overdue"] += 1

            reg_name = top_region_name(rid) or f"Регион {rid}"
            by_region[reg_name]["total"] += 1
            if st == "DONE": by_region[reg_name]["done"] += 1
            if ovd: by_region[reg_name]["overdue"] += 1

            if created:
                monthly[created[:7]] += 1
                if st == "DONE" and done_at:
                    try:
                        c = dt_mod.datetime.fromisoformat(created[:19])
                        d = dt_mod.datetime.fromisoformat(done_at[:19])
                        days = (d - c).days
                        if 0 <= days <= 365:
                            by_cat[cid]["days"].append(days)
                            done_days.append(days)
                    except Exception: pass

    med_days = round(statistics.median(done_days), 1) if done_days else 0
    avg_days = round(statistics.mean(done_days), 1)   if done_days else 0

    # ── Категории ────────────────────────────────────────────────────────────
    categories_out = []
    for cid, v in sorted(by_cat.items(), key=lambda x: -x[1]["total"]):
        if cid == "?": continue
        avg_d = round(statistics.mean(v["days"]), 1) if v["days"] else None
        done_pct = round(v["done"] / v["total"] * 100, 1) if v["total"] else 0
        categories_out.append({
            "id": cid,
            "name": cats.get(cid, f"Категория {cid}"),
            "total": v["total"],
            "done": v["done"],
            "done_pct": done_pct,
            "overdue": v["overdue"],
            "avg_days": avg_d,
        })

    # ── По регионам ──────────────────────────────────────────────────────────
    # Удовлетворённость
    sat_by_reg = collections.defaultdict(list)
    try:
        with open(TAZA_SAT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("rating") and row.get("name_ru"):
                    try:
                        sat_by_reg[row["name_ru"]].append(float(row["rating"]))
                    except Exception: pass
    except Exception: pass

    # Нормализация названий регионов из sat/complaint файлов
    def norm_reg(name):
        return _REG_NORM.get(name, name)

    sat_norm = {norm_reg(k): round(statistics.mean(v), 2) for k, v in sat_by_reg.items() if v}

    # Жалобы
    comp_by_reg = collections.defaultdict(lambda: {"req":0,"comp":0})
    try:
        with open(TAZA_COMPLAINTS_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("name_ru"): continue
                try:
                    n = norm_reg(row["name_ru"])
                    comp_by_reg[n]["req"]  += int(row.get("request_count","0") or 0)
                    comp_by_reg[n]["comp"] += int(row.get("complaint_count","0") or 0)
                except Exception: pass
    except Exception: pass

    regions_out = []
    for rname, v in sorted(by_region.items(), key=lambda x: -x[1]["total"]):
        done_pct  = round(v["done"] / v["total"] * 100, 1) if v["total"] else 0
        ovd_pct   = round(v["overdue"] / v["total"] * 100, 1) if v["total"] else 0
        sat       = sat_norm.get(rname)
        cd        = comp_by_reg.get(rname, {})
        comp_req  = cd.get("req", 0)
        comp_cnt  = cd.get("comp", 0)
        comp_pct  = round(comp_cnt / comp_req * 100, 1) if comp_req else 0
        regions_out.append({
            "name": rname,
            "total": v["total"],
            "done": v["done"],
            "done_pct": done_pct,
            "overdue": v["overdue"],
            "overdue_pct": ovd_pct,
            "satisfaction": sat,
            "complaints": comp_cnt,
            "complaint_pct": comp_pct,
        })

    # ── Удовлетворённость (отдельный список для чарта) ───────────────────────
    sat_list = [{"region": k, "rating": v} for k, v in sat_norm.items() if v > 0]
    sat_list.sort(key=lambda x: x["rating"])

    # ── Месячный тренд ───────────────────────────────────────────────────────
    monthly_out = [{"ym": ym, "total": cnt} for ym, cnt in sorted(monthly.items())]

    # ── Скорость закрытия (распределение) ────────────────────────────────────
    speed = {
        "same_day":  sum(1 for d in done_days if d == 0),
        "d1_3":      sum(1 for d in done_days if 1 <= d <= 3),
        "d4_7":      sum(1 for d in done_days if 4 <= d <= 7),
        "over_7":    sum(1 for d in done_days if d > 7),
    }

    period_months = sorted(monthly.keys())
    result = {
        "total": total,
        "done": done,
        "done_pct": round(done / total * 100, 1) if total else 0,
        "cancelled": cancelled,
        "in_work": in_work,
        "overdue": overdue,
        "overdue_pct": round(overdue / total * 100, 1) if total else 0,
        "median_days": med_days,
        "avg_days": avg_days,
        "period_from": period_months[0] if period_months else "",
        "period_to":   period_months[-1] if period_months else "",
        "categories": categories_out,
        "by_region": regions_out,
        "monthly": monthly_out,
        "satisfaction": sat_list,
        "speed": speed,
    }
    return result


if __name__ == "__main__":
    main()

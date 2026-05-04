# Eco Dashboard — Потоки данных и прогресс

**Последнее обновление:** 2026-04-25 (добавлены fire_emissions.json, water_emissions.json)  
**Продакшн:** https://eco-dashboard-psi.vercel.app

---

## Статус вкладок

| Вкладка | ID | Статус | Источник данных |
|---|---|---|---|
| Главная | `panel-main` | ✅ Реальные данные | summary.json + preview.json + kgs.json + RSS |
| Выбросы | `panel-emissions` | ✅ Реальные данные (очищены) | air_emissions.json + fire_emissions.json + water_emissions.json |
| Отходы | `panel-waste` | ⚠️ Заглушки | Нет данных (КГС данные есть, не подключены) |
| Слушания | `panel-hear` | ⚠️ Заглушки | Нет данных |
| Новости | `panel-news` | ✅ Реальный парсинг | RSS (6 сайтов) + Telegram (2 канала) |
| Карта | `panel-map` | ✅ Реальные данные | pek_objects.json + emergency_emissions.json |
| Обращения | `panel-apps` | ✅ Реальные данные | summary.json + preview.json |
| КГС | `panel-kgs` | ✅ Реальные данные | kgs.json |
| Соц. напряжение | `panel-tension` | ✅ Реальные данные | summary.json (ikomek) |

---

## Архитектура данных

```
CSV-файлы (НБД СОС / eObr / iKomek / КГС)
       ↓
scripts/process_data.py
       ↓
public/data/*.json
       ↓
public/index.html (Vanilla JS + Chart.js + Leaflet)
       ↓
Vercel → eco-dashboard-psi.vercel.app
```

---

## Детальный поток данных по каждому JSON

---

### 1. `public/data/summary.json` (78 KB)

**Генерируется из двух CSV:**

#### appeals (Обращения eObr)
**Источник:** `ecology_eobr_subissues.csv` — 352 641 строка, с 2021-07-01

| Поле в JSON | Откуда | Куда идёт в дашборде |
|---|---|---|
| `total` | COUNT(*) | KPI `kpiEco`, `appKpiTotal` |
| `done` / `latedone` / `work` / `late` | COUNT по `current_working_state` | KPI `kpiDone`, `kpiWork`, `kpiLate` |
| `done_pct` | (done+latedone)/total | KPI `kpiDone` (%) |
| `duplicates` | COUNT WHERE `is_duplicate=Y` | KPI `kpiFwd`, `appKpiDup` |
| `forwarded` | COUNT WHERE `is_forward=Y` | KPI `appKpiFwd` |
| `ext_forwarded` | COUNT WHERE `is_ext_forward=Y` | KPI `appKpiExtFwd` |
| `by_region[region]` | GROUP BY `_region` (маппинг REGION_MAP) | Хороплет карты, региональные KPI, фильтр `gReg` |
| `categories` | TOP-8 `_category` (аббрев. CATEGORY_SHORT) | График `c3` (горизонт. бар), фильтр `gCatF` |
| `appeal_types` | TOP-8 `appeal_type` | График `cAppType` (бар), фильтр `gType` |
| `top_subissues` | TOP-8 `_subissue` (аббрев. SUBISSUE_SHORT) | График `cAppSub` (бар), фильтр `gSubF` |
| `top_issues` | TOP-20 `issue` (сырое название) | Фильтр `gIssueF` (Подкатегория) |
| `top_orgs` | TOP-50 `org_name` | Фильтры `gCGO` (ЦГО) и `gMIO` (МИО) |
| `hierarchy` | GROUP BY `_category → issue → _subissue` (cnt≥50) | Каскадная логика фильтров `_HIERARCHY` |
| `monthly` | GROUP BY `year, month_name` | Обновление KPI при фильтре по году |

**Маппинги:**
- `REGION_MAP`: CSV-регион → ключ дашборда (напр. "Восточно-Казахстанская область" → "ВКО")
- `CATEGORY_SHORT`: длинное название категории → сокращение (напр. "ИСПОЛЬЗОВАНИЕ ПРИРОДНО-СЫРЬЕВЫХ..." → "Экология и природные ресурсы")
- `SUBISSUE_SHORT`: длинное название подвопроса → сокращение (до 55 символов)
- `STATUS_MAP`: статус CSV → done/latedone/work/late

**Иерархия полей CSV:**
```
category (Категория) → issue (Подкатегория) → subissue (Характер вопроса)
```

#### ikomek
**Источник:** `ecology_ikomek.csv` — 16 103 строки, с 2019-04-01

| Поле в JSON | Куда идёт |
|---|---|
| `total` | KPI `kpiIkom` |
| `by_character` | График `cAppChar` (doughnut), вкладка Главная |
| `by_status` | Таблица вкладки Слушания |
| `by_region` | Региональная разбивка |
| `monthly` | Линейный график `c11` на вкладке Соц. напряжение |

#### emergency (Аварийные выбросы — сводка)
**Источник:** `ecology_emergency_emission.csv` — агрегаты только, не сырые строки

| Поле | Куда идёт |
|---|---|
| `total` | KPI `kpiEmerg`, `envEmergCount` |
| `by_year` | KPI `envEmerg2026`, `envEmerg2025`, `envEmergDelta` |
| `cur_ytd` / `prev_ytd` / `delta_ytd` | KPI сравнения год к году |

---

### 2. `public/data/preview.json` (365 KB)

**Источник:** `ecology_eobr_subissues.csv` — последние 300 строк (отсортировано по `start_dt DESC`)

| Поле | Откуда (CSV) | Используется для |
|---|---|---|
| `reg_number` | `reg_number` | Колонка таблицы, поиск |
| `created_date` | `start_dt` (переименовано) | Колонка таблицы |
| `type_name_ru` | `appeal_type` (переименовано) | Колонка, фильтр `appTypeFilter` |
| `issue_category_name_ru` | `category` (переименовано, сырое) | Колонка таблицы (отображение) |
| `category_short` | `category` → CATEGORY_SHORT | Фильтрация по `gCatF`, `appCatFilter`, `prvCat` |
| `issue` | `issue` (сырое) | Колонка, фильтр `gIssueF`, `appIssFilter`, `prvIss` |
| `subissue` | `subissue` (сырое) | Колонка таблицы (отображение) |
| `subissue_short` | `subissue` → SUBISSUE_SHORT | Фильтрация по `gSubF`, `appSubFilter`, `prvSub` |
| `region` | `region` (сырое, не маппировано) | Фильтр региона в таблице |
| `org_name_ru` | `org_name` (переименовано) | Колонка, фильтры `gCGO`/`gMIO` |
| `current_working_state` | `current_working_state` | Статус, фильтр `gStatus` |

**Используется в двух таблицах:**
- `appTblPreview` (`tbody`) — главная страница, `panel-main`
- `appTbl` (`tbody`) — вкладка Обращения, `panel-apps`

---

### 3. `public/data/air_emissions.json` (12 KB)

**Генерируется из 5 CSV-файлов:**

| CSV-файл | Данные | Период |
|---|---|---|
| `ecology_air_emission_measurement_data_month_substances.csv` | Месячный тренд | Oct 2023 → Apr 2026 |
| `ecology_air_emission_measurement_data_top_devices_sum.csv` | Топ источников | Всё время |
| `ecology_air_emission_measurement_data_SUM_substances.csv` | Итоги (НЕ ИСПОЛЬЗУЕТСЯ напрямую — пересчитывается) | — |
| `ecology_emergency_emission_air_fact_vs_limit.csv` | Аварийные: факт vs лимит | 2024–2026 |
| `ecology_emergency_emission_air_month_fact_limit.csv` | Аварийные: месячный тренд | Jan 2024 → Apr 2026 |

**⚠️ Проблемы качества (исправлены в process_data.py):**
- Jul-Sep 2024: CO/NO₂/NO/SO₂ имели значения порядка -10¹¹ (переполнение в НБД СОС) → отфильтровано порогом `|emissions| > 1e9`
- `Пыль (взвешенные частицы)`: значение -4×10³⁴ → исключено навсегда
- `total_by_substance` теперь пересчитывается из очищенных месячных данных, а не из SUM CSV

| Поле JSON | Источник CSV | График на дашборде | ID Canvas |
|---|---|---|---|
| `monthly_labels` + `monthly_series` | month_substances.csv | Линейный: Тренд выбросов топ-5 веществ | `c6` |
| `emergency_monthly` | emerg_month.csv | Бар: Аварийные факт vs лимит по месяцам | `c5` |
| `total_by_substance` | Пересчёт из month_substances | Пончик: Итого по веществам | `cEmTypes` |
| `emergency_by_pollutant` | emerg_fl.csv | Бар: Факт vs лимит по загрязнителям | `cEmSeason` |
| `top_sources` | top_devices.csv | Бар: Топ источников | `_chartNbdSrc` |
| `summary.total_exceedances` | emerg_fl.csv → SUM(exceedances) | KPI `emStatExceed` |
| `summary.total_actual/limit` | emerg_month.csv → SUM | KPI `emStatRatio` (55%) |

**Топ-5 веществ (после очистки):** CO, NO₂, SO₂, NO, Пыль

---

### 4. `public/data/pek_objects.json` (2096 KB)

**Источник:** `ecology_pekobject.csv` — 55 483 строк → 5 478 активных с координатами

**Фильтрация:**
- `is_deleted ≠ True` AND `inactive ≠ True` → активные
- Координаты в пределах КЗ: lat 40–56, lon 49–88
- Целые координаты (51, 71 и т.п.) отброшены — это дефолтные заглушки НБД СОС

| Поле | Откуда | Куда |
|---|---|---|
| `id`, `name`, `lat`, `lon` | CSV прямо | Маркеры карты `pekLayerMain` |
| `cat` / `cat_lbl` | `dic_category_id` (1/2/3) | Цвет маркера: кат.1=красный, кат.2=оранжевый |
| `address`, `region` | `address` | Попап маркера |

**KPI:** `kpiPek` (5 478), `envPekCat1` (941 — кат.1), `envPekCat2` (4 529 — кат.2)

---

### 5. `public/data/emergency_emissions.json` (1582 KB)

**Источник:** `ecology_emergency_emission.csv` — 993 000 строк → 6 720 инцидентов (ReportId) → 4 739 с координатами

**Агрегация:** один `ReportId` = один инцидент. Группируется по ReportId, берётся min(date), first(lat/lng), список загрязнителей.

| Поле | Куда |
|---|---|
| `lat`, `lon` | Маркеры карты `emergLayerMain` |
| `date`, `closed` | Попап: дата инцидента, статус закрытия |
| `pollutants` | Попап: список загрязнителей (до 5) |
| `actual`, `limit` | Попап: объём факт / лимит |

---

### 6. `public/data/kgs.json` (6 KB)

**Источник: 4 CSV от Казахстан Гарыш Сапары (спутниковый мониторинг)**

#### forest (Леса)
**Источник:** `get_forest_detailed.csv` — 24 685 строк

| Поле | Куда |
|---|---|
| `total` / `legal` / `illegal` | KPI `kgsForestTotal`, `kgsForestIllegal`, `kgsMainForestVal` |
| `area_legal_ha` / `area_illegal_ha` | KPI `kgsForestIllArea` (257.6 га незаконных) |
| `by_year` | График `_kgsCharts.forest` (бар по годам, законные vs незаконные) |
| `top_illegal_regions` | Попап/список топ-регионов по незаконным рубкам |

#### land (Самозахваты земель)
**Источник:** `get_land_seizure_detailed.csv` — 5 323 строки

| Поле | Куда |
|---|---|
| `total` | KPI `kgsLandTotal`, `kgsMainLandVal` |
| `by_result` | Разбивка по результату (объект строительства и т.п.) |
| `by_city` | Топ городов |
| `by_year` | График `_kgsCharts.land` (бар по годам) |

#### nedra (Карьеры/недра)
**Источник:** `get_nedra_detailed.csv` — 12 421 строка, 26 488 га

| Поле | Куда |
|---|---|
| `total` / `total_area_ha` | KPI `kgsNedraTotal`, `kgsNedraArea`, `kgsMainNedraVal` |
| `by_class` | Разбивка по классу карьера |
| `by_region` | График `_kgsCharts.nedraReg` (регионы) |
| `by_year` | График `_kgsCharts.nedraYear` |

#### waste (Несанкционированные свалки)
**Источник:** `get_waste_detailed.csv` — 50 122 строки

| Поле | Куда |
|---|---|
| `total` / `cleared` / `uncleared` / `cleared_pct` | KPI `kgsWasteTotal`, `kgsWasteCleared`, `kgsMainWasteVal` |
| `by_status` | Разбивка: утилизирован/не утилизирован |
| `by_type` | ТБО / строительные / промышленные |
| `by_region` | График `_kgsCharts.wasteReg` |
| `by_year` | График `_kgsCharts.wasteYear` |

---

### 7. `public/data/fire_emissions.json` (2 KB)

**Источник:** `view_fire_emissions_full.csv` — 1 269 839 строк, 2 орг., 6 факелов, май 2024 → апр 2026

**⚠️ Проблемы данных:**
- `volumetric_gas_consumption_m3_s` — смешанный тип (str/float, запятая/точка) → `_safe_float()`
- Отрицательные значения (0.47%, "Факел ВД №31") — кратковременный обратный ток, отфильтрованы (`vol > 0`)
- Дублирование: каждый timestamp×источник → N строк (одна на вещество) с одинаковым vol → дедублировано по `(registered_at, org, source)`

| Поле JSON | Источник | График / KPI |
|---|---|---|
| `summary` | Метаданные | KPI `fireStatOrgs`, `fireStatSrc`, `firePeriod` |
| `monthly_labels` + `monthly_avg_flow` | GROUP BY month, AVG(vol) × 3600 | Бар `cFire` |
| `by_org_monthly` | GROUP BY org, month | (не используется в текущем chart) |
| `by_substance` | GROUP BY emission_type, SUM(vol) | (Future: Пончик веществ) |
| `by_org` | GROUP BY org, AVG(vol) × 3600 | Прогресс-бары `fireOrgBars` |

**Организации:** GAS PROCESSING COMPANY (Актюбинская, ср. поток 639 617 м³/ч) | NCOC/Кашаган (Атырауская, 876 м³/ч)

---

### 8. `public/data/water_emissions.json` (4 KB)

**Источник:** `view_water_emissions_full.csv` — 1 163 285 строк → 764 204 чистых, 19 орг., 31 источник, 7 регионов

**⚠️ Проблемы данных и фильтрация:**
- `Карагандинская область` (Рудник Саяк): pH = 0.0 у 99.5% записей → датчик не работал → ИСКЛЮЧЕНА
- `АО Севказэнерго ПТЭЦ-2` (СКО): flow < 0, turbidity зависла на 3400 NTU, pH ≈ 0 → ИСКЛЮЧЕНА конкретная орг.
- `ГКП Очистные сооружения` (СКО): 4 431 валидная запись, pH 7.3, flow 500-640 м³/ч → ОСТАВЛЕНА
- мар-май 2024: pH ≈ 0, мизерный поток → период калибровки → ИСКЛЮЧЁН (начало с 2024-06)
- `Тест АСМ`: тестовые данные → ИСКЛЮЧЕНА

| Поле JSON | Источник | График / KPI |
|---|---|---|
| `summary.ph_normal_pct` | % строк с pH 6–9 | KPI `wtrStatPh` (63%) |
| `summary.ph_acidic_pct` | % строк с pH < 6 | KPI `wtrStatAcid` (2%) |
| `summary.ph_alkaline_pct` | % строк с pH > 9 | KPI `wtrStatAlk` (34%) |
| `monthly_ph` | GROUP BY month, AVG(ph) | Линия `cWaterPh` (с зонами 6-9) |
| `monthly_flow` | GROUP BY month, AVG(waste_water_flow_m3_h) | Бар `cWaterFlow` |
| `by_region` | GROUP BY region, AVG/COUNT | Таблица `wtrRegionTable` |
| `by_org` | TOP-12 орг по ср. потоку | Прогресс-бары `wtrOrgBars` |

**Регионы (7):** ВКО (доминирует — Казцинк), Костанайская, Атырауская, Павлодарская, Актюбинская, СКО, Жамбылская

---

### 9. Новости (без JSON — живой парсинг)

**Маршрут данных:**
```
RSS-лента → /api/proxy?rss=<url> (serverless, allowlist доменов) → parseRssXml() → localStorage (кэш 30 мин)
Telegram → /api/social?channel=<name> → scraping t.me/s → localStorage
```

**RSS-источники:** tengrinews.kz, kapital.kz, 24.kz, kursiv.kz, primeminister.kz, gov.kz  
**Telegram:** @kozachkow, @tengrinews

**AI-анализ новостей:** `/api/proxy` POST → Anthropic API (claude-haiku-4-5) → impact: high/med/low

---

### 10. Карта (Leaflet.js)

**Источники данных для слоёв:**

| Слой | JS-переменная | Данные | Цвет |
|---|---|---|---|
| Регионы хороплет | `geoLayerMain` | `REAL_ECO[region].total` из summary.json | Зелёный градиент |
| Казгидромет | `hydroLayerMain` | `KAZHYDROMET_MAIN` — **ЖЁСТКИЙ КОД** в JS | Фиолетовый |
| ПЭК объекты | `pekLayerMain` | `/data/pek_objects.json` | Красный (кат.1) / Оранжевый (кат.2) |
| Аварийные выбросы | `emergLayerMain` | `/data/emergency_emissions.json` | Жёлтый (закрыт) / Серый (открыт) |

**GeoJSON полигоны:** `public/kaz.geojson` — упрощённые границы регионов РК  
**Маппинг GeoJSON→REAL_ECO:** `GEO_TO_ECO` — словарь в JS (напр. "Атырауская область" → "Атырауская")

---

## Фильтры и их связи

### Глобальный фильтр-бар (влияет на ВСЕ панели)

| ID | Метка | Поле данных | Действие |
|---|---|---|---|
| `gYear` | Год | `summary.appeals.monthly[].year` | Фильтр таблиц + KPI по году |
| `gReg` | Регион | `REAL_ECO` ключи | Фильтр таблиц + KPI по региону |
| `gType` | Тип | `summary.appeals.appeal_types` | Фильтр таблиц + KPI |
| `gCatF` | Категория | `summary.appeals.categories` (аббрев.) | Каскад → `gIssueF` → `gSubF` |
| `gIssueF` | Подкатегория | `summary.appeals.top_issues` (сырое `issue`) | Каскад → `gSubF` |
| `gSubF` | Характер вопроса | `summary.appeals.top_subissues` (аббрев. `subissue`) | Фильтр таблиц |
| `gCGO` | ЦГО | `top_orgs` → keyword-классификация | Фильтр по `org_name_ru` |
| `gMIO` | МИО | `top_orgs` → keyword-классификация | Фильтр по `org_name_ru` |
| `gStatus` | Статус | Hardcode: done/work/late | Фильтр + подсветка KPI |

### Каскадная логика фильтров

```
gCatF (Категория) изменилась
  → _doCascadeMid('gCatF','gIssueF','gSubF')
  → gIssueF перезаполняется из _HIERARCHY[cat] ключами (подкатегории)
  → gSubF перезаполняется из всех значений _HIERARCHY[cat] (характеры)

gIssueF (Подкатегория) изменилась
  → _doCascadeSub('gCatF','gIssueF','gSubF')
  → gSubF перезаполняется только характерами данной подкатегории
```

`_HIERARCHY` = `summary.appeals.hierarchy` = `{категория: {подкатегория: [характеры]}}`  
Строится в process_data.py с порогом `cnt ≥ 50` (убирает редкие комбинации)

### Локальные фильтры таблиц

| Таблица | ID-фильтров | Вызывает |
|---|---|---|
| Главная страница | `prvCat`, `prvIss`, `prvSub` | `filterPrvTable()` |
| Вкладка Обращения | `appCatFilter`, `appIssFilter`, `appSubFilter` | `filterAppTable()` |

Все локальные фильтры применяются **вместе** с глобальными (AND-логика).

---

## Классификация ЦГО / МИО

Ключевые слова для определения типа организации из `top_orgs`:

```js
// ЦГО (Центральные государственные органы)
_CGO_KW = ['министерств','республиканское государственное','агентство республик','жасыл даму','акционерное общество']

// МИО (Местные исполнительные органы)
_MIO_KW = ['аппарат акима','акимат','коммунальное государственное','гкп на праве','коммунальное предприятие']
// + управление + (области|города|района) если не ЦГО
```

---

## Известные проблемы данных

| Проблема | Статус | Решение |
|---|---|---|
| CO/NO₂/NO/SO₂ Jul-Sep 2024 — переполнение (−10¹¹) | ✅ Исправлено | Фильтр `|emissions| > 1e9` в process_data.py |
| Пыль (PM) — значение −4×10³⁴ | ✅ Исправлено | Исключено из BROKEN_SUBSTANCES |
| `air_excess_ratio` в view_air_emissions — смешанный разделитель (запятая/точка) | ℹ️ Известно | При использовании: `toFloat64OrZero(replaceAll(x, ',', '.'))` |
| `volumetric_gas_consumption_m3_s` — смешанный str/float, запятая/точка | ✅ Исправлено | `_safe_float()` в process_fire_emissions() |
| СКО Севказэнерго: flow<0, turbidity зависла, pH=0 | ✅ Исключено | `WATER_BAD_ORGS` в process_water_emissions() |
| Карагандинская Рудник Саяк: pH=0 у 99.5% записей | ✅ Исключено | `WATER_BAD_REGIONS` |
| Мар-май 2024: калибровочный период сточных вод | ✅ Исключено | Фильтр `registered_at >= 2024-06-01` |
| ПЭК объекты с целыми координатами (51,71) — дефолт НБД СОС | ✅ Исправлено | Фильтр `lat == int(lat)` в parse_coords() |
| `total_by_substance` из SUM-CSV имел кумулятивные негативы | ✅ Исправлено | Пересчёт из очищенного monthly |

---

## TODO / Следующие шаги

- [ ] **Отходы** — подключить КГС waste данные (уже в kgs.json) к вкладке `panel-waste`
- [ ] **Слушания** — нет данных, нужен источник
- [x] **Выбросы в воду** — ✅ Подключены (764 204 строки, 19 орг., 7 регионов, pH тренды, топ источников)
- [x] **Факельные выбросы** — ✅ Подключены (1.27М строк, 2 орг., 6 факелов, ежемесячный тренд)
- [ ] **ПЭК историчность** — данные с 2023-11-15, подсветить на дашборде
- [ ] **view_air_emissions** — при получении агрегатов добавить блок "Коэффициент ПДК" на вкладке Выбросы
- [ ] **Казгидромет** — станции захардкожены, нужны реальные данные мониторинга

---

## Команды

```bash
# Перегенерировать все JSON
cd "/Users/alprasalam/Desktop/Кейс по экологии/eco-dashboard"
python3 scripts/process_data.py

# Задеплоить
vercel --prod
```

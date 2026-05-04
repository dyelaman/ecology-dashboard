# Eco Dashboard — МЭПР РК / Таза Казахстан

**Продакшн:** https://eco-dashboard-psi.vercel.app  
**Проект:** /Users/alprasalam/Desktop/Кейс по экологии/eco-dashboard  
**Деплой:** `cd "/Users/alprasalam/Desktop/Кейс по экологии/eco-dashboard" && vercel --prod`  
**Данные:** `cd "/Users/alprasalam/Desktop/Кейс по экологии/eco-dashboard" && python3 scripts/process_data.py`

---

## Архитектура

- **`public/index.html`** — единственный SPA-файл (~3500+ строк), Vanilla JS + Chart.js 4.4.1 + Leaflet.js 1.9.4
- **`api/proxy.js`** — Vercel serverless: RSS-прокси (allowlist доменов) + Anthropic API proxy
- **`api/social.js`** — Vercel serverless: скрапинг Telegram t.me/s (каналы: kozachkow, tengrinews)
- **`scripts/process_data.py`** — обработка всех CSV → JSON в `public/data/`
- **`public/data/`** — генерируемые JSON (не редактировать вручную)
- **`public/kaz.geojson`** — упрощённые полигоны регионов РК

## Вкладки дашборда

| ID | Название | Статус данных |
|---|---|---|
| `panel-main` | Главная | ✅ Реальные данные + полная аналитика по обращениям |
| `panel-hearings` | Социальное напряжение | ✅ Реальные данные (eObr — индекс напряжённости, регионы, тренды) |
| `panel-news` | Новости | ✅ Реальный парсинг RSS + Telegram |
| `panel-emissions` | Выбросы | ✅ Реальные данные (НБД СОС) |
| `panel-waste` | Отходы | ⚠️ Заглушки |
| `panel-kgs` | 🛰 КГС | ✅ Реальные данные (спутниковый мониторинг) |
| `panel-appeals` | (скрыт) | display:none — данные перенесены на Главную |

**Порядок вкладок:** Главная → Социальное напряжение → Новости → Выбросы → Отходы → КГС

---

## Главная страница (panel-main)

### Блоки сверху вниз

1. **KPI-сетка** — Обращений, iKomek, Исполнено, В работе, Просрочено, Повторные, Перенаправлено, Перенапр. частично
2. **КГС-инсайты** (4 карточки) — Самозахваты, Свалки, Рубки, Горные работы
3. **2-колонки:** Карта (Leaflet) | НБД СОС мониторинг
4. **Аналитика по обращениям** (4 чарта):
   - `c3` — Категории обращений (drill-down: категория → вопрос → подвопрос)
   - `cAppSub` — контекст-зависимый: характер вопроса / подкатегории
   - `cAppType` — Тип обращений
   - `cAppChar` — Характер вопроса iKomek
5. **3 чарта:** Топ регионов (`c12`) | Просрочено по регионам (`cRegLate`) | Топ исполнителей (`envPlants`)
6. **Таблица "Общая информация по обращениям"** (`#appTblPreview`) — 1944 строк, пагинация

### Таблица preview — колонки (в порядке выгрузки)

| # | Поле | JS-ключ |
|---|---|---|
| 1 | Рег. номер | `reg_number` |
| 2 | Дата подачи | `created_date` |
| 3 | Повтор | `is_duplicate` |
| 4 | Перенаправлено | `is_forward` |
| 5 | Перенапр. частично | `is_ext_forward` |
| 6 | Тип | `type_name_ru` |
| 7 | Заявитель | `applicant_type` |
| 8 | Категория | `issue_category_name_ru` |
| 9 | Вопрос | `issue` |
| 10 | Подвопрос | `subissue` |
| 11 | Регион | `region` |
| 12 | Район | `raion` |
| 13 | Исполнитель | `org_name` |
| 14 | Статус | `current_working_state` |
| 15 | Просрочка | `status_overdue` |
| 16 | Срок | `deadline` |
| 17 | Дата закрытия | `finish_dt` |

### Фильтры таблицы preview

- `prvSearch`, `prvType`, `prvStatus`, `prvCat`, `prvIss`, `prvSub`, `prvRegion` — все `width:130px`
- Чекбоксы: `prvDup` (Повторные), `prvFwd` (Перенаправлено)
- Кнопка **✕ Сбросить** → вызывает `resetPrvFilters()`

---

## Кросс-фильтрация (drill-down)

### Глобальные фильтры (fbar)

```
gYear, gReg, gType, gCatF, gIssueF, gSubF, gCGO, gMIO, gStatus
```
Все `.fbar select` имеют `width:140px` (CSS).  
Клик по чарту → устанавливает значение селекта → `onGlobalFilter()` → `_rechartOnFilter()`

### Данные кросс-фильтрации

- `_CROSS` — кросс-таблица по категориям: `{cat: {total, done, work, late, dup, fwd, issues[], by_region{}, top_orgs[]}}`
- `_ISSUE_CROSS` — кросс по категория×вопрос: `{cat||iss: {total, done, work, late, subs[]}}`
- Генерируются в `process_data.py` → `summary.json` → загружаются в JS

### JS-функции кросс-фильтрации

```js
_renderC3()        // drill-down чарт: все категории → вопросы → подвопросы
_renderCAppSub()   // контекст-зависимый чарт (subissues или issues)
_rechartOnFilter() // мастер-обновление: вызывает оба выше + c12 + cRegLate + envPlants + KPIs
resetPrvFilters()  // сброс всех локальных фильтров таблицы preview
```

---

## Источники данных

### Обращения (eObr)
- **Файл:** `/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по обращениям с 2021-07-01/ecology_eobr_subissues.csv`
- **Записей:** 352,641 | **С:** 2021-07-01
- **Выход:** `public/data/summary.json` (appeals + cross + issue_cross) + `public/data/preview.json` (1944 строк, стратифицированная выборка)

### iKomek
- **Файл:** `/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по ikomek с 2019-04-01/ecology_ikomek.csv`
- **Записей:** 16,103 | **С:** 2019-04-01
- **Выход:** `public/data/summary.json` (ikomek)

### ПЭК объекты (НБД СОС)
- **Файл:** `/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_pekobject.csv`
- **Записей:** 55,483 → 5,478 активных с координатами (кат.1: 941, кат.2: 4,529, кат.3: 8)
- **Историчность:** с 2023-11-15 (нужно подсветить на дашборде — TODO)
- **Выход:** `public/data/pek_objects.json`

### Аварийные выбросы (НБД СОС)
- **Файл:** `/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/ecology_emergency_emission.csv`
- **Записей:** 993,000 → 6,720 инцидентов (ReportId) | **С:** 2024-01
- **Выход:** `public/data/emergency_emissions.json` (4,739 точек для карты)

### Выбросы в воздух — замеры (НБД СОС)
- **Полная выгрузка:** 25 млн записей (агрегированные запросы выполнены)
- **Агрегаты:**
  - Месячный тренд: `ecology_air_emission_measurement_data_month_substances.csv`
  - Топ источников: `ecology_air_emission_measurement_data_top_devices_sum.csv`
  - Итого по веществам: `ecology_air_emission_measurement_data_SUM_substances.csv`
- **Топ вещества:** CO, NO₂, SO₂, NO, Пыль (после фильтрации отрицательных значений)
- **Выход:** `public/data/air_emissions.json`

### Аварийные выбросы в воздух (НБД СОС)
- **Полная выгрузка:** 80 млн записей (агрегированные запросы выполнены)
- **Агрегаты:**
  - Факт vs лимит: `ecology_emergency_emission_air_fact_vs_limit.csv`
  - Месячный тренд: `ecology_emergency_emission_air_month_fact_limit.csv`
  - Месячный тренд по веществам: `ecology_air_emission_emergency_measurement_data_month_substances.csv`
- **Превышений:** 5,289 | Факт/Лимит: 55%
- **Выход:** включено в `public/data/air_emissions.json`

### КГС — Спутниковый мониторинг (Казахстан Гарыш Сапары)
- **Леса:** `get_forest_detailed.csv` — 24,685 рубок (316 незаконных, 257.6 га)
- **Земли:** `get_land_seizure_detailed.csv` — 5,323 самозахватов (2024–2025)
- **Недра:** `get_nedra_detailed.csv` — 12,421 карьеров, 26,488 га (2021–2025)
- **Отходы:** `get_waste_detailed.csv` — 50,122 несанкц. свалок, 45% утилизировано
- **Выход:** `public/data/kgs.json` (~6 KB)

### Факельные выбросы (НБД СОС)
- **Файл:** `view_fire_emissions_full.csv`
- **Записей:** 1,269,839 → 207,355 уникальных замеров | **Период:** 2024-05 → 2026-04
- **Организаций:** 2 (NCOC Кашаган — Атырауская, GAS PROCESSING CO — Актюбинская)
- **Вещества:** H₂S, COS, CS₂, меркаптаны, NO
- **Выход:** `public/data/fire_emissions.json` (2 KB)

### Сточные воды (НБД СОС)
- **Файл:** `view_water_emissions_full.csv`
- **Записей:** 1,163,285 → **764,204 после очистки** | **Период:** 2024-06 → 2026-04
- **Организаций:** 19 | **Источников:** 31 | **Регионов:** 7
- **pH в норме (6–9):** 63% | **Щелочная среда (>9):** ~35% (типично для горнодобычи)
- **Исключены:** Карагандинская обл. (датчик pH=0), АО Севказэнерго ПТЭЦ-2 (все датчики неисправны)
- **Выход:** `public/data/water_emissions.json` (4 KB)

### Все CSV агрегаты лежат в:
`/Users/alprasalam/Desktop/Кейс по экологии/выгрузки по НБД СОС/`

**Методология всех агрегаций:** см. `AGGREGATIONS.md` (для согласования с госорганом)

---

## Карта (Leaflet)

Атрибуция: `🇰🇿 Таза Казахстан`

Слои на главной карте (`mapMain`):
| Слой | ID чекбокса | Цвет | Данные |
|---|---|---|---|
| Обращения (хороплет) | `mlyrAppeals` | зелёный градиент | REAL_ECO |
| Казгидромет | `mlyrHydro` | фиолетовый | KAZHYDROMET_MAIN (константа) |
| ПЭК объекты | `mlyrPek` | красный/оранжевый | /data/pek_objects.json |
| Аварийные выбросы | `mlyrEmerg` | жёлтый | /data/emergency_emissions.json |
| Свалки КГС | `mlyrWaste` | красный | /data/kgs.json |
| Самозахваты | `mlyrLand` | оранжевый | /data/kgs.json |
| Карьеры | `mlyrNedra` | фиолетовый | /data/kgs.json |
| Факелы | `mlyrFire` | оранжево-красный | /data/kgs.json |

---

## Новости

- **RSS-источники:** tengrinews.kz, kapital.kz, 24.kz, kursiv.kz, primeminister.kz, gov.kz
- **Telegram:** @kozachkow (Kozachkov Offside), @tengrinews (через api/social.js)
- **Кеш:** localStorage, 30 мин TTL

---

## TODO / Следующие шаги

- [ ] Подсветить историчность ПЭК объектов с 2023-11-15 на карте/вкладке
- [ ] Выбросы в воздух: получить полные 25 млн строк (или SQL-агрегаты) и обновить
- [ ] Выбросы в воду — данные ещё не получены
- [ ] Вкладка "Отходы" — заглушки, нужны реальные данные
- [ ] Вкладка "Социальное напряжение" — заглушки, нужны реальные данные
- [ ] Протестировать кросс-фильтрацию в браузере (drill-down c3, cAppSub, KPI)

---

## Ключевые ID элементов

```
# KPI главной
kpiEco, kpiIkom, kpiDone, kpiWork, kpiLate, kpiDup, kpiFwd, kpiExtFwd

# НБД СОС (на главной, справа от карты)
envPekTotal, envPekCat1, envPekCat2
envEmergCount, envEmerg2026, envEmerg2025, envEmergDelta
emStatPek, emStatEmerg, emStatExceed, emStatRatio, emStatSrc

# Чарты главной
c3, cAppSub, cAppType, cAppChar   // аналитика обращений
c12, cRegLate, envPlants           // регионы + исполнители
c3Title, c3Breadcrumb, cAppSubTitle

# Карта
mapMain, mlyrAppeals, mlyrHydro, mlyrPek, mlyrEmerg, mlyrWaste, mlyrLand, mlyrNedra, mlyrFire

# Таблица preview
appTblPreview, prvSearch, prvType, prvStatus, prvCat, prvIss, prvSub, prvRegion
prvDup, prvFwd, prvCount, prvPageInfo
```

## Глобальные JS-переменные

```js
_DATA            // { summary, preview, air } — загружается async
_CROSS           // кросс-таблица по категориям (из summary.json)
_ISSUE_CROSS     // кросс по категория×вопрос (из summary.json)
_HIERARCHY       // иерархия категорий для каскадных фильтров
_appAllRows      // нормализованные строки preview.json (1944 записи)
_prvFiltered     // отфильтрованные строки после filterPrvTable()
_prvPage         // текущая страница пагинации
REAL_ECO         // данные по регионам (перезаписывается из summary.json)
_emChartC5/C6/Types/Season  // инстансы Chart.js вкладки Выбросы
mapMainInst, geoLayerMain, hydroLayerMain, pekLayerMain, emergLayerMain
allNews          // все новости после фильтрации
```

# Методология агрегации данных — Eco Dashboard
## НБД СОС (Национальный банк данных состояния окружающей среды)

**Скрипт обработки:** `scripts/process_data.py`  
**Дата последней генерации:** см. поле `generated` в `public/data/summary.json`  
**Все агрегации воспроизводимы** — запуск `python3 scripts/process_data.py` пересчитывает все JSON из исходных CSV.

---

## 1. ОБРАЩЕНИЯ ГРАЖДАН (eObr)

**Источник:** `ecology_eobr_subissues.csv`  
**Записей:** 352,641 | **Период:** с 01.07.2021

### 1.1 Нормализация статусов

| Исходное значение CSV | Внутренний код | Отображение |
|---|---|---|
| Завершено | `done` | Исполнено |
| Завершено с просрочкой | `latedone` | Исполнено (с просрочкой) |
| В работе | `work` | В работе |
| В работе с просрочкой | `late` | Просрочено |

### 1.2 KPI — сводные показатели

| Показатель | Формула | Результат |
|---|---|---|
| Всего обращений | `COUNT(*)` | 352,641 |
| Исполнено | `COUNT WHERE статус IN (done, latedone)` | 346,299 |
| % исполнения | `исполнено / всего × 100` | 98% |
| В работе | `COUNT WHERE статус = work` | 5,457 |
| Просрочено | `COUNT WHERE статус = late` | 885 |
| Повторные | `COUNT WHERE is_duplicate IN (Y, 1, true, да)` | 9,331 |
| Перенаправлено | `COUNT WHERE is_forward IN (Y, 1, true, да)` | 72,837 |
| Перенапр. частично | `COUNT WHERE is_ext_forward IN (Y, 1, true, да)` | 2,715 |

### 1.3 Чарт: Категории обращений (c3 — drill-down)

**Уровень 1 — все категории:**
```
GROUP BY category → COUNT(*) → TOP-8 по убыванию
```
Применено сокращение длинных названий (CATEGORY_SHORT в скрипте).

**Уровень 2 — характер вопроса (после выбора категории):**
```
FILTER WHERE category = выбранная
GROUP BY issue → COUNT(*), COUNT(WHERE статус=late)
TOP-15 по убыванию
```

**Уровень 3 — подкатегория (после выбора характера вопроса):**
```
FILTER WHERE category = X AND issue = Y
GROUP BY subissue → COUNT(*), COUNT(WHERE статус=late)
TOP-15 по убыванию
```

### 1.4 Чарт: Регионы (c12)

```
GROUP BY region → COUNT(*), COUNT(late), COUNT(work), COUNT(done)
Сортировка: по убыванию COUNT(*)
```

При активном фильтре по категории:
```
FILTER WHERE category = выбранная → те же агрегации
```

### 1.5 Чарт: Просрочено по регионам (cRegLate)

```
FILTER WHERE статус IN (late, latedone)
GROUP BY region → COUNT(*)
TOP-10 по убыванию
```

### 1.6 Блок: Топ исполнителей (envPlants)

```
GROUP BY org_name → COUNT(*)
TOP-10 по убыванию
```

При активном фильтре по категории:
```
FILTER WHERE category = выбранная → GROUP BY org_name → TOP-10
```

### 1.7 Таблица: Общая информация (preview)

**Стратифицированная выборка 2,000 записей:**
- Просроченные (late + latedone): до 800 записей, новейшие первыми
- В работе (work): до 400 записей, новейшие первыми
- Завершено (done): до 400 записей, новейшие первыми
- Остаток: до 400 записей, новейшие первыми

**Поля в таблице** (в порядке выгрузки):
`reg_number, created_date, is_duplicate, is_forward, is_ext_forward, type_name_ru, applicant_type, issue_category_name_ru, issue, subissue, region, raion, org_name, current_working_state, status_overdue, deadline, finish_dt`

---

## 2. iKOMEK (колл-центр)

**Источник:** `ecology_ikomek.csv`  
**Записей:** 16,103 | **Период:** с 01.04.2019

### 2.1 Чарт: Характер вопроса iKomek (cAppChar)

```
GROUP BY character → COUNT(*)
```
Нормализация дублей: "Использование природно-сырьевых ресурсов, экология" и "ЭКОЛОГИЯ" → "Экология и природные ресурсы".

### 2.2 Месячный тренд iKomek

```
GROUP BY year, month → COUNT(*)
Сортировка: по year, month ASC
```

---

## 3. ПЭК ОБЪЕКТЫ (НБД СОС)

**Источник:** `ecology_pekobject.csv`  
**Записей:** 55,483 → **Активных с координатами:** 5,478  
**Историчность данных:** с 2023-11-15

### 3.1 Фильтрация активных объектов

```
FILTER WHERE is_deleted ≠ true AND inactive ≠ true
→ 15,013 активных
```

### 3.2 Валидация координат

Координаты хранятся в JSON-поле `coords`. Отбрасываются:
- Целочисленные координаты (дефолтное значение [51, 71] — не введены)
- За пределами Казахстана: широта вне [40–56], долгота вне [49–88]

Результат: **5,478 объектов** с валидными координатами.

### 3.3 KPI по категориям ПЭК

| Категория | Кол-во | Описание |
|---|---|---|
| 1-я категория | 941 | Объекты высокой экологической нагрузки |
| 2-я категория | 4,529 | Объекты средней нагрузки |
| 3-я категория | 8 | Объекты малой нагрузки |

---

## 4. АВАРИЙНЫЕ ВЫБРОСЫ (НБД СОС)

**Источник:** `ecology_emergency_emission.csv`  
**Записей:** 993,000 строк → **Инцидентов (ReportId):** 6,720  
**Период:** с января 2024

### 4.1 Агрегация инцидентов

Одна строка = один замер в рамках инцидента. Группировка по `ReportId`:

```
GROUP BY ReportId →
  date = MIN(CreateDate)
  is_closed = ANY(IsClosed = true)
  lat/lng = FIRST(Lat, Lng)
  pollutants = UNIQUE(NameRu)[:5]
  actual_vol = SUM(ActualVolume)
  limit_vol = SUM(LimitedVolume)
```

### 4.2 Карта аварийных выбросов

Из 6,720 инцидентов отобраны **4,739** с валидными координатами:
- Широта в [40–56], долгота в [49–88]
- Не целочисленные координаты

### 4.3 KPI аварийных выбросов

| Показатель | Значение |
|---|---|
| Всего инцидентов | 6,720 |
| Закрыто | 178 |
| 2024 год | 2,483 |
| 2025 год | 3,089 |
| 2026 (янв–апр) | 1,148 |
| 2025 (янв–апр) | 1,419 |
| Δ год к году | −271 (−19%) |

---

## 5. ВЫБРОСЫ В ВОЗДУХ — ПЛАНОВЫЙ МОНИТОРИНГ (НБД СОС)

**Источники:**
- `ecology_air_emission_measurement_data_month_substances.csv` — месячные агрегаты
- `ecology_air_emission_measurement_data_top_devices_sum.csv` — топ источников
- `ecology_emission_limits_100_rows.csv` — лимиты (справочно)

**Полная выборка:** ~25 млн строк (SQL-агрегация на стороне НБД СОС)

### 5.1 Чарт: Месячный тренд по веществам

**Фильтрация аномалий:**
- Исключено вещество `Пыль (взвешенные частицы)` — значения ~10³⁴ (переполнение типа данных в НБД СОС)
- Исключены месяцы с `|total_emissions| > 1×10⁹` (аномалия Jul–Sep 2024 для CO/NO₂/NO/SO₂)
- Исключены строки с `total_emissions ≤ 0`

```
FILTER аномалии → GROUP BY substance, month → SUM(total_emissions)
Топ-5 веществ по суммарному объёму за весь период
```

**Топ-5 веществ:** CO, NO₂, SO₂, NO, Пыль

### 5.2 Чарт: Топ источников выбросов

```
FILTER WHERE device_id ≠ 1 (тест) AND total_emissions > 0
SORT BY total_emissions DESC → TOP-15
```

### 5.3 KPI по веществам (итоговая таблица)

Пересчитывается из очищенных месячных данных (не из SUM CSV, т.к. там содержатся испорченные суммы за аномальные месяцы):

```
GROUP BY substance →
  total = SUM(total_emissions)
  measurements = COUNT(months)
  avg = total / measurements
```

---

## 6. АВАРИЙНЫЕ ВЫБРОСЫ В ВОЗДУХ (НБД СОС)

**Источники:**
- `ecology_emergency_emission_air_fact_vs_limit.csv` — факт vs лимит по загрязнителю
- `ecology_emergency_emission_air_month_fact_limit.csv` — месячный тренд
- `ecology_air_emission_emergency_measurement_data_month_substances.csv` — по веществам

**Полная выборка:** ~80 млн строк (SQL-агрегация на стороне НБД СОС)

### 6.1 Чарт: Факт vs Лимит по загрязнителям

```
SORT BY total_actual DESC → TOP-20
Показатели: total_actual, total_limit, measurements, exceedances
```

| Сводно | Значение |
|---|---|
| Всего превышений | 5,289 |
| Суммарный факт (усл. ед.) | 52,319,740 |
| Суммарный лимит (усл. ед.) | 95,096,466 |
| % использования лимита | 55% |

### 6.2 Чарт: Месячный тренд аварийных выбросов

```
GROUP BY month (YYYY-MM) →
  total_actual = SUM(actual)
  total_limit = SUM(limit)
  exceedances = COUNT(WHERE actual > limit)
SORT BY month ASC
```

---

## 7. ФАКЕЛЬНЫЕ ВЫБРОСЫ (НБД СОС)

**Источник:** `view_fire_emissions_full.csv`  
**Записей:** 1,269,839 | **Период:** 2024-05 → 2026-04

### 7.1 Структура данных

Каждая строка = один замер одного вещества на одном факеле в один момент времени.
Несколько веществ на одном замере имеют **одинаковое значение** `volumetric_gas_consumption_m3_s` (объёмный расход газа общий на источник).

**Организации (2):**
- NCOC (Кашаган) — Атырауская область — 6 факелов
- GAS PROCESSING COMPANY — Актюбинская область

### 7.2 Дедупликация для агрегации объёмов

```
DEDUPLICATE BY (registered_at, organization_name, source_name)
→ 207,355 уникальных замеров (из 1,269,839 строк)
FILTER WHERE vol > 0
```

### 7.3 Чарт: Месячный тренд объёма сжигания

```
GROUP BY month (YYYY-MM) →
  avg_flow = MEAN(vol) × 3600  [перевод м³/с → м³/ч]
  max_flow = MAX(vol) × 3600
  readings = COUNT(*)
```

### 7.4 Чарт: По организациям (месячный)

```
GROUP BY organization, month → MEAN(vol) × 3600
```

### 7.5 Чарт: Состав газа (по веществам)

```
GROUP BY emission_type → SUM(volumetric_gas_consumption_m3_s)
SORT BY DESC
```

Вещества: H₂S (сероводород), COS (углерод оксид-сульфид), CS₂ (сероуглерод), меркаптаны, NO.

---

## 8. СТОЧНЫЕ ВОДЫ (НБД СОС)

**Источник:** `view_water_emissions_full.csv`  
**Записей:** 1,163,285 | **Период:** с 2024-03  
**После очистки:** 764,204 записей

### 8.1 Очистка данных (исключения)

Исключены из расчётов следующие данные с обоснованием:

| Исключение | Причина |
|---|---|
| Карагандинская область (Рудник Саяк) | pH = 0 в 99.5% случаев — датчик pH не откалиброван/не работал |
| АО "Севказэнерго" ПТЭЦ-2 | flow < 0, turbidity застряла на 3400 NTU, pH = 0 — все датчики неисправны |
| Строки с `flow ≤ 0` | Нулевой/отрицательный поток = датчик не пишет или обратный ток |
| Строки с `pH = 0` или `pH > 14` | Нулевой pH = датчик не откалиброван |
| Строки с `turbidity < 0` | Физически невозможное значение |
| Период до 2024-06-01 | Период калибровки: pH ≈ 0, минимальный поток |

### 8.2 Нормы качества воды (ПДК/ПДС)

Использованные пороги для флагирования нарушений:

| Параметр | Норма | Источник |
|---|---|---|
| pH | 6.0 – 9.0 | Нормы РК для сточных вод в водные объекты |
| Мутность | ≤ 100 NTU | Ориентировочный порог |

### 8.3 KPI сточных вод

| Показатель | Значение |
|---|---|
| Чистых замеров | 764,204 |
| Организаций | 19 |
| Источников сброса | 31 |
| Регионов | 7 (ВКО, Костанайская, Павлодарская, Карагандинская очищена, Актюбинская, Атырауская, Жетысуская) |
| pH в норме (6–9) | 63% |
| pH кислая среда (< 6) | ~2% |
| pH щелочная среда (> 9) | ~35% |

> **Примечание:** высокая доля щелочной среды типична для горнодобывающих предприятий (Казцинк, Ульбинский МЗ) — связана с процессами обогащения руды.

### 8.4 Чарт: Месячный тренд (три параметра)

```
GROUP BY month (YYYY-MM) →
  flow_mean = MEAN(waste_water_flow_m3_h)   [м³/ч]
  ph_mean = MEAN(ph)
  turbidity_mean = MEAN(turbidity_ntu)      [NTU]
```

### 8.5 Чарт/Таблица: По организациям

```
GROUP BY organization_name →
  flow_mean = MEAN(flow)          [м³/ч]
  ph_mean = MEAN(ph)
  ph_normal_pct = COUNT(6≤pH≤9) / COUNT(*) × 100
TOP-12 по flow_mean DESC
```

### 8.6 Чарт: По регионам

```
GROUP BY region →
  flow_mean = MEAN(flow)
  ph_mean = MEAN(ph)
  ph_normal_pct = COUNT(6≤pH≤9) / COUNT(*) × 100
  turb_mean = MEAN(turbidity)
  records = COUNT(*)
SORT BY flow_mean DESC
```

---

## 9. КГС — СПУТНИКОВЫЙ МОНИТОРИНГ (Казахстан Гарыш Сапары)

### 9.1 Леса

**Источник:** `get_forest_detailed.csv` | **Записей:** 24,685

```
Всего рубок: 24,685
  Законных:   24,369 (38,011 га)
  Незаконных:    316 (257.6 га)
```

**Чарт: По годам**
```
GROUP BY god (год) →
  legal = COUNT(WHERE is_legal = "Законная")
  illegal = COUNT(WHERE is_legal = "Незаконная")
  area_legal = SUM(ploshad WHERE legal)
  area_illegal = SUM(ploshad WHERE illegal)
```

**Чарт: Топ регионов по незаконным рубкам**
```
FILTER WHERE is_legal = "Незаконная"
GROUP BY region → COUNT(*) → TOP-8
```

### 9.2 Земли (самозахваты)

**Источник:** `get_land_seizure_detailed.csv` | **Записей:** 5,323

```
GROUP BY result (тип объекта) → COUNT(*) → TOP-8
GROUP BY city → COUNT(*) → TOP-10
GROUP BY god → COUNT(*)
```

### 9.3 Недра (карьеры, горные работы)

**Источник:** `get_nedra_detailed.csv` | **Записей:** 12,421 | **Площадь:** 26,488 га

```
GROUP BY mining_class → COUNT(*) → TOP-6
GROUP BY region → COUNT(*) → TOP-8
GROUP BY god →
  count = COUNT(*)
  area_ha = SUM(area)
```

### 9.4 Отходы (несанкционированные свалки)

**Источник:** `get_waste_detailed.csv` | **Записей:** 50,122

| Статус | Кол-во |
|---|---|
| Утилизирован | 22,684 (45%) |
| Не утилизирован | 7,677 (15%) |
| Прочие статусы | ~27,761 (40%) |

```
GROUP BY statustext → COUNT(*) → TOP-6
GROUP BY vid_othod (вид отхода) → COUNT(*) → TOP-6
GROUP BY region → COUNT(*) → TOP-10
GROUP BY god →
  total = COUNT(*)
  cleared = COUNT(WHERE status = "Утилизирован")
```

---

## 10. ВЫХОДНЫЕ JSON-ФАЙЛЫ

| Файл | Размер | Содержимое |
|---|---|---|
| `public/data/summary.json` | 210 KB | Обращения, iKomek, аварийные выбросы (сводки) |
| `public/data/preview.json` | 2,355 KB | 1,944 строк обращений (стратифицированная выборка) |
| `public/data/pek_objects.json` | 2,096 KB | 5,478 объектов ПЭК с координатами |
| `public/data/emergency_emissions.json` | 1,582 KB | 4,739 точек аварийных выбросов для карты |
| `public/data/air_emissions.json` | 13 KB | Выбросы в воздух: тренды, топ источников, аварийные |
| `public/data/kgs.json` | 6 KB | КГС: лес, земля, недра, отходы |
| `public/data/fire_emissions.json` | 2 KB | Факельные выбросы |
| `public/data/water_emissions.json` | 4 KB | Сточные воды |

---

## 11. ВОСПРОИЗВОДИМОСТЬ И ПРОВЕРКА

Все агрегации воспроизводимы из исходных CSV. Для проверки конкретного показателя:

```bash
# Пример: проверить кол-во просроченных обращений
python3 -c "
import pandas as pd
df = pd.read_csv('/путь/к/ecology_eobr_subissues.csv')
late = df['current_working_state'].isin(['В работе с просрочкой'])
print(f'Просрочено: {late.sum():,}')
"

# Пример: проверить нарушения pH в сточных водах
python3 -c "
import pandas as pd
df = pd.read_csv('/путь/к/view_water_emissions_full.csv')
df['ph'] = pd.to_numeric(df['ph'], errors='coerce')
# После применения фильтров очистки (flow>0, ph>0, ph<=14, дата>=2024-06)
clean = df[(df['ph']>0)&(df['ph']<=14)&(df['waste_water_flow_m3_h'].apply(lambda x: float(str(x).replace(',','.')) if str(x).replace(',','').replace('.','').lstrip('-').isdigit() else 0)>0)]
print(f'pH в норме: {((clean.ph>=6)&(clean.ph<=9)).mean()*100:.1f}%')
"
```

**Скрипт генерации:** `scripts/process_data.py`  
**Запуск:** `cd eco-dashboard && python3 scripts/process_data.py`  
**Время выполнения:** ~3-5 минут (чтение ~3 GB CSV-файлов)

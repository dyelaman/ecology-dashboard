# CONTEXT — Eco Dashboard (МЭПР РК · Таза Казахстан)

> Файл состояния проекта. Обновляется в конце каждой сессии Claude Code.
> Источник правды о том, на чём остановились. Не держим сессию открытой —
> вместо этого читаем этот файл при старте новой.

**Последнее обновление:** 2026-07-08
**Производство:** <https://taza-eco.vercel.app>
**Репозиторий:** <https://github.com/dyelaman/ecology-dashboard>
**Корень проекта:** `/Users/alprasalam/Desktop/проекты/Кейс по экологии/eco-dashboard`
**Корень данных:** `/Users/alprasalam/Desktop/проекты/Кейс по экологии/`  (переименовано из `Вайбкод кейсы/`)

---

## 1. Архитектура и стек

### Язык / фреймворк
- **Vanilla JS SPA** в одном файле `public/index.html` (~12 000 строк), без bundler'а
- **Vercel serverless** (`api/proxy.js`, `api/social.js`) для прокси и Anthropic API
- **Python 3** для оффлайн-агрегации CSV → JSON

### Ключевые библиотеки (CDN)
- `Chart.js 4.4.1` + `chartjs-plugin-datalabels 2.2.0` + `chartjs-plugin-zoom 2.0.1`
- `Leaflet 1.9.4` + `leaflet.heat 0.2.0` + `leaflet.markercluster 1.5.3`
- `flatpickr 4.6.13` + l10n/ru
- `PapaParse 5.4.1`

### База данных / хранилище
- Нет БД. Всё в **статичных JSON в `public/data/`**:
  - `summary.json` (~3.3 МБ) — агрегаты по обращениям
  - `preview.json` (~2.5 МБ) — стратифицированная выборка таблицы обращений
  - `appeals_compact.json` (~11 МБ) — **343 228** эко-обращений per-row, int-кодированные (период **23.07.2021 → 07.07.2026**, обновлено 08.07.2026)
  - `ikomek_compact.json` (~1.5 МБ) — **86 687** звонков iKomek per-call (была урезанная эко-выборка 16 103, теперь полная выгрузка komek_total_data, период **18.03.2019 → 02.07.2026**)
  - `taza_kz.json`, `taza_compact.json` (~1.7 МБ), `taza_table.json` (~22 МБ) — **48 375 заявок** (20.06.2024 → 07.07.2026)
  - `nbd_facts.json` (~6.8 МБ, **schema v2**) — расширенная структура: organizations[], sources[], air/water/fire (facts+aggregates+incidents), coverage + LEGACY-схема facts[] для backward-compat
  - `nbd_2025.json` (~23 КБ) — легаси-формат для существующего UI
  - `pek_objects.json` (~2 МБ), `kgs_facts.json` (~5 МБ), `kgs.json` (~7 КБ), `kgs_map.json`
  - `accumulation_waste.json`, `fire_emissions.json`, `water_emissions.json`, `air_emissions.json`
  - `border_regions.geojson` — реальные границы 20 регионов

### Как запускать локально
```bash
cd "/Users/alprasalam/Desktop/проекты/Кейс по экологии/eco-dashboard"
python3 -m http.server 8000 --directory public
# открыть http://localhost:8000
```
API-ручки (`/api/proxy`, `/api/social`) локально работают только через `vercel dev`.

### Как деплоить
```bash
cd "/Users/alprasalam/Desktop/проекты/Кейс по экологии/eco-dashboard"
git push origin main
URL=$(vercel --prod 2>&1 | grep -oE "https://taza-[a-z0-9-]+\.vercel\.app" | head -1)
vercel alias set "$URL" taza-eco.vercel.app
```

### Как тестировать
- Нет unit/integration suite. Smoke-проверки:
```bash
# JS-syntax inline скриптов
python3 -c "
import re
html=open('public/index.html',encoding='utf-8').read()
scripts=re.findall(r'<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>', html)
open('/tmp/_combined.mjs','w').write('\n;//---\n'.join(scripts))" && node --check /tmp/_combined.mjs
```
- Offline-проверка контрольных чисел perform через прямое чтение JSON в Python — используется в коммитах для верификации перед деплоем.

### Структура проекта
```
eco-dashboard/
├── public/
│   ├── index.html              # SPA — единственный исходник UI (~12 000 строк)
│   ├── border_regions.geojson  # реальные полигоны 20 регионов (3.2 МБ)
│   ├── kaz.geojson             # старые упрощённые прямоугольники регионов
│   └── data/                   # все статичные агрегаты + per-row датасеты
├── api/
│   ├── proxy.js                # RSS/HTML proxy + Anthropic API proxy
│   └── social.js               # Telegram t.me/s/ scraper
├── scripts/
│   ├── process_data.py         # большой исторический pipeline
│   ├── process_nbd_2025.py     # ClickHouse-агрегаты НБД v2 (после 2026-06-05)
│   ├── process_ikomek.py       # per-call iKomek датасет
│   ├── process_kgs.py          # КГС спутниковый мониторинг
│   └── sql/
│       └── appeals_incremental.sql  # инкрементальная выгрузка еОбр из ClickHouse
├── CLAUDE.md                   # инструкции для Claude Code
├── CONTEXT.md                  # ⟵ ЭТОТ ФАЙЛ
├── NBD_DATA_SUMMARY.md         # выжимка по 5 свежим CSV НБД СОС
└── vercel.json
```

### Источники сырых данных (вне репо, все под `/проекты/Кейс по экологии/`)

- **Обращения eObr**: `выгрузки по обращениям с 2021-07-01/ecology_eobr_subissues.csv` (310 МБ, 363 582 уникальных appeal_id после дедупа 08.07)
  - Инкременты: `eobr_ecolog_5.06.2026.csv` (11 МБ), `eobr_ecolog_5.06-15.06.csv` (1.9 МБ), `eobr_ecolog_7.07.csv` (5.7 МБ) — все backtick-separated
  - Merge-логика (внешняя, не в скрипте): reorder колонок из incr → main порядок, `concat + drop_duplicates(subset=['appeal_id'], keep='first')` (incr побеждает)
  - Backups: `.bak_2026-04-21.csv`, `.bak_2026-06-05.csv`, `.bak_2026-06-15.csv`

- **iKomek**: `выгрузки по ikomek с 2019-04-01/komek_total_data d.csv` (18 МБ, 86 687 звонков, backtick separator)
  - Старая: `ecology_ikomek.csv` (3.8 МБ, 16 103 звонка — искусственно эко-урезанная)
  - Новая — **полная выгрузка** из системы 109 (много «БЛАГОУСТРОЙСТВА»)

- **Таза**: `выгрузки по Таза Казахстан/` — 5 CSV от 07.07.2026 (`202607071242…44`)

- **НБД СОС актуальное** (ClickHouse-агрегаты, обновлено 08.07.2026):
  - `mepr_nbdsos_air_emissions dd.csv` (2.8 МБ, 11 846 строк, до **2026-07**)
  - `mepr_nbdsos_water_emissions dd.csv` (164 КБ, 569 строк, до **2026-06**)
  - `mepr_nbdsos_fire_emissions d.csv` (160 КБ, 662 строки, до **2026-06**)
  - Разделитель: `` ` `` (backtick) — в июньских версиях был `;`. Скрипт авто-детектит.
  - Справочники (без изменений): `ecology_organizations.csv` (81 орг), `ecology_emission_sources.csv` (242 источника)

- НБД СОС исторические: `выгрузки по НБД СОС/` (pekobject, emergency, accumulation, view_fire/water) — НЕ обновлены, последние данные апрель 2026
- КГС: `КГС/` (forest, land_seizure, nedra, waste) — НЕ обновлены

---

## 2. Текущий статус

Дашборд в проде, **6 вкладок рабочие**, источники привязаны, **multi-select cross-filter** на Обращениях, **тотальная кросс-фильтрация** через `applyTimeEngine` (single-pass через 344k обращений). **AI-блоки рекомендаций** на НБД и КГС с поименными нарушителями. **30-дневный архив новостей** с 11 тематическими тегами и аналитикой E+F (новости ↔ обращения). i18n RU/KZ базовый.

**Финальные «звёздные» фичи для презентации министерству:**
- 🤖 ИИ-рекомендации НБД (5 секций × 3 среды) — Павлодарский нефтехим 99.3% × 6 веществ, overflow 10³⁸ на АлЭС ТЭЦ-1
- 🤖 ИИ-рекомендации КГС (4 секции × 4 типа) — 3 лесхоза ВКО дают 28% незаконных рубок страны, Зерендинский + Бухар-Жырауский = 9% всех свалок в 2 районах
- 📡 Coverage блок НБД — 76/81 организаций активны, 39 silent с кликабельным переходом на Обращения
- 📊 Связка «новости ↔ обращения» в Соц.напряжении (блоки E/F) с auto-insight о слепых пятнах СМИ

---

## 3. Что уже сделано (последние ~40 коммитов, новые → старые)

**Июль 2026 — refresh 07-08.07 (пред-презентационный):**
- `3611a13` ui(nbd): явные единицы измерения во всех блоках вкладки НБД СОС (шт., мг/м³, г/с, м³/ч, °C, мкСм/см, pH, кг/м³)
- `49c4d53` data: refresh iKomek → 07.07 (полная выгрузка komek_total_data, 86 687 звонков вместо старых 16 103)
- `0d2d347` data: refresh НБД СОС агрегаты → 2026-07-01 (авто-детект separator `;`/`` ` ``)
- `fb0addf` data: refresh appeals 2026-06-15 → 2026-07-07 (+6 957 · дедуп 11 702 pre-existing дублей · 343 228 итого)
- `71c02e8` data: refresh Таза → 07.07 (+3 034 → 48 375)

**Финальный спринт (июнь 2026):**
- `071948c` AI-рекомендации КГС — поименные нарушители × 4 типа (forest/nedra/waste/land_seizure)
- `712b183` НБД: убран «ДЛЯ МИНИСТЕРСТВА» из заголовка ИИ-блока
- `8dede52` НБД: AI-рекомендации министерству — 5 секций × 3 среды (нарушители/тренды/региональные паттерны/сезонность/качество данных)
- `ea4ef3a` НБД: insight-баннер + auto-insights + period comparison + кликабельные silent-orgs
- `92c47cf` НБД: Coverage-блок вынесен над картой + переименован заголовок «🆕 Свежие данные» → «Сведения НБД СОС предоставленные МЭПР»
- `af16a9f` НБД: Coverage-блок в UI + legacy compat для `_loadNbdFacts`
- `88eb8d7` НБД pipeline v2 на ClickHouse-агрегатах + справочники + coverage (schema_v2 + legacy compat)
- `bf1abec` data: refresh appeals 2026-04-22 → 2026-06-05 (+13 562) — fix путей КГС в process_data.py
- `590d88d` Соц.напряжение: блоки E (топ тем) + F (не освещённые регионы) — связка новости↔обращения
- `7376450` News filter v2.6 — drop погода/поздравления/зарубеж + fix substring 'недр'
- `0e5ad5c` News: strict eco-filter + 11 тематических тегов + archive v2
- `d54c629` News: архив 30 дней в localStorage с дедупом по link/(src+head)
- `290b0bd` News: заменить 6 мёртвых RSS-источников (Tengrinews/Kapital/24kz/…) + динамический srcRow
- `0d107a6` SQL incremental fetch для обращений еОбр (с инструкцией)

**Большой спринт по Обращениям (май-июнь 2026):**
- `36585ba` Числовые подписи на Динамике + барах регионов
- `d9e6754` Multi-select popover виден сразу + полный rerender при reset
- `e2cd6d2` Click-toggle на карте/барах/исполнителях + multi-region highlight
- `9a72dd8` Мультивыбор (8 фильтров) с OR/AND-логикой и popover c чекбоксами
- `8f17eef` Тотальная кросс-фильтрация + drill-down + fix донат-биндингов + полный reset
- `5bf17f4` iKomek subpanel: полный per-call движок + 2 новых donut + hero-alert + fix двух багов
- `09c20cd` iKomek: per-call датасет → полноценная кросс-фильтрация kpiIkom

**Май 2026:**
- `af9031d` Подзаголовок шапки — все 6 интеграций
- `0be076e` Этап 1 i18n — словарь 130+ ключей RU/KZ, `setLang()` + `localStorage`
- `9911498` Е-Өтініш как источник аналитики; объединённый чарт `cDyn` с переключателем Год/Месяц/День

`git log --oneline | head -60` — для полного списка.

---

## 4. Что осталось сделать (TODO)

Приоритет сверху вниз:

1. ~~**Единицы измерения на чартах НБД**~~ ✅ **сделано 08.07.2026** (коммит `3611a13`)
   - `_NBD_UNIT.measUnit = 'шт.'` + `fieldUnits` по среде
   - KPI-карточки: явное «шт.» под числом
   - `_renderNbdClickList` — «зам.» справа
   - Monthly chart: Y-title «Количество замеров, шт.» + X-title «Месяц» + tooltip с «шт.»

2. **Short_names в bar-чартах НБД**
   - Сейчас `_renderNbdClickList` обрезает длинные имена через `nameMax`
   - В новой `nbd_facts.json` есть `organizations[].short` — нужно прокинуть через рендер
   - Длинные ТОО названия станут читаемыми («АО ЖГРЭС» вместо «АО Жамбылская ГРЭС им. Т.И. Батурова»)

3. **Fuzzy region/org matching** в NBD coverage
   - Сейчас silent=39 завышено из-за разницы написания («АО ЕвроАзиатская» vs «АО Евроазиатская»)
   - Реальное число silent — меньше, нужен fuzzy match через стемминг или Levenshtein

4. **Запросить обновления данных** (по результатам диагностики):
   - **КГС**: полная пере-выгрузка 4 файлов (forest/land_seizure/nedra/waste). Особенно `get_waste_detailed.csv` — 2025 год пуст.
   - **НБД СОС исторические**: refresh `ecology_pekobject.csv`, `ecology_emergency_emission.csv`, `accumulation_waste.csv` (последние данные 22-27 апреля 2026, сегодня 08.07).
   - **Fire аномалия резко усугубилась** (см. раздел 6): май 8.2M, июнь 3.3M вместо ~80K. Требуется срочный пересчёт `mepr_nbdsos_fire_emissions` за 2026-05 и 2026-06.
   - **Расшифровка** `get_rational.csv` (rational land use) — ждём от владельца данных что значит `area_ha`.

5. **i18n Этап 2** — машинный перевод динамического контента (тексты новостей, обращений, организаций)

6. **Pie/doughnut datalabels** — отключены из-за `RangeError` в ChartDataLabels. Изучить, починить или взять другой подход.

7. **iKomek подвкладка subpanel** — char-bar и cat-donut работают через локальные `_ikCharSel`/`_ikCatSel` (не пробрасываются в `_AC` — разные словари). Можно сделать fuzzy-map если будет смысл.

---

## 5. Ключевые решения и договорённости

| Решение | Причина |
|---|---|
| **Vanilla JS в одном `index.html`** | Прототип под показ министру, без шага сборки. Файл вырос до ~12 000 строк, но `grep` остаётся быстрым. |
| **Per-row int-encoded JSON (`*_compact.json`)** | Чистый JSON массивов поверх Int32. 344k обращений = 10 МБ raw / ~2 МБ gzip → миллисекундная фильтрация. |
| **Multi-select architecture** (`_mSel` Map<id,Set>) | 8 фильтров Обращений с OR внутри / AND между. Source of truth — `_mSel`, `<select>` синкается для backward-compat (0/1/2+ значений). Engine читает через `_mAllowedArr` Uint8Array → O(1) per row в hot loop 330k×n_filters. |
| **NBD pipeline v2** — ClickHouse-агрегаты вместо raw 4.8 ГБ | Время выполнения: 15 мин → 3 секунды. Размер данных: 4.8 ГБ → 2.5 МБ. Все нужные срезы (n_excess, avg/max/p95) уже посчитаны на стороне БД. |
| **nbd_facts.json schema_v2 + legacy compat** | Новая структура (organizations/sources/coverage/per-env aggregates) для AI-блоков НЕ ломает старый UI: top-level `schema`/`facts` сохранены для `_loadNbdFacts`/`getFilteredNbdFacts`. |
| **News archive в localStorage** (`eco_news_archive_v3`) | 30-дневный накопительный архив с merge+dedup по `link` или `src+head[0..80]`. TTL 30 дней, hard limit 5000 items. `ts` (Unix ms) рядом с `date` (dd.mm.yyyy). Старая запись побеждает новую при collision (честная дата). |
| **News filter v3** — 11 тегов с весами + 40+ стоп-паттернов | `_ecoAnalyze(head, text)`: strong-фразы (+3/+2), context-слова (+2/+1). Eco-relevant = sum ≥ 3. Стопы: иглесиас/опера/спорт/праздники/зарубеж/прогноз погоды/поздравл. Архив-ключ bumpается при изменении логики. |
| **AI-блоки на НБД и КГС** | Динамические рекомендации с конкретными именами нарушителей. Под каждый env/тип — отдельные секции (нарушители/тренды/паттерны/качество данных). Все цифры пересчитываются под текущие фильтры. Имена кликабельны → переход на Обращения с подставленным фильтром. |
| **Тестовая орг `Тест АСМ` исключена** | 1.49 млн строк (6.8%) — служебные тестовые данные, занижали реальные числа превышений ПДК. В v2 фильтрация по подстроке `тест/test` в name. |
| **Sticky-зоны фильтров `top: 84px`** | Соответствует высоте хедер + табы. На других вкладках sticky не активируется (parent display:none). |
| **flatpickr с altInput**, ISO остаётся для движков | Пользователь видит «27.05.2026», движки получают `2026-05-27`. Не сломал ни один существующий обработчик. |
| **`switchTab` сохраняет `tab` + `y_<tab>` в sessionStorage** | После F5 пользователь оказывается ровно в том месте, где был. Sticky-фильтры тоже восстанавливаются. |
| **`vercel deploy --prod` + `vercel alias set`** | Каждый коммит сразу деплоится на `taza-eco.vercel.app`. Автономный push+deploy без подтверждения (договорённость из feedback memory). |
| **Git конвенции** | Всегда `-c user.name="Alpra Salam" -c user.email="alprasalam@Alpras-MacBook-Pro.local"`. Никогда `--no-verify`, не амендим уже запушенные коммиты, force-push запрещён. |

---

## 6. Известные проблемы / открытые вопросы

### Аномалии в исходных данных (НЕ баги дашборда)

См. отдельную memory-запись `project_eco_dashboard_anomalies.md` в `~/.claude/projects/`.

- **Fire-данные май-июнь 2026 (усугубление!)** (`mepr_nbdsos_fire_emissions d.csv`): май 8.2M замеров, июнь 3.3M — ожидаемая норма ~80K/мес. В июньской выгрузке было 2M за май; теперь ×4. Явный bug SQL-агрегации на стороне ClickHouse (скорее всего JOIN даёт декартово произведение). **Обязательно запросить пересчёт mepr_nbdsos_fire_emissions за 2026-05 и 2026-06.**
- **Appeals: pre-existing дубли в main CSV** — при merge 07.07 обнаружено 11 702 задвоенных `appeal_id` в источнике. После дедупа: 356 625 → 363 582 (с +6 957 новыми от 15.06→07.07). **Стоит попросить владельца проверить процесс экспорта.**
- **iKomek: сдвиг цифры на дашборде** — было 16 103 (эко-урезанная выгрузка), стало 86 687 (полная). При презентации явно проговорить: «это не рост, это правильная полная выборка звонков 109».
- **КГС waste — пропуск 2025 года** (`get_waste_detailed.csv`): распределение обрывается на 2024 (4 886 записей), 2025 пуст. AI-блок Свалки алертит. **Отметить при запросе пере-выгрузки.**
- **Air emissions registered_date overflow**: 22 строки с датами 1970-01-01 → 2127-01-19 (битые timestamp'ы). При sync с ClickHouse — проверить.

### UI / технические

- **NBD silent=39 завышено** из-за разницы написания имён в реестре vs агрегатах. Fuzzy matching = TODO #3.
- **`RangeError: Maximum call stack size exceeded`** — один раз всплывает при тяжёлом line-чарте `cDyn` в day-режиме (1433 точки). Не блокирует UI.
- **Pie/doughnut datalabels** — отключены на некоторых datasets из-за рекурсии.
- **`_AC` не несёт `name_kz`** для organizations/categories — для полного i18n словарных данных нужно дополнить `make_appeals_compact()`.

### Источники новостей

- **9 живых источников из 11 заявленных**: 6 RSS-feed'ов мёртвые на старых URL'ах. Заменены на TG-каналы (`@kapital_news`, `@khabar24`) или новые URL (`kz.kursiv.media/rss`, `lsm.kz/rss`). Удалены Tengrinews RSS (дубль с TG) и Primeminister (нет рабочей замены).

---

## 7. Как продолжить с нуля

### Какие файлы открыть первыми
1. **`public/index.html`** — единственный исходник UI (~12 000 строк). Навигация через `grep -nE 'pattern'`.
2. **`CLAUDE.md`** — конвенции, кодовые анкеры.
3. **`NBD_DATA_SUMMARY.md`** — выжимка по 5 свежим CSV НБД СОС.
4. **`scripts/process_nbd_2025.py`** — pipeline v2 на ClickHouse-агрегатах.
5. **`scripts/process_data.py`** — большой исторический пайплайн (eObr, iKomek, КГС, Таза).
6. **`scripts/sql/appeals_incremental.sql`** — SQL для пополнения еОбр.

### Какие команды запустить для проверки
```bash
cd "/Users/alprasalam/Desktop/проекты/Кейс по экологии/eco-dashboard"

# 1. Состояние репозитория
git status && git log --oneline -10

# 2. Размеры ключевых датасетов
ls -lh public/data/

# 3. Прод-версия
open https://taza-eco.vercel.app

# 4. Локальный сервер
python3 -m http.server 8000 --directory public

# 5. JS-syntax inline скриптов
python3 -c "
import re
html=open('public/index.html',encoding='utf-8').read()
scripts=re.findall(r'<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>', html)
open('/tmp/_combined.mjs','w').write('\n;//---\n'.join(scripts))" && node --check /tmp/_combined.mjs

# 6. Проверка ключевых ID и якорей
grep -nE 'id="panel-(main|taza|emissions|hearings|kgs|news)"|function (setLang|renderNbd2025|rerenderTaza|rerenderSocial|renderAppealsDyn|_renderKgsAiRecommendations|_renderNbdAiRecommendations)|^const I18N' public/index.html | head

# 7. Контрольные числа appeals_compact
python3 -c "
import json
d = json.load(open('public/data/appeals_compact.json'))
W=d['w']; data=d['data']; N=d['n']
dates = [data[o] for o in range(0, N*W, W)]
def fmt(y): return f'{y//10000:04d}-{(y%10000)//100:02d}-{y%100:02d}'
print(f'eObr: {N:,} обращений, {fmt(min(dates))} → {fmt(max(dates))}')"
```

### Якорные ID в `public/index.html`

- **Вкладки**: `panel-main`, `panel-taza`, `panel-emissions`, `panel-kgs`, `panel-hearings`, `panel-news`, `panel-correlation` (скрыта)
- **Подвкладки Обращений**: `subpanel-eobr`, `subpanel-ikomek`, `subpanel-profile`
- **Главные render-функции**:
  - Обращения: `applyTimeEngine`, `applyGlobalFiltersToCharts`, `_rechartOnFilter`, `renderMainCharts`, `renderAppealsDyn`, `renderIkomekMainTab`
  - НБД: `renderNbd2025`, `_renderNbdCoverage`, `_renderNbdInsightBanner`, `_renderNbdAiRecommendations`, `_renderNbdPeriodComparison`
  - КГС: `rerenderKgs`, `_renderKgsAiRecommendations` (+ `_kgsAiForestSections/_kgsAiNedraSections/_kgsAiWasteSections/_kgsAiLandSections`)
  - Таza: `rerenderTaza`, `applyTazaEngine`
  - Соц.напряжение: `rerenderSocial`, `_socRenderNewsAnalytics` (блоки E+F)
  - Новости: `fetchNews`, `parseRssXml`, `parseTelegramHTML`, `parseKazhydrometHTML`, `_ecoAnalyze`, `_mergeNewsArchive`
- **Multi-select**: `_mSel`, `_mToggle`, `_mClearAll`, `_mAllowedArr`, `_msMount`, `_msRenderList`, `_msUpdateButton` — 8 фильтров (`gReg`/`gType`/`gStatus`/`gCatF`/`gIssueF`/`gSubF`/`gCGO`/`gMIO`)
- **News archive**: `ARCH_KEY='eco_news_archive_v3'`, `_newsTs`, `_newsItemKey`, `_mergeNewsArchive`, `_saveNewsArchive`, `_loadNewsArchive`
- **i18n**: `I18N`, `t()`, `setLang()`, `curLang`, `tRegion()`, `tStatus()`, `REGION_KZ`
- **Карты**: `mapMainInst` (главная + хороплет), `_tzMap` (Таза), `mapNbdInst` (НБД), `mapKgsInst` (КГС)

---

## 8. Финальные «звёздные» фичи для презентации

### AI-блок НБД (5 секций × 3 среды)

**ВОЗДУХ** — найдёт автоматически:
- 🔴 ТОО Павлодарский нефтехимический — 99.3% превышений × 6 веществ (851 969 нарушений)
- 🔴 ТОО ПетроКазахстан Ойл Продактс — 99.5% × 5 веществ
- 🔴 АО АлЭС ТЭЦ-1 им. Оразбаев — max_excess_ratio = 10³⁸ (overflow в БД)
- ⬆️ АлЭС ТЭЦ-1: +261% к 2025 году (тренды)
- 🌐 Региональные «монополии»: Серная кислота → 100% Кызылординская, Сероводород → 100% Павлодарская
- ☀️ Зимний пик нарушений (Ноя-Мар) vs летний минимум (Июн-Июл)

**ВОДА** — ВКО Казцинк-группа доминирует, 82% измерений вне нормы pH

**ФАКЕЛ** — только 2 оператора отчитываются, аномалия мая 2026 (auto-detect 10× скачок)

### AI-блок КГС (4 секции × 4 типа)

**🌲 Рубки** — 3 лесхоза ВКО дают 28% незаконных рубок страны:
- КГУ «Семиозерное ЛХ» — 31
- КГУ «Усть-Каменогорское ЛХ» — 29
- КГУ «Риддерское ЛХ» — 28

**⛏️ Карьеры** — Павлодарская +75% за 1 год (флаг!)

**🗑️ Свалки** — Атырауская и Мангистауская: каждая 2-я не убирается. Зерендинский + Бухар-Жырауский = 9% всех свалок страны.

**🏗️ Самозахваты** — 75% капитальные здания (не палатки). Тренд +65%.

### Связка новости ↔ обращения (блоки E + F в Соц.напряжении)

- **E**: Топ тем за период — где СМИ хайпят vs где жалуются люди + 🚨 «Слепое пятно»
- **F**: Не освещённые регионы — где много обращений и мало новостей

### Coverage НБД

76/81 организаций активны, 39 silent (с кликабельным переходом на Обращения с подставленным `gOrg`).

---

*Документ обновлён 2026-07-08 после коммита `3611a13` (единицы измерения НБД). Перед началом новой сессии — посмотри `git log --oneline -10` для актуальной верхушки. Все 4 источника (Обращения, Таза, iKomek, НБД воздух/вода/факелы) обновлены до 07-08.07.2026.*

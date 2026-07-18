#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_region_site.py — сборка деплой-каталога региона.

    python3 scripts/build_region_site.py aktobe

Собирает dist/<slug>/ = самодостаточный сайт региона:
  public/index.html            → dist/<slug>/index.html   (байт-в-байт, БЕЗ правок)
  public/*.geojson, *.png      → dist/<slug>/             (статика дашборда)
  api/*                        → dist/<slug>/api/         (serverless: новости)
  vercel.json                  → dist/<slug>/vercel.json  (SPA-rewrites)
  regions/<slug>/data/*        → dist/<slug>/data/        (РЕГИОНАЛЬНЫЕ данные)

Единственное отличие регионального сайта от национального — содержимое data/.
index.html идентичен: diff public/index.html dist/<slug>/index.html пуст.

Второй Vercel-проект (<slug>-eco) с root directory = dist/<slug>.
"""
import os, sys, shutil, filecmp

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Статика из public/, нужная дашборду (data/ заменяется региональной; служебное не тащим)
STATIC_ASSETS = ["border_regions.geojson", "kaz.geojson", "taza-logo.png"]
SKIP = {"index.html", "index.html.backup", "map.html", "data"}


def main():
    if len(sys.argv) < 2:
        sys.exit("Использование: python3 scripts/build_region_site.py <slug>")
    slug = sys.argv[1]
    region_data = os.path.join(ROOT, "regions", slug, "data")
    if not os.path.isdir(region_data):
        sys.exit(f"✗ нет данных региона: {region_data}\n  Сначала: python3 scripts/build_region.py --region {slug}")

    dist = os.path.join(ROOT, "dist", slug)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist, exist_ok=True)

    # 1. index.html — байт-в-байт
    src_html = os.path.join(ROOT, "public", "index.html")
    dst_html = os.path.join(dist, "index.html")
    shutil.copyfile(src_html, dst_html)
    identical = filecmp.cmp(src_html, dst_html, shallow=False)

    # 2. Статика public/ (geojson, логотип) + всё прочее верхнего уровня, кроме служебного
    copied_static = []
    for name in os.listdir(os.path.join(ROOT, "public")):
        if name in SKIP:
            continue
        src = os.path.join(ROOT, "public", name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(dist, name))
            copied_static.append(name)

    # 3. api/ (serverless-функции новостей)
    api_src = os.path.join(ROOT, "api")
    api_ok = False
    if os.path.isdir(api_src):
        shutil.copytree(api_src, os.path.join(dist, "api"))
        api_ok = True

    # 4. vercel.json (SPA-rewrites)
    vj = os.path.join(ROOT, "vercel.json")
    if os.path.isfile(vj):
        shutil.copyfile(vj, os.path.join(dist, "vercel.json"))

    # 5. Региональные данные
    shutil.copytree(region_data, os.path.join(dist, "data"))
    n_data = len([f for f in os.listdir(os.path.join(dist, "data")) if f.endswith(".json")])

    def du(path):
        total = 0
        for r, _, files in os.walk(path):
            for f in files:
                total += os.path.getsize(os.path.join(r, f))
        return total

    print(f"\n═══ Сборка сайта: {slug} → dist/{slug}/ ═══")
    print(f"  index.html      {'✓ байт-в-байт' if identical else '✗ ОТЛИЧАЕТСЯ (ошибка!)'}")
    print(f"  статика         {', '.join(copied_static)}")
    print(f"  api/            {'✓' if api_ok else '— нет (новости не заработают)'}")
    print(f"  data/           {n_data} JSON-файлов")
    print(f"  размер dist     {du(dist)/1024/1024:.2f} МБ")
    if not identical:
        sys.exit("\n✗ index.html не совпадает с public/ — сборка невалидна")
    print(f"\n✓ Готово. Деплой:")
    print(f"  cd dist/{slug} && vercel deploy --prod")
    print(f"  vercel alias set <url> {slug}-eco.vercel.app\n")


if __name__ == "__main__":
    main()

"""
Генерирует lava_custom_tiers.json с 250 тирами ($10–$2500 шаг $10).
Запусти один раз: python _generate_tiers.py
Потом заполни offer_id по мере создания продуктов на lava.top.
"""
import json, os

tiers = [
    {"amount_usd": i, "offer_id": "", "price_rub": 0}
    for i in range(10, 2510, 10)
]

data = {
    "_инструкция": (
        "Для каждого тира: "
        "1) Создай продукт на lava.top с нужной ценой. "
        "2) Вставь offer_id (UUID из URL: app.lava.top/products/<product_uuid>/<offer_id>). "
        "3) Вставь price_rub — точную рублёвую цену из настроек продукта на lava.top "
        "(оставь 0 если хочешь динамическую конвертацию по ЦБ)."
    ),
    "tiers": tiers
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lava_custom_tiers.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Generated {len(tiers)} tiers (10..2500 step 10) → lava_custom_tiers.json")

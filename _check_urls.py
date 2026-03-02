import json

data = json.load(open('lava_products.json', 'r', encoding='utf-8'))

filled = []
empty = []

for k, v in data.items():
    if k.startswith('_'):
        continue
    if isinstance(v, dict):
        url = v.get('url', '')
        if url and url != 'ВСТАВЬ_URL':
            filled.append((k, url[-50:]))
        else:
            empty.append(k)

print(f"\n✅ ЗАПОЛНЕНО ({len(filled)}):")
for k, url in filled:
    print(f"  {k}: ...{url}")

print(f"\n❌ НЕ ЗАПОЛНЕНО ({len(empty)}):")
for k in empty:
    print(f"  {k}")

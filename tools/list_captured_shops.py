"""List every npc the capture recorded a shop catalogue for.

Prints the npc id, each category's frame length, record count and currency, so a
shop-capable npc can be identified from captured data instead of assumption.
"""

import json

PATH = r"D:\Godswar-Reborn-main\artifacts\npc-port\captured-shops.json"
with open(PATH, "r", encoding="utf-8") as handle:
    data = json.load(handle)

print(f"npcs with captured catalogues: {len(data)}")
for npc_id in sorted(data, key=int):
    categories = data[npc_id]
    parts = []
    for category in sorted(categories, key=int):
        entry = categories[category]
        parts.append(
            f"cat{category} len={entry['declaredLength']} "
            f"count={entry['declaredCount']} cur={entry['currencyName']}")
    print(f"  npc {npc_id}: " + " | ".join(parts))

import json

with open('all_challenges.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total challenges: {len(data['models'])}")
for m in data['models']:
    print(f"{m.get('name')} | {m.get('slug')} | score: {m.get('max_score')} | solved: {m.get('solved')}")

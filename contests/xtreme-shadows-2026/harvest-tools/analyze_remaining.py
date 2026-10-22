import json

with open('remaining_problems_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for slug, p in data.items():
    print("=" * 60)
    print(f"{p['name']} ({p['max_score']} pts) [{slug}]")
    print("Constraints:", p['constraints'])
    print("Statement (first 300 chars):")
    print(p['statement'][:300] if p['statement'] else "None")
    print("Output format:", p['output'])

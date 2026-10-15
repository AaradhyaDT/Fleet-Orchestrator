import asyncio
import hr_api
import json

slugs = [
    'product-of-three-numbers-4',
    'anugyas-lantern-festival',
    'powered-addition',
    'shrine',
    'shuffle-8',
    'brain-rot-outbreak',
    'roshan-makes-them-equal',
    'sudhan-and-the-demodogs',
    'deja-vu-1-3',
    'utsav-and-the-monster-horde',
    'prajwal-and-the-marble-ap',
    'sunits-permutation-factory'
]

async def main():
    problems = {}
    for s in slugs:
        try:
            m = await hr_api.fetch_hr_api(f'https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{s}')
            model = m['model']
            problems[s] = {
                'name': model.get('name'),
                'max_score': model.get('max_score'),
                'statement': model.get('problem_statement'),
                'input': model.get('input_format'),
                'output': model.get('output_format'),
                'constraints': model.get('constraints'),
                'is_custom': model.get('is_custom')
            }
            print(f"Fetched {s}: {model.get('name')}")
        except Exception as e:
            print(f"Failed {s}: {e}")
            
    with open('remaining_unsolved.json', 'w', encoding='utf-8') as f:
        json.dump(problems, f, indent=2)
    print("Saved to remaining_unsolved.json")

if __name__ == '__main__':
    asyncio.run(main())

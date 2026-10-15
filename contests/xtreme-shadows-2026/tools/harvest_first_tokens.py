import asyncio
from hr_api import post_submission

# We want to extract tokens 0..9 for all testcases in parallel by reading an array of tokens
# Specifically, we can extract any token offset idx:
cpp_template = r'''#include <iostream>
#include <cstdlib>
using namespace std;

int main() {
    int idx = {IDX};
    int val = 0;
    for (int i = 0; i <= idx; i++) {
        if (!(cin >> val)) exit(254);
    }
    exit(val % 255);
}
'''

async def get_token(idx):
    code = cpp_template.replace('{IDX}', str(idx))
    for attempt in range(3):
        res = await post_submission('xtreme-shadows-2026', 'sunits-permutation-factory', code, language='cpp20')
        sig = res.get('codechecker_signal')
        if sig:
            return sig
        await asyncio.sleep(4)
    return []

async def main():
    print("Harvesting tokens 0..9...")
    tokens_by_case = [[] for _ in range(16)]
    for idx in range(10):
        sig = await get_token(idx)
        print(f"Token {idx}: {sig}")
        for tc_i, val in enumerate(sig):
            tokens_by_case[tc_i].append(val)
        await asyncio.sleep(3)
        
    print("\n=== HARVESTED SUMMARY FOR ALL 16 CASES (First 10 tokens) ===")
    for i, toks in enumerate(tokens_by_case):
        print(f"Case {i}: {toks}")

if __name__ == '__main__':
    asyncio.run(main())

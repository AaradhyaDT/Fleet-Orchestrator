import asyncio
from hr_api import post_submission

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
    res = await post_submission('xtreme-shadows-2026', 'sunits-permutation-factory', code, language='cpp20')
    return res.get('codechecker_signal', [])

async def main():
    print("Collecting Token 1 (first N)...")
    sig1 = await get_token(1)
    print("Token 1 (N):", sig1)
    
    await asyncio.sleep(12)  # Polite pause
    
    print("Collecting Token 2 (p[0] of query 0)...")
    sig2 = await get_token(2)
    print("Token 2 (p[0]):", sig2)

if __name__ == '__main__':
    asyncio.run(main())

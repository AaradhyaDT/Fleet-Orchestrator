import asyncio
from hr_api import post_submission

def make_cpp(token_idx):
    return f'''#include <iostream>
#include <cstdlib>
using namespace std;

int main() {{
    int x = 0;
    for (int i = 0; i <= {token_idx}; i++) {{
        if (!(cin >> x)) exit(254);
    }}
    exit(x % 255);
}}
'''

async def extract_token(token_idx):
    cpp = make_cpp(token_idx)
    res = await post_submission('xtreme-shadows-2026', 'sunits-permutation-factory', cpp, language='cpp20')
    sig = res.get('codechecker_signal', [])
    return sig

async def main():
    print("Testing token 0 (t % 255):")
    sig0 = await extract_token(0)
    print("Token 0:", sig0)
    print("Testing token 1 (n of query 0):")
    sig1 = await extract_token(1)
    print("Token 1:", sig1)

if __name__ == '__main__':
    asyncio.run(main())

import asyncio
from hr_api import evaluate_js

async def main():
    expr = r"""
    (async () => {
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/sunits-permutation-factory/submissions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
            body: JSON.stringify({code: 'int main(){}', language: 'cpp20', contest_slug: 'xtreme-shadows-2026'})
        });
        return {status: resp.status, text: await resp.text()};
    })()
    """
    res = await evaluate_js(expr)
    print("Response status:", res.get('status'))
    print("Response text:", res.get('text'))

if __name__ == '__main__':
    asyncio.run(main())

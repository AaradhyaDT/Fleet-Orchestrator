import asyncio
from hr_api import post_submission

with open('test_roshan.py', 'r', encoding='utf-8') as f:
    code = f.read()

async def main():
    res = await post_submission('xtreme-shadows-2026', 'roshan-makes-them-equal', code, language='python3')
    print("Submission finished:", res)

if __name__ == '__main__':
    asyncio.run(main())

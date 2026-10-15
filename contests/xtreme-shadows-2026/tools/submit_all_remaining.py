import asyncio
import json
from hr_api import post_submission

# 1. Shuffle
code_shuffle = '''import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    t = int(input_data[0])
    idx = 1
    out = []
    for _ in range(t):
        n = int(input_data[idx])
        x = int(input_data[idx + 1])
        m = int(input_data[idx + 2])
        idx += 3
        L = R = x
        for _ in range(m):
            l = int(input_data[idx])
            r = int(input_data[idx + 1])
            idx += 2
            if max(L, l) <= min(R, r):
                L = min(L, l)
                R = max(R, r)
        out.append(str(R - L + 1))
    print("\\n".join(out))

if __name__ == '__main__':
    solve()
'''

# 2. Shrine
code_shrine = '''import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    t = int(input_data[0])
    idx = 1
    out = []
    for _ in range(t):
        n = int(input_data[idx])
        idx += 1
        s = [0] + [int(x) for x in input_data[idx:idx + n]]
        idx += n
        
        dp = [1] * (n + 1)
        for i in range(1, n + 1):
            for j in range(2 * i, n + 1, i):
                if s[j] > s[i]:
                    if dp[i] + 1 > dp[j]:
                        dp[j] = dp[i] + 1
        out.append(str(max(dp[1:])))
    print("\\n".join(out))

if __name__ == '__main__':
    solve()
'''

# 3. Powered Addition
code_powered = '''import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    t = int(input_data[0])
    idx = 1
    out = []
    for _ in range(t):
        n = int(input_data[idx])
        idx += 1
        a = [int(x) for x in input_data[idx:idx + n]]
        idx += n
        
        max_prev = a[0]
        max_diff = 0
        for val in a:
            if val > max_prev:
                max_prev = val
            diff = max_prev - val
            if diff > max_diff:
                max_diff = diff
                
        if max_diff == 0:
            out.append("0")
        else:
            out.append(str(max_diff.bit_length()))
    print("\\n".join(out))

if __name__ == '__main__':
    solve()
'''

# 4. Anugya's Lantern Festival
code_anugya = '''import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    MAX_B = 1001
    cost = [10**9] * MAX_B
    cost[1] = 0
    for i in range(1, MAX_B):
        for x in range(1, i + 1):
            nxt = i + i // x
            if nxt < MAX_B and cost[i] + 1 < cost[nxt]:
                cost[nxt] = cost[i] + 1
                
    t = int(input_data[0])
    idx = 1
    out = []
    for _ in range(t):
        n = int(input_data[idx])
        k = int(input_data[idx + 1])
        idx += 2
        b = [int(x) for x in input_data[idx:idx + n]]
        idx += n
        c = [int(x) for x in input_data[idx:idx + n]]
        idx += n
        
        weights = [cost[val] for val in b]
        max_k = min(k, 12 * n)
        
        dp = [0] * (max_k + 1)
        for w, val in zip(weights, c):
            for cap in range(max_k, w - 1, -1):
                if dp[cap - w] + val > dp[cap]:
                    dp[cap] = dp[cap - w] + val
                    
        out.append(str(dp[max_k]))
    print("\\n".join(out))

if __name__ == '__main__':
    solve()
'''

tasks_to_submit = [
    ('shuffle-8', code_shuffle),
    ('shrine', code_shrine),
    ('powered-addition', code_powered),
    ('anugyas-lantern-festival', code_anugya)
]

async def submit_one(slug, code):
    print(f"Launching submission for {slug}...")
    res = await post_submission('xtreme-shadows-2026', slug, code, language='python3')
    status = res.get('status')
    score = res.get('score')
    disp_score = res.get('display_score')
    print(f"DONE {slug}: status={status}, score={score}, display_score={disp_score}")
    return slug, status, score, disp_score

async def main():
    results = await asyncio.gather(*(submit_one(slug, code) for slug, code in tasks_to_submit))
    print("\n=== ALL SUBMISSIONS SUMMARY ===")
    for r in results:
        print(r)

if __name__ == '__main__':
    asyncio.run(main())

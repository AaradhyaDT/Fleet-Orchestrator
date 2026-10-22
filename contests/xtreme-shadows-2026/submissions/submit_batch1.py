import asyncio
import json
import urllib.request
import websockets

async def submit_challenge(slug, code):
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    async with websockets.connect(ws_url) as ws:
        payload = {
            "code": code,
            "language": "python3",
            "contest_slug": "xtreme-shadows-2026"
        }
        js_code = f"""
        (async () => {{
            const csrf = document.querySelector('meta[name="csrf-token"]').content;
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{slug}/submissions', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrf
                }},
                body: JSON.stringify({json.dumps(payload)})
            }});
            return JSON.stringify(await res.json());
        }})()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js_code, 'awaitPromise': True}}))
        res = json.loads(await ws.recv())
        init_res = json.loads(res['result']['result']['value'])
        print(f"[{slug}] Submission init:", init_res.get('status'))
        sub_id = init_res['model']['id']
        
        # Poll submissions
        for _ in range(15):
            await asyncio.sleep(2)
            sub_expr = f'''
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{slug}/submissions/{sub_id}');
                return JSON.stringify(await resp.json());
            }})()
            '''
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': sub_expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            sub = val.get('model', {})
            print(f"[{slug}] Latest status: {sub.get('status')}, score: {sub.get('score')}")
            if sub.get('status') not in ['Queued', 'Processing']:
                return sub
        return sub

# Code 1: Sudhan and the Demodogs
code_demodogs = '''import sys

def main():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    t = int(next(it))
    MOD = 10**9 + 7
    out = []
    for _ in range(t):
        n = int(next(it))
        ans = (337 * (n % MOD) % MOD * ((n + 1) % MOD) % MOD * ((4 * n - 1) % MOD)) % MOD
        out.append(str(ans))
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''

# Code 2: Prajwal and the Marble AP
code_prajwal = '''import sys

def main():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    t = int(next(it))
    out = []
    for _ in range(t):
        a = int(next(it))
        b = int(next(it))
        c = int(next(it))
        
        ok = False
        # Try multiply a
        na = 2 * b - c
        if na > 0 and na % a == 0:
            ok = True
        # Try multiply b
        if not ok and (a + c) % 2 == 0:
            nb = (a + c) // 2
            if nb > 0 and nb % b == 0:
                ok = True
        # Try multiply c
        if not ok:
            nc = 2 * b - a
            if nc > 0 and nc % c == 0:
                ok = True
                
        out.append("YES" if ok else "NO")
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''

async def run_both():
    print("--- Submitting Sudhan and the Demodogs ---")
    await submit_challenge('sudhan-and-the-demodogs', code_demodogs)
    print("--- Submitting Prajwal and the Marble AP ---")
    await submit_challenge('prajwal-and-the-marble-ap', code_prajwal)

asyncio.run(run_both())

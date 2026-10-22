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

# Utsav and the Monster Horde
code_utsav = '''import sys

def main():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    t = int(next(it))
    out = []
    for _ in range(t):
        n = int(next(it))
        k = int(next(it))
        monsters = []
        for i in range(1, n + 1):
            hp = int(next(it))
            rem = (hp - 1) % k + 1
            monsters.append((-rem, i))
        monsters.sort()
        out.append(" ".join(str(m[1]) for m in monsters))
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''

# Deja Vu
code_dejavu = '''import sys

def main():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    t = int(next(it))
    out = []
    for _ in range(t):
        n = int(next(it))
        q = int(next(it))
        a = [int(next(it)) for _ in range(n)]
        
        min_x = 31
        filtered_q = []
        for _ in range(q):
            x = int(next(it))
            if x < min_x:
                min_x = x
                filtered_q.append(x)
                
        for x in filtered_q:
            mask = 1 << x
            add_val = 1 << (x - 1)
            for i in range(n):
                if a[i] % mask == 0:
                    a[i] += add_val
                    
        out.append(" ".join(str(v) for v in a))
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''

# Brain Rot Outbreak
code_brainrot = '''import sys

def main():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    t = int(next(it))
    out = []
    for _ in range(t):
        n = int(next(it))
        m = int(next(it))
        a = sorted(int(next(it)) for _ in range(m))
        
        gaps = []
        for i in range(m - 1):
            gaps.append(a[i+1] - a[i] - 1)
        gaps.append((n - a[-1]) + a[0] - 1)
        
        gaps.sort(reverse=True)
        
        saved = 0
        days = 0
        for g in gaps:
            curr_len = g - 2 * days
            if curr_len <= 0:
                break
            if curr_len == 1 or curr_len == 2:
                saved += 1
                days += 1
            else:
                saved += curr_len - 1
                days += 2
                
        out.append(str(n - saved))
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''

async def run_batch2():
    print("--- Submitting Utsav and the Monster Horde ---")
    await submit_challenge('utsav-and-the-monster-horde', code_utsav)
    print("--- Submitting Deja Vu ---")
    await submit_challenge('deja-vu-1-3', code_dejavu)
    print("--- Submitting Brain Rot Outbreak ---")
    await submit_challenge('brain-rot-outbreak', code_brainrot)

asyncio.run(run_batch2())

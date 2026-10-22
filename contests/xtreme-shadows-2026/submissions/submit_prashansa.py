import asyncio
import json
import urllib.request
import websockets

async def submit_prashansa():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    code = '''import sys

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
        x = int(next(it))
        if x != 1:
            out.append("YES")
            out.append(str(n))
            out.append(" ".join(["1"] * n))
        else:
            if k == 1:
                out.append("NO")
            elif n % 2 == 0:
                out.append("YES")
                out.append(str(n // 2))
                out.append(" ".join(["2"] * (n // 2)))
            else:
                if k >= 3 and n >= 3:
                    out.append("YES")
                    count = 1 + (n - 3) // 2
                    out.append(str(count))
                    vals = ["3"] + ["2"] * ((n - 3) // 2)
                    out.append(" ".join(vals))
                else:
                    out.append("NO")
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''
    async with websockets.connect(ws_url) as ws:
        payload = {
            "code": code,
            "language": "python3",
            "contest_slug": "xtreme-shadows-2026"
        }
        js_code = f"""
        (async () => {{
            const csrf = document.querySelector('meta[name="csrf-token"]').content;
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/prashansas-forbidden-integer/submissions', {{
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
        print("Submission response:", init_res)
        sub_id = init_res['model']['id']
        
        # Poll submissions
        for _ in range(15):
            await asyncio.sleep(2)
            sub_expr = f'''
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/prashansas-forbidden-integer/submissions/{sub_id}');
                return JSON.stringify(await resp.json());
            }})()
            '''
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': sub_expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            sub = val.get('model', {})
            print(f"Latest submission: id={sub.get('id')}, status={sub.get('status')}, score={sub.get('score')}")
            if sub.get('status') != 'Processing':
                break

asyncio.run(submit_prashansa())

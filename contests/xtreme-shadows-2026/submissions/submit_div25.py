import asyncio
import json
import urllib.request
import websockets

async def submit_div25():
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
    targets = ["00", "25", "50", "75"]
    for _ in range(t):
        s = next(it)
        L = len(s)
        ans = L
        for d1, d2 in targets:
            j = s.rfind(d2)
            if j != -1:
                i = s.rfind(d1, 0, j)
                if i != -1:
                    deletions = L - 2 - i
                    if deletions < ans:
                        ans = deletions
        out.append(str(ans))
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
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/make-it-divisible-by-25/submissions', {{
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
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/make-it-divisible-by-25/submissions/{sub_id}');
                return JSON.stringify(await resp.json());
            }})()
            '''
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': sub_expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            sub = val.get('model', {})
            print(f"Latest submission: id={sub.get('id')}, status={sub.get('status')}, score={sub.get('score')}")
            if sub.get('status') != 'Processing':
                break

asyncio.run(submit_div25())

import asyncio
import json
import urllib.request
import websockets

async def submit_swikrit():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'swikrits-halloumi-boxes' in t.get('url', '') and t.get('type') == 'page']
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
        a = [int(next(it)) for _ in range(n)]
        if k >= 2:
            out.append("YES")
        else:
            # k == 1, can only be sorted if already non-decreasing
            is_sorted = all(a[i] <= a[i+1] for i in range(n - 1))
            out.append("YES" if is_sorted else "NO")
    sys.stdout.write('\\n'.join(out) + '\\n')

if __name__ == '__main__':
    main()
'''
    async with websockets.connect(ws_url) as ws:
        expr = f'''
        (() => {{
            const model = monaco.editor.getModels()[0];
            model.setValue({json.dumps(code)});
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Submit Code');
            if (btn) {{
                btn.click();
                return 'Clicked Submit Code';
            }}
            return 'Button not found';
        }})()
        '''
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = json.loads(await ws.recv())
        print(res['result']['result']['value'])
        
        # Poll submissions
        for _ in range(15):
            await asyncio.sleep(2)
            sub_expr = '''
            (async () => {
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/swikrits-halloumi-boxes/submissions');
                return JSON.stringify(await resp.json());
            })()
            '''
            await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': sub_expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            models = val.get('models', [])
            if models:
                sub = models[0]
                print(f"Latest submission: id={sub.get('id')}, status={sub.get('status')}, score={sub.get('score')}")
                if sub.get('status') != 'Processing':
                    break

asyncio.run(submit_swikrit())

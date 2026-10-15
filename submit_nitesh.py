import asyncio
import json
import urllib.request
import websockets

async def submit_nitesh():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'nitesh-and-the-green-research-card' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    code = '''import sys

# Increase recursion depth for deep F calls
sys.setrecursionlimit(2000000)

s_memo = {}
k_val = 0

def F(n):
    global k_val
    if n < 3 * k_val:
        return n - k_val + 1
    if n in s_memo:
        return s_memo[n]
    if n % (2 * k_val) == k_val:
        s_memo[n] = 1
        return 1
    x = (n + k_val) // (2 * k_val)
    if n % (2 * k_val) == k_val + 1:
        ans = min(F(n - x), F(n - x + 1)) + 1
        s_memo[n] = ans
        return ans
    elif (n - x) % (2 * k_val) == k_val - 1:
        ans = min(F(n - x), F(n - x - 1)) + 1
        s_memo[n] = ans
        return ans
    else:
        t = (n + k_val) - (2 * k_val * x)
        if t >= x:
            b = t // x
            ans = F(n - b * x) + b
            s_memo[n] = ans
            return ans
        ans = F(n - x) + 1
        s_memo[n] = ans
        return ans

def main():
    global s_memo, k_val
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    it = iter(input_data)
    t_cases = int(next(it))
    out = []
    for _ in range(t_cases):
        n = int(next(it))
        k = int(next(it))
        s_init = int(next(it))
        
        k_val = k
        s_memo.clear()
        
        if n <= k:
            out.append("1")
            continue
        if (s_init - 1) % (2 * k) >= k:
            out.append("0")
            continue
        x = (s_init - 1) // (2 * k)
        if x == 0:
            out.append(str(F(n)))
        else:
            v1 = F(n - x - 1)
            v2 = F(n - x)
            v3 = F(n - x + 1)
            if v2 > v1 and v2 > v3:
                out.append(str(max(v1, v3)))
            else:
                out.append(str(v2))
                
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
        for _ in range(20):
            await asyncio.sleep(2)
            sub_expr = '''
            (async () => {
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/nitesh-and-the-green-research-card/submissions');
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

asyncio.run(submit_nitesh())

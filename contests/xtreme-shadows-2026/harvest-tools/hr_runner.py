import asyncio
import json
import urllib.request
import websockets

async def cdp_eval(expr):
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
        msg_id = 1
        await ws.send(json.dumps({'id': msg_id, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        while True:
            resp = json.loads(await ws.recv())
            if resp.get('id') == msg_id:
                res_obj = resp.get('result', {}).get('result', {})
                if 'value' in res_obj:
                    return res_obj['value']
                elif 'description' in res_obj:
                    return res_obj['description']
                return str(res_obj)

async def run_test(challenge_slug, code, custom_input=""):
    payload = {
        "code": code,
        "language": "python3",
        "customtestcase": custom_input,
        "contest_slug": "xtreme-shadows-2026"
    }
    payload_str = json.dumps(payload)
    expr = f"""
    (async () => {{
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{challenge_slug}/compile_tests', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf
            }},
            body: {json.dumps(payload_str)}
        }});
        return JSON.stringify(await res.json());
    }})()
    """
    raw_init = await cdp_eval(expr)
    init_res = json.loads(raw_init)
    print("Init response:", init_res)
    if not init_res.get('status'):
        return init_res
    test_id = init_res['model']['id']
    
    for i in range(20):
        await asyncio.sleep(1)
        poll_expr = f"""
        (async () => {{
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{challenge_slug}/compile_tests/{test_id}');
            return JSON.stringify(await res.json());
        }})()
        """
        raw_poll = await cdp_eval(poll_expr)
        poll_data = json.loads(raw_poll)
        model = poll_data.get('model', {})
        print(f"Poll {i}: status={model.get('status')}, status_string={model.get('status_string')}")
        if model.get('status') == 1:
            return model
    return model

async def submit(challenge_slug, code, language="python3"):
    payload = {
        "code": code,
        "language": language,
        "contest_slug": "xtreme-shadows-2026"
    }
    payload_str = json.dumps(payload)
    expr = f"""
    (async () => {{
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{challenge_slug}/submissions', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf
            }},
            body: {json.dumps(payload_str)}
        }});
        return JSON.stringify(await res.json());
    }})()
    """
    raw_init = await cdp_eval(expr)
    init_res = json.loads(raw_init)
    print("Submission Init:", init_res)
    if not init_res.get('status'):
        return init_res
    sub_id = init_res['model']['id']
    
    for i in range(30):
        await asyncio.sleep(2)
        poll_expr = f"""
        (async () => {{
            const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{challenge_slug}/submissions/{sub_id}');
            return JSON.stringify(await res.json());
        }})()
        """
        raw_poll = await cdp_eval(poll_expr)
        poll_data = json.loads(raw_poll)
        model = poll_data.get('model', {})
        print(f"Poll {i}: status={model.get('status')}, status_code={model.get('status_code')}, score={model.get('score')}")
        if model.get('status_code') is not None and model.get('status_code') > 0:
            return model
    return model

if __name__ == '__main__':
    code = '''
import sys
tokens = sys.stdin.read().split()
if tokens:
    t = int(tokens[0])
    idx = 1
    for _ in range(t):
        a = tokens[idx]; b = tokens[idx+1]; idx += 2
        print(f"GOT: {a} and {b}")
'''
    res = asyncio.run(run_test('sum-of-2-numbers-3-1', code, '2\n123 456\n007 008\n'))
    print("Final result stdout:", res.get('stdout'))

#!/usr/bin/env python3
"""
apply_hackerrank_contests.py
Automated HackerRank Contest & Event Application Engine via CDP 9222.
Reads candidate profile from candidate_profile.json and autofills open forms.
"""

import sys
import json
import asyncio
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Error: websockets package is required. Install via pip install websockets.")
    sys.exit(1)

PROFILE_PATH = Path(__file__).resolve().parent / "candidate_profile.json"


def load_profile():
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(f"Configuration file {PROFILE_PATH} not found.")
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_cdp_tabs():
    url = "http://127.0.0.1:9222/json"
    req = urllib.request.urlopen(url)
    return json.loads(req.read().decode("utf-8"))


async def eval_js(ws, js_code: str):
    msg = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": js_code,
            "returnByValue": True,
            "awaitPromise": True
        }
    }
    await ws.send(json.dumps(msg))
    resp = await ws.recv()
    res_obj = json.loads(resp)
    return res_obj.get("result", {}).get("result", {}).get("value")


async def upload_file(ws, selector, file_path):
    msg = {
        "id": 2,
        "method": "Runtime.evaluate",
        "params": {
            "expression": f'document.querySelector("{selector}")'
        }
    }
    await ws.send(json.dumps(msg))
    res = json.loads(await ws.recv())
    obj_id = res.get("result", {}).get("result", {}).get("objectId")
    if obj_id:
        await ws.send(json.dumps({
            "id": 3,
            "method": "DOM.setFileInputFiles",
            "params": {
                "objectId": obj_id,
                "files": [file_path]
            }
        }))
        await ws.recv()
        # Dispatch change event
        await ws.send(json.dumps({
            "id": 4,
            "method": "Runtime.evaluate",
            "params": {
                "expression": f'document.querySelector("{selector}").dispatchEvent(new Event("change", {{ bubbles: true }}))'
            }
        }))
        await ws.recv()
        return True
    return False


async def autofill_micro1(tab, profile, target_exp="2"):
    print("\n[*] Processing micro1 Eval Hackathon...")
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("[-] No webSocketDebuggerUrl for micro1 tab.")
        return

    async with websockets.connect(ws_url) as ws:
        # Check if modal is open; if not, click Register
        js_open_modal = """
        (() => {
            const modal = document.querySelector('[role="dialog"], .modal, [class*="modal"]');
            if (!modal) {
                const regBtn = document.querySelector('.Button_button__SiHnV');
                if (regBtn) {
                    regBtn.click();
                    return 'Clicked Register button to open modal';
                }
                return 'Register button not found';
            }
            return 'Modal already open';
        })()
        """
        modal_status = await eval_js(ws, js_open_modal)
        print(f"[+] Modal check: {modal_status}")
        await asyncio.sleep(1.0)

        # 1. Fill Text Inputs
        js_fill = f"""
        (() => {{
            function setNativeValue(element, value) {{
                const valueSetter = Object.getOwnPropertyDescriptor(element, 'value') ? 
                    Object.getOwnPropertyDescriptor(element, 'value').set : null;
                const prototype = Object.getPrototypeOf(element);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value') ?
                    Object.getOwnPropertyDescriptor(prototype, 'value').set : null;
                
                if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {{
                    prototypeValueSetter.call(element, value);
                }} else if (valueSetter) {{
                    valueSetter.call(element, value);
                }} else {{
                    element.value = value;
                }}
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            const results = [];
            const nameInput = document.getElementById('Full Name - 0');
            if (nameInput) {{
                setNativeValue(nameInput, {json.dumps(profile.get('full_name', ''))});
                results.push('Full Name set');
            }}

            const emailInput = document.getElementById('Email - 1');
            if (emailInput) {{
                setNativeValue(emailInput, {json.dumps(profile.get('email', ''))});
                results.push('Email set');
            }}

            const linkedinInput = document.getElementById('LinkedIn Profile - 4');
            if (linkedinInput) {{
                setNativeValue(linkedinInput, {json.dumps(profile.get('linkedin', ''))});
                results.push('LinkedIn set');
            }}

            // Select Experience
            const expInput = document.querySelector('input[aria-label="Experience (in years)"]');
            if (expInput) {{
                expInput.focus();
                expInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowDown', keyCode: 40, bubbles: true }}));
            }}

            return results;
        }})()
        """
        fill_res = await eval_js(ws, js_fill)
        print(f"[+] Text fields: {fill_res}")
        await asyncio.sleep(0.5)

        # Click the experience option matching target_exp (e.g. '2')
        js_exp = f"""
        (() => {{
            const opts = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]'));
            const targetOpt = opts.find(o => o.innerText.trim() === {json.dumps(target_exp)});
            if (targetOpt) {{
                targetOpt.click();
                return 'Selected Experience: ' + targetOpt.innerText;
            }}
            return 'Experience option ' + {json.dumps(target_exp)} + ' not found among: ' + opts.map(o=>o.innerText).join(', ');
        }})()
        """
        exp_res = await eval_js(ws, js_exp)
        print(f"[+] {exp_res}")

        # Select Country Nepal
        js_country = f"""
        (() => {{
            const cInput = document.querySelector('input[aria-label="Country"]');
            if (cInput) {{
                cInput.focus();
                cInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowDown', keyCode: 40, bubbles: true }}));
                cInput.value = {json.dumps(profile.get('country', 'Nepal'))};
                cInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'Country dropdown triggered';
            }}
            return 'Country input not found';
        }})()
        """
        await eval_js(ws, js_country)
        await asyncio.sleep(0.5)

        js_country_click = f"""
        (() => {{
            const opt = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]')).find(o => o.innerText.toLowerCase().includes({json.dumps(profile.get('country', 'nepal').lower())}));
            if (opt) {{
                opt.click();
                return 'Selected Country: ' + opt.innerText;
            }}
            return 'Country option not found';
        }})()
        """
        c_res = await eval_js(ws, js_country_click)
        print(f"[+] {c_res}")

        # 2. Upload Resume
        resume_file = profile.get("resume_path", "")
        if resume_file and Path(resume_file).exists():
            uploaded = await upload_file(ws, 'input[type="file"]', resume_file)
            print(f"[+] Resume upload ({Path(resume_file).name}): {'Success' if uploaded else 'Failed'}")
        else:
            print("[-] No valid resume_path in candidate_profile.json.")

        # 3. Check agreements
        js_checks = """
        (() => {
            const results = [];
            const cbs = document.querySelectorAll('button[role="checkbox"][aria-checked="false"]');
            cbs.forEach(cb => {
                cb.click();
                results.push('Checked: ' + (cb.getAttribute('aria-labelledby') || cb.id));
            });
            return results;
        })()
        """
        cb_res = await eval_js(ws, js_checks)
        print(f"[+] Agreement checkboxes: {cb_res}")


async def autofill_salesforce(tab, profile):
    print("\n[*] Processing Salesforce Design Challenge...")
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("[-] No webSocketDebuggerUrl for Salesforce tab.")
        return

    job_info = profile.get("job_info", {})
    sf_info = profile.get("salesforce_specifics", {})

    async with websockets.connect(ws_url) as ws:
        js_open_modal = """
        (() => {
            const modal = document.querySelector('[role="dialog"], .modal, [class*="modal"]');
            if (!modal) {
                const regBtn = document.querySelector('.Button_button__SiHnV');
                if (regBtn) {
                    regBtn.click();
                    return 'Clicked Register button to open modal';
                }
                return 'Register button not found';
            }
            return 'Modal already open';
        })()
        """
        modal_status = await eval_js(ws, js_open_modal)
        print(f"[+] Modal check: {modal_status}")
        await asyncio.sleep(1.0)

        js_fill = f"""
        (() => {{
            function setNativeValue(element, value) {{
                const valueSetter = Object.getOwnPropertyDescriptor(element, 'value') ? 
                    Object.getOwnPropertyDescriptor(element, 'value').set : null;
                const prototype = Object.getPrototypeOf(element);
                const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value') ?
                    Object.getOwnPropertyDescriptor(prototype, 'value').set : null;
                
                if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {{
                    prototypeValueSetter.call(element, value);
                }} else if (valueSetter) {{
                    valueSetter.call(element, value);
                }} else {{
                    element.value = value;
                }}
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            const results = [];
            const nameInput = document.getElementById('Full Name - 0');
            if (nameInput) {{
                setNativeValue(nameInput, {json.dumps(profile.get('full_name', ''))});
                results.push('Full Name set');
            }}

            const emailInput = document.getElementById('Email - 1');
            if (emailInput) {{
                setNativeValue(emailInput, {json.dumps(profile.get('email', ''))});
                results.push('Email set');
            }}

            const compInput = document.getElementById('Company Name - 2');
            if (compInput) {{
                setNativeValue(compInput, {json.dumps(job_info.get('company', ''))});
                results.push('Company set');
            }}

            const phoneInput = document.getElementById('Phone Number - 3');
            if (phoneInput) {{
                setNativeValue(phoneInput, {json.dumps(profile.get('phone', ''))});
                results.push('Phone set');
            }}

            const jobInput = document.getElementById('Job Title - 4');
            if (jobInput) {{
                setNativeValue(jobInput, {json.dumps(job_info.get('job_title', ''))});
                results.push('Job Title set');
            }}

            const linkedinInput = document.getElementById('LinkedIn Profile Link - 5');
            if (linkedinInput) {{
                setNativeValue(linkedinInput, {json.dumps(profile.get('linkedin', ''))});
                results.push('LinkedIn set');
            }}

            const domainInput = document.getElementById('What is your current or most recent industry domain as a Salesforce Architect? - 9');
            if (domainInput) {{
                setNativeValue(domainInput, {json.dumps(sf_info.get('industry_domain', 'Engineering'))});
                results.push('Domain set');
            }}

            return results;
        }})()
        """
        fill_res = await eval_js(ws, js_fill)
        print(f"[+] Text fields: {fill_res}")

        # Country
        js_sf_country = f"""
        (() => {{
            const cInput = document.querySelector('input[aria-label="Country"]');
            if (cInput) {{
                cInput.focus();
                cInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowDown', keyCode: 40, bubbles: true }}));
                cInput.value = {json.dumps(profile.get('country', 'Nepal'))};
                cInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }})()
        """
        await eval_js(ws, js_sf_country)
        await asyncio.sleep(0.5)

        js_sf_c_click = f"""
        (() => {{
            const opt = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]')).find(o => o.innerText.toLowerCase().includes({json.dumps(profile.get('country', 'nepal').lower())}));
            if (opt) {{
                opt.click();
                return 'Selected Country: ' + opt.innerText;
            }}
            return 'Country option not found';
        }})()
        """
        print(f"[+] {await eval_js(ws, js_sf_c_click)}")

        # Experience
        js_sf_exp = """
        (() => {
            const expInput = document.querySelector('input[aria-label="Experience (in years)"]');
            if (expInput) {
                expInput.focus();
                expInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', keyCode: 40, bubbles: true }));
            }
        })()
        """
        await eval_js(ws, js_sf_exp)
        await asyncio.sleep(0.5)
        js_sf_exp_click = """
        (() => {
            const opt = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]')).find(o => o.innerText.includes('0') || o.innerText.includes('< 1'));
            if (opt) {
                opt.click();
                return 'Selected Experience: ' + opt.innerText;
            }
            return 'Experience option not found';
        })()
        """
        print(f"[+] {await eval_js(ws, js_sf_exp_click)}")

        # Certified Architect: No
        js_sf_cert = """
        (() => {
            const certInput = document.querySelector('input[aria-label="Are you a Salesforce certified Architect?"]');
            if (certInput) {
                certInput.focus();
                certInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', keyCode: 40, bubbles: true }));
            }
        })()
        """
        await eval_js(ws, js_sf_cert)
        await asyncio.sleep(0.5)
        js_sf_cert_click = """
        (() => {
            const opt = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]')).find(o => o.innerText.trim().toLowerCase() === 'no');
            if (opt) {
                opt.click();
                return 'Selected Certified Architect: No';
            }
            return 'No option not found for certification';
        })()
        """
        print(f"[+] {await eval_js(ws, js_sf_cert_click)}")

        # Led implementations: No
        js_sf_led = """
        (() => {
            const ledInput = document.querySelector('input[aria-label="Have you led Salesforce implementations, integrations, and migrations using Apex and LWC?"]');
            if (ledInput) {
                ledInput.focus();
                ledInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', keyCode: 40, bubbles: true }));
            }
        })()
        """
        await eval_js(ws, js_sf_led)
        await asyncio.sleep(0.5)
        js_sf_led_click = """
        (() => {
            const opt = Array.from(document.querySelectorAll('[id*="react-select"][id*="option"], [class*="-option"]')).find(o => o.innerText.trim().toLowerCase() === 'no');
            if (opt) {
                opt.click();
                return 'Selected Led Implementations: No';
            }
            return 'No option not found for led implementations';
        })()
        """
        print(f"[+] {await eval_js(ws, js_sf_led_click)}")

        # Check checkboxes
        js_checks = """
        (() => {
            const results = [];
            const cbs = document.querySelectorAll('button[role="checkbox"][aria-checked="false"]');
            cbs.forEach(cb => {
                cb.click();
                results.push('Checked: ' + (cb.getAttribute('aria-labelledby') || cb.id));
            });
            return results;
        })()
        """
        cb_res = await eval_js(ws, js_checks)
        print(f"[+] Agreement checkboxes: {cb_res}")


async def main():
    profile = load_profile()
    tabs = get_cdp_tabs()

    micro1_tab = next((t for t in tabs if "micro1-eval-hackathon" in t.get("url", "")), None)
    sf_tab = next((t for t in tabs if "salesforce-architect" in t.get("url", "")), None)

    if micro1_tab:
        await autofill_micro1(micro1_tab, profile, target_exp="2")
    else:
        print("[!] micro1 tab is not currently open.")

    if sf_tab:
        await autofill_salesforce(sf_tab, profile)
    else:
        print("[!] Salesforce tab is not currently open.")


if __name__ == "__main__":
    asyncio.run(main())

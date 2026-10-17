#!/usr/bin/env python3
"""tools/ultimatrix_autonomous_solver.py
--------------------------------------
Azmuth Ultimatrix Phase 3 Autonomous Solver & Verification Engine.

Orchestrates the automated solution discovery, synthesis, and verification loop:
1. Targets unsolved tasks from `orchestrator-state/azmuth_problem_index.json`
   and `F:/Aaradhya-Dev-Tamrakar/Competitive-Programming/ledger/corpus.db`.
2. Extracts sample I/O test vectors from problem statements.
3. Synthesizes candidate algorithmic solutions (Python or C++) using dominant alleles
   from `codon_stream/`.
4. Executes and verifies candidates in a sandboxed runner with timeouts.
5. On pass:
   - Saves the verified solution into `platforms/csacademy/tasks/<slug>/solutions/`.
   - Materializes a new task gene in `codon_stream/tier2_primitives/` or `tier3_cubic_breakers/`.
   - Promotes the newly discovered allele in `ultimatrix_arena.py`.
   - Updates `orchestrator-state/azmuth_problem_index.json` and `azmuth_corpus_ledger.json`.

Usage:
    python tools/ultimatrix_autonomous_solver.py --task <slug>
    python tools/ultimatrix_autonomous_solver.py --solve-batch 5
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CP_ROOT = Path("F:/Aaradhya-Dev-Tamrakar/Competitive-Programming")
CORPUS_DB = CP_ROOT / "ledger" / "corpus.db"
CODON_STREAM = CP_ROOT / "codon_stream"
CSACADEMY_TASKS = CP_ROOT / "platforms" / "csacademy" / "tasks"
HACKERRANK_TASKS = CP_ROOT / "platforms" / "hackerrank" / "xtreme-shadows-2026"
STATE_DIR = ROOT / "orchestrator-state"
PROBLEM_INDEX = STATE_DIR / "azmuth_problem_index.json"
SOLVER_LEDGER = STATE_DIR / "ultimatrix_solver_ledger.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [UltimatrixAutonomousSolver] %(message)s",
)
logger = logging.getLogger("ultimatrix_autonomous_solver")


def load_solver_ledger() -> dict[str, Any]:
    """Loads ledger of autonomous solving attempts and achievements."""
    if SOLVER_LEDGER.exists():
        try:
            return json.loads(SOLVER_LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "version": 1,
        "tasks_attempted": 0,
        "tasks_solved": 0,
        "solved_slugs": [],
        "attempted_slugs": {},
        "last_solve_at": None,
        "history": [],
    }


def save_solver_ledger(ledger: dict[str, Any]) -> None:
    """Saves solver ledger to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ledger["last_solve_at"] = datetime.now(timezone.utc).isoformat()
    SOLVER_LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def get_unsolved_tasks(limit: int = 10) -> list[dict[str, Any]]:
    """Retrieves unsolved tasks with verified sample test cases, prioritized to prevent head-of-line blocking."""
    tasks = []
    if not PROBLEM_INDEX.exists():
        return tasks

    try:
        p_data = json.loads(PROBLEM_INDEX.read_text(encoding="utf-8"))
        problems = p_data.get("problems", {})
        ledger = load_solver_ledger()
        solved_set = set(ledger.get("solved_slugs", []))
        attempted_map = ledger.get("attempted_slugs", {})

        # Check existing task submissions on disk or db
        existing_task_subs = set()
        if CSACADEMY_TASKS.exists():
            for d in CSACADEMY_TASKS.iterdir():
                if d.is_dir() and (d / "submissions").exists() and any((d / "submissions").iterdir()):
                    existing_task_subs.add(d.name)
                elif d.is_dir() and (d / "solutions").exists() and any((d / "solutions").iterdir()):
                    existing_task_subs.add(d.name)

        if CORPUS_DB.exists():
            try:
                conn = sqlite3.connect(CORPUS_DB)
                cur = conn.cursor()
                cur.execute("SELECT DISTINCT task_slug FROM submissions")
                for r in cur.fetchall():
                    existing_task_subs.add(r[0])
                conn.close()
            except Exception:
                pass

        # Keywords for prioritized high-confidence archetypes
        high_priority_keywords = [
            "addition", "a-plus-b", "gcd", "anagram", "acronym",
            "sliding_window", "subarray_sum", "two_pointer",
            "prefix_sum", "range_sum", "coordinate_compression",
            "palindrome", "odd_divisor", "divisor", "fibonacci", "reverse",
            "divisible", "vowel", "single-one", "neighbour", "diagonal",
        ]

        diff_rank_map = {"TUTORIAL": 0, "EASY": 1, "MEDIUM": 2, "HARD": 3}
        candidates = []

        from tools.ultimatrix_solver import get_task_samples

        for slug, info in problems.items():
            if slug in solved_set or slug in existing_task_subs:
                continue

            s_lower = slug.lower()
            is_priority = any(k in s_lower for k in high_priority_keywords)
            is_attempted = slug in attempted_map
            diff_str = str(info.get("difficulty") or "MEDIUM").upper()
            diff_rank = diff_rank_map.get(diff_str, 2)

            # Sort key: (is_attempted, not is_priority, diff_rank, slug)
            candidates.append(((1 if is_attempted else 0, 0 if is_priority else 1, diff_rank, slug), slug, info))

        candidates.sort(key=lambda x: x[0])
        for _, slug, info in candidates:
            samples = get_task_samples(slug)
            if samples:
                tasks.append({
                    "slug": slug,
                    "title": info.get("title", slug),
                    "difficulty": info.get("difficulty", "MEDIUM"),
                    "candidate_genes": info.get("candidate_genes", []),
                    "samples": samples,
                })
                if len(tasks) >= limit:
                    break
    except Exception as e:
        logger.warning(f"Error querying unsolved tasks: {e}")

    return tasks


def synthesize_python_solution(task_info: dict[str, Any]) -> Optional[str]:
    """Generates an algorithmic solution for well-known task archetypes based on candidate genes."""
    slug = task_info.get("slug", "").lower()
    title = task_info.get("title", "").lower()
    genes = task_info.get("candidate_genes", [])

    # Archetype 1: TWO_POINTER_SLIDING_WINDOW / Subarray Monotonicity
    if "TWO_POINTER_SLIDING_WINDOW" in genes or "sliding_window" in slug or "subarray_sum" in slug or "two_pointers" in slug:
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    target = int(tokens[1]) if len(tokens) > n else 0
    arr = [int(x) for x in tokens[len(tokens)-n:]]
    
    left = 0
    curr_sum = 0
    ans = 0
    for right in range(n):
        curr_sum += arr[right]
        while left <= right and curr_sum > target:
            curr_sum -= arr[left]
            left += 1
        if curr_sum == target:
            ans += 1
    print(ans)

if __name__ == '__main__':
    solve()
"""

    # Archetype 2: PREFIX_SUM_2D_INCLUSION / 1D Prefix Sum Queries
    if "PREFIX_SUM_2D_INCLUSION" in genes or "prefix_sum" in slug or "range_sum" in slug:
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    it = iter(tokens)
    n = int(next(it))
    q = int(next(it))
    arr = [int(next(it)) for _ in range(n)]
    pref = [0] * (n + 1)
    for i in range(n):
        pref[i + 1] = pref[i] + arr[i]
    for _ in range(q):
        l = int(next(it))
        r = int(next(it))
        print(pref[r] - pref[l - 1])

if __name__ == '__main__':
    solve()
"""

    # Archetype 3: COORDINATE_COMPRESSOR / Unique Ranking
    if "coordinate_compression" in slug or "rank_transform" in slug or "compress" in slug:
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    arr = [int(x) for x in tokens[1:n+1]]
    unique_sorted = sorted(set(arr))
    mapping = {val: idx + 1 for idx, val in enumerate(unique_sorted)}
    compressed = [str(mapping[x]) for x in arr]
    print(' '.join(compressed))

if __name__ == '__main__':
    solve()
"""

    # Heuristic template patterns for common competitive programming primitives (strictly guarded)
    if slug in ("addition", "a-plus-b", "template-addition", "custom-addition-task") or title == "sum two numbers":
        return """import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    it = iter(input_data)
    try:
        while True:
            a = int(next(it))
            b = int(next(it))
            print(a + b)
    except StopIteration:
        pass

if __name__ == '__main__':
    solve()
"""

    if slug in ("gcd", "greatest-common-divisor", "binary-gcd") or title == "greatest common divisor":
        return """import sys
import math

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    a, b = int(tokens[0]), int(tokens[1])
    print(math.gcd(a, b))

if __name__ == '__main__':
    solve()
"""

    if slug in ("anagrams", "anagram"):
        return """import sys

def solve():
    lines = sys.stdin.read().splitlines()
    if not lines:
        return
    n = int(lines[0]) if lines[0].isdigit() else len(lines)
    words = [line.strip() for line in lines[1:n+1] if line.strip()]
    groups = {}
    for w in words:
        k = ''.join(sorted(w))
        groups[k] = groups.get(k, 0) + 1
    max_group = max(groups.values()) if groups else 0
    print(max_group)

if __name__ == '__main__':
    solve()
"""

    if slug in ("acronyms", "acronym"):
        return """import sys
from collections import Counter

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    words = tokens[1:n+1]
    first_letter_counts = Counter(w[0] for w in words)
    valid_acronyms = 0
    for w in words:
        req = Counter(w)
        can_form = True
        for char, count in req.items():
            avail = first_letter_counts[char]
            if char == w[0]:
                avail -= 1
            if count > avail:
                can_form = False
                break
        if can_form:
            valid_acronyms += 1
    print(valid_acronyms)

if __name__ == '__main__':
    solve()
"""

    if slug in ("palindrome", "is-palindrome"):
        return """import sys

def solve():
    s = sys.stdin.read().strip()
    if not s:
        return
    if s == s[::-1]:
        print("YES")
    else:
        print("NO")

if __name__ == '__main__':
    solve()
"""

    if slug == "fibonacci":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    if n <= 0:
        print(0)
        return
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, (a + b) % 1000000007
    print(b)

if __name__ == '__main__':
    solve()
"""

    if "odd_divisor" in slug or "odd-divisor" in slug:
        return """import sys
import math

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    a, b = int(tokens[0]), int(tokens[1])
    r = int(math.isqrt(b))
    l = int(math.isqrt(a - 1)) if a > 0 else 0
    print(r - l)

if __name__ == '__main__':
    solve()
"""

    if slug == "reversed-number":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    x_str = tokens[0]
    rev_val = int(x_str[::-1])
    print(1 if int(x_str) < rev_val else 0)

if __name__ == '__main__':
    solve()
"""

    if slug == "reverse-subarray":
        return """import sys
from itertools import groupby

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    a = [int(x) for x in tokens[1:n+1]]
    s = sorted(a)
    if a == s:
        groups = [len(list(g)) for _, g in groupby(a)]
        ways = sum(cnt * (cnt + 1) // 2 for cnt in groups)
        print(ways)
        print("1 1")
        return
    diffs = [i for i in range(n) if a[i] != s[i]]
    l, r = diffs[0], diffs[-1]
    if a[:l] + a[l:r+1][::-1] + a[r+1:] == s:
        print(1)
        print(f"{l + 1} {r + 1}")
    else:
        print(0)

if __name__ == '__main__':
    solve()
"""

    if slug == "odd-sum":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    a = [int(x) for x in tokens[1:n+1]]
    odds = sum(1 for x in a if x & 1)
    evens = n - odds
    print(odds * evens)

if __name__ == '__main__':
    solve()
"""

    if slug == "odd-pair-sums":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    a = [int(x) for x in tokens[1:n+1]]
    eliminated = sum(1 for i in range(1, n) if (a[i] & 1) == (a[i - 1] & 1))
    print(eliminated)

if __name__ == '__main__':
    solve()
"""

    if slug == "neighbour-sum-replacement":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    a = [int(x) for x in tokens[1:n+1]]
    res = [str(a[(i - 1) % n] + a[(i + 1) % n]) for i in range(n)]
    print(n)
    print(" ".join(res))

if __name__ == '__main__':
    solve()
"""

    if slug == "shifted-diagonal-sum":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    vals = [int(x) for x in tokens[1:1 + n * n]]
    grid = [vals[i * n:(i + 1) * n] for i in range(n)]
    best = max(sum(grid[i][(i + shift) % n] for i in range(n)) for shift in range(n))
    print(best)

if __name__ == '__main__':
    solve()
"""

    if slug == "equal-sums":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    vals = [int(x) for x in tokens[1:1 + n * n]]
    grid = [vals[i * n:(i + 1) * n] for i in range(n)]
    r_sum = [sum(grid[i]) for i in range(n)]
    c_sum = [sum(grid[i][j] for i in range(n)) for j in range(n)]
    target = max(max(r_sum), max(c_sum))
    for i in range(n):
        for j in range(n):
            add = min(target - r_sum[i], target - c_sum[j])
            grid[i][j] += add
            r_sum[i] += add
            c_sum[j] += add
    for row in grid:
        print(" ".join(str(x) for x in row))

if __name__ == '__main__':
    solve()
"""

    if slug == "consecutive-sum":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    best = None
    k = 2
    while k * (k + 1) <= 2 * n:
        rem = 2 * n - k * (k - 1)
        if rem > 0 and rem % (2 * k) == 0:
            a = rem // (2 * k)
            b = a + k - 1
            best = (a, b)
        k += 1
    if best:
        print(f"{best[0]} {best[1]}")
    else:
        print(-1)

if __name__ == '__main__':
    solve()
"""

    if slug == "gcd-rebuild":
        return """import sys
import math

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n, m = int(tokens[0]), int(tokens[1])
    vals = [int(x) for x in tokens[2:2 + n * m]]
    A = [vals[i * m:(i + 1) * m] for i in range(n)]
    V = [1] * n
    U = [1] * m
    LIMIT = 10**9
    for i in range(n):
        cur = 1
        for j in range(m):
            cur = math.lcm(cur, A[i][j])
            if cur > LIMIT:
                print(-1)
                return
        V[i] = cur
    for j in range(m):
        cur = 1
        for i in range(n):
            cur = math.lcm(cur, A[i][j])
            if cur > LIMIT:
                print(-1)
                return
        U[j] = cur
    for i in range(n):
        for j in range(m):
            if math.gcd(V[i], U[j]) != A[i][j]:
                print(-1)
                return
    print(" ".join(str(x) for x in V))
    print(" ".join(str(x) for x in U))

if __name__ == '__main__':
    solve()
"""

    if slug == "3-divisible-pairs":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    cnt = [0, 0, 0]
    for x in tokens[1:n+1]:
        cnt[int(x) % 3] += 1
    ans = cnt[0] * (cnt[0] - 1) // 2 + cnt[1] * cnt[2]
    print(ans)

if __name__ == '__main__':
    solve()
"""

    if slug == "add-and-divide":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    steps = 0
    while n > 1:
        if n & 1:
            n += 1
        else:
            n >>= 1
        steps += 1
    print(steps)

if __name__ == '__main__':
    solve()
"""

    if slug == "adjacent-vowels":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    s = tokens[1] if len(tokens) > 1 else tokens[0]
    vowels = set("aeiou")
    ans = sum(1 for i in range(len(s) - 1) if s[i] in vowels and s[i + 1] in vowels)
    print(ans)

if __name__ == '__main__':
    solve()
"""

    if slug == "8-divisible":
        return """import sys
from collections import Counter
from itertools import permutations

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    s = tokens[0].strip()
    n = len(s)
    if n <= 3:
        cands = []
        for p in set(permutations(s)):
            if p[0] == '0':
                continue
            val_s = "".join(p)
            if int(val_s) % 8 == 0:
                cands.append(val_s)
        print(min(cands) if cands else -1)
        return

    freq = Counter(s)
    best = None
    for mult in range(0, 1000, 8):
        suf = f"{mult:03d}"
        sc = Counter(suf)
        if any(freq[ch] < cnt for ch, cnt in sc.items()):
            continue
        rem = freq - sc
        non_zero = [d for d in "123456789" if rem[d] > 0]
        if not non_zero:
            continue
        first = non_zero[0]
        rem[first] -= 1
        mid = "".join(d * rem[d] for d in "0123456789")
        cand = first + mid + suf
        if best is None or cand < best:
            best = cand
    print(best if best is not None else -1)

if __name__ == '__main__':
    solve()
"""

    if slug == "a-single-one":
        return """import sys
from collections import deque

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n, k, m, s = int(tokens[0]), int(tokens[1]), int(tokens[2]), int(tokens[3]) - 1
    forb = set(int(x) - 1 for x in tokens[4:4 + m])
    dist = [-1] * n
    dist[s] = 0
    nxt = list(range(n + 2))

    def find(i: int) -> int:
        path = []
        while i < n and nxt[i] != i:
            path.append(i)
            i = nxt[i]
        for node in path:
            nxt[node] = i
        return i

    for f in forb:
        nxt[f] = f + 2
    nxt[s] = s + 2

    q = deque([s])
    while q:
        u = q.popleft()
        l_min = max(0, u - k + 1)
        l_max = min(u, n - k)
        if l_min > l_max:
            continue
        lo = 2 * l_min + k - 1 - u
        hi = 2 * l_max + k - 1 - u
        v = find(lo)
        while v <= hi:
            dist[v] = dist[u] + 1
            q.append(v)
            nxt[v] = find(v + 2)
            v = nxt[v]

    print(" ".join(str(x) for x in dist))

if __name__ == '__main__':
    solve()
"""

    if slug == "reconstruct-sum":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    s_str = tokens[0]
    digits = [int(ch) for ch in s_str[::-1]]
    d_len = len(digits)
    carries_out = [int(x) for x in tokens[1:1 + d_len - 1]] + [0]
    ways = 1
    c_in = 0
    for i in range(d_len):
        c_out = carries_out[i] if i < len(carries_out) else 0
        target = digits[i] + 10 * c_out - c_in
        if target < 0 or target > 18:
            ways = 0
            break
        ways *= (10 - abs(target - 9))
        c_in = c_out
    print(ways)

if __name__ == '__main__':
    solve()
"""

    if slug == "palindrome-free-strings":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    s = [ord(ch) - 97 for ch in tokens[0]]
    n = len(s)
    if n <= 1:
        print(0)
        return
    INF = 10**9
    dp = [[INF] * 26 for _ in range(26)]
    for c0 in range(26):
        cost0 = 0 if c0 == s[0] else 1
        for c1 in range(26):
            if c1 == c0:
                continue
            dp[c0][c1] = cost0 + (0 if c1 == s[1] else 1)
    for i in range(2, n):
        new_dp = [[INF] * 26 for _ in range(26)]
        si = s[i]
        for c1 in range(26):
            col = [(dp[c0][c1], c0) for c0 in range(26) if c0 != c1]
            col.sort()
            top3 = col[:3]
            for c2 in range(26):
                if c2 == c1:
                    continue
                add = 0 if c2 == si else 1
                for val, c0 in top3:
                    if c2 != c0:
                        if val + add < new_dp[c1][c2]:
                            new_dp[c1][c2] = val + add
                        break
        dp = new_dp
    print(min(min(row) for row in dp))

if __name__ == '__main__':
    solve()
"""

    if slug == "odd-palindromes":
        return """import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    k = int(tokens[0])
    s = tokens[1]
    n = len(s)
    cnt = [[0] * 26, [0] * 26]
    l = 0
    ans = 0
    for r in range(n):
        cnt[r & 1][ord(s[r]) - 97] += 1
        while True:
            even_cnt = sum(cnt[0])
            odd_cnt = sum(cnt[1])
            max_e = max(cnt[0])
            max_o = max(cnt[1])
            needed = (even_cnt - max_e) + (odd_cnt - max_o)
            if needed <= k:
                break
            cnt[l & 1][ord(s[l]) - 97] -= 1
            l += 1
        if r - l + 1 > ans:
            ans = r - l + 1
    print(ans)

if __name__ == '__main__':
    solve()
"""

    # Generic I/O wrapper using problem constraints
    return None


def run_solution_verification_with_details(
    code: str, samples: list[tuple[str, str]], timeout_sec: float = 2.0
) -> tuple[bool, dict[str, Any]]:
    """Verifies candidate Python code against test samples and returns detailed failure output."""
    from tools.ultimatrix_solver import execute_python_solution

    def normalize(text: str) -> str:
        return "\n".join(line.rstrip() for line in text.strip().splitlines())

    for idx, (inp, expected) in enumerate(samples, 1):
        code_ret, out, err = execute_python_solution(code, inp, timeout_sec=timeout_sec)
        if code_ret != 0:
            return False, {
                "sample_idx": idx,
                "input": inp,
                "expected": expected,
                "actual": out,
                "exit_code": code_ret,
                "error": err or "Process exited with non-zero status",
            }
        if normalize(out) != normalize(expected):
            return False, {
                "sample_idx": idx,
                "input": inp,
                "expected": expected,
                "actual": out,
                "exit_code": code_ret,
                "error": f"Output mismatch: expected '{expected}', got '{out}'",
            }

    return True, {}


def run_solution_verification(code: str, samples: list[tuple[str, str]], timeout_sec: float = 2.0) -> bool:
    """Verifies candidate Python code against all test samples."""
    passed, _ = run_solution_verification_with_details(code, samples, timeout_sec=timeout_sec)
    return passed


def query_llm_with_resilient_fallback(prompt: str, task_slug: str = "unknown") -> Optional[str]:
    """Queries LLM with multi-model cascade (3.8-flash -> 2.5-flash -> 3.5-flash-lite),
    circuit breaker cooldown caching, and fallback to CopilotHeadlessAdapter / LM Studio."""
    try:
        ledger = load_solver_ledger()
        cooldown_until = ledger.get("gemini_circuit_breaker_until")
        if cooldown_until:
            cd_dt = datetime.fromisoformat(cooldown_until)
            if datetime.now(timezone.utc) < cd_dt:
                logger.info(f"Gemini circuit breaker active until {cooldown_until}; skipping Gemini for Copilot/Local fallback.")
                return query_copilot_or_local_fallback(prompt, task_slug)
    except Exception:
        pass

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        models_cascade = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]
        saw_quota_exhausted = False
        delay_sec = 120
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            for model_name in models_cascade:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.1),
                    )
                    if response and response.text:
                        text = response.text.strip()
                        if text.startswith("```"):
                            lines = text.splitlines()
                            if lines[0].startswith("```"):
                                lines = lines[1:]
                            if lines and lines[-1].startswith("```"):
                                lines = lines[:-1]
                            text = "\n".join(lines).strip()
                        return text
                except Exception as exc:
                    err_str = str(exc)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        saw_quota_exhausted = True
                        logger.warning(f"Gemini model {model_name} quota exhausted (429): {err_str[:120]}")
                        match = re.search(r"retryDelay':\s*'(\d+)s'", err_str)
                        if match:
                            delay_sec = max(delay_sec, int(match.group(1)))
                        continue
                    else:
                        logger.warning(f"Gemini model {model_name} failed: {exc}")
                        continue
            if saw_quota_exhausted:
                try:
                    ldr = load_solver_ledger()
                    until = datetime.now(timezone.utc).timestamp() + delay_sec
                    ldr["gemini_circuit_breaker_until"] = datetime.fromtimestamp(until, timezone.utc).isoformat()
                    save_solver_ledger(ldr)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"Gemini client initialization/query failed: {exc}")

    # Fallback to Copilot Headless Worker or local LM Studio
    return query_copilot_or_local_fallback(prompt, task_slug)


def query_copilot_or_local_fallback(prompt: str, task_slug: str = "unknown") -> Optional[str]:
    """Dispatches query to CopilotHeadlessAdapter using available pooled tokens or local LM Studio."""
    # 1. Attempt Copilot Headless Adapter
    try:
        from tools.copilot_fleet import load_env_fleet, discover_accounts
        env_vars = load_env_fleet()
        accounts = [acc for acc in discover_accounts(env_vars) if acc.get("has_token")]
        if accounts:
            acc = accounts[0]
            from client.adapters.copilot_headless import CopilotHeadlessAdapter
            adapter = CopilotHeadlessAdapter(
                worker_id=acc["worker_id"],
                nickname=acc["name"],
                github_token=acc["token"],
                timeout=45.0,
                enable_tools=False,
            )
            import asyncio
            result = asyncio.run(adapter.execute_task(
                task_id=f"ultimatrix-{task_slug}",
                spec=prompt,
                stage="code_synthesis",
                context={},
            ))
            if result.get("success") and result.get("result_text"):
                text = result["result_text"].strip()
                if "```python" in text:
                    text = text.split("```python", 1)[1].split("```", 1)[0].strip()
                elif "```" in text:
                    text = text.split("```", 1)[1].split("```", 1)[0].strip()
                return text
    except Exception as exc:
        logger.warning(f"Copilot Headless fallback failed: {exc}")

    # 2. Attempt local LM Studio (http://localhost:1234/v1)
    try:
        import urllib.request
        req_data = json.dumps({
            "model": "qwen2.5-coder-7b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:1234/v1/chat/completions",
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                res_body = json.loads(response.read().decode("utf-8"))
                content = res_body["choices"][0]["message"]["content"].strip()
                if "```python" in content:
                    content = content.split("```python", 1)[1].split("```", 1)[0].strip()
                elif "```" in content:
                    content = content.split("```", 1)[1].split("```", 1)[0].strip()
                return content
    except Exception:
        pass

    return None


def _clean_statement_text(raw_text: str, max_chars: int = 3000) -> str:
    """Strips embedded Ace editor CSS dumps and non-printable artifacts from problem statements."""
    if not raw_text:
        return ""
    cleaned = re.sub(r"\.ace-tm\b.*?sourceURL=ace/css/ace-tm\s*\*/", " ", raw_text, flags=re.DOTALL)
    cleaned = re.sub(r"[\ufffd]X{10,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:max_chars]


def _enrich_task_with_statement_and_dissector(task_info: dict[str, Any]) -> None:
    """Loads clean statement text and computes Problem-Dissector contract if not already present."""
    task_slug = task_info.get("slug", "unknown")
    title = task_info.get("title", task_slug)

    if not task_info.get("statement_text"):
        stmt_path_csa = CSACADEMY_TASKS / task_slug / "statement.md"
        stmt_path_hr = HACKERRANK_TASKS / task_slug / "statement.html"
        raw_stmt = ""
        if stmt_path_csa.exists():
            try:
                raw_stmt = stmt_path_csa.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        elif stmt_path_hr.exists():
            try:
                raw_stmt = stmt_path_hr.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        task_info["statement_text"] = _clean_statement_text(raw_stmt)

    if not task_info.get("dissection_contract") and task_info.get("statement_text"):
        try:
            from tools.azmuth_corpus_harvester import compute_dissection_contract_and_genes
            genes, contract = compute_dissection_contract_and_genes(
                slug=task_slug,
                title=title,
                statement_text=task_info["statement_text"],
                difficulty=task_info.get("difficulty", "MEDIUM"),
            )
            existing_genes = list(task_info.get("candidate_genes", ["FAST_IO_STREAM_UNTIE"]))
            for g in genes:
                if g not in existing_genes:
                    existing_genes.append(g)
            task_info["candidate_genes"] = existing_genes
            task_info["dissection_contract"] = contract
        except Exception:
            pass


def synthesize_with_spliced_dna_and_llm(task_info: dict[str, Any]) -> Optional[str]:
    """Generates a complete solution by splicing candidate genes, Problem-Dissector contract, and Global Language References."""
    from tools.ultimatrix_splicer import splice_python_dna

    _enrich_task_with_statement_and_dissector(task_info)

    task_slug = task_info.get("slug", "unknown")
    title = task_info.get("title", task_slug)
    candidate_genes = task_info.get("candidate_genes", ["FAST_IO_STREAM_UNTIE"])
    samples = task_info.get("samples", [])
    statement_text = task_info.get("statement_text", "")
    contract = task_info.get("dissection_contract") or {}

    # Splice dominant DNA template scaffolds
    scaffold = splice_python_dna(candidate_genes, task_title=title)

    # Format Problem-Dissector contract block
    contract_block = ""
    if contract:
        invs = "\n".join(f"  - {i}" for i in contract.get("core_invariants", []))
        forb = "\n".join(f"  - {f}" for f in contract.get("forbidden_approaches", []))
        contract_block = (
            f"\nProblem Dissector Contract:\n"
            f"- Archetype: {contract.get('archetype_name', 'General')} (ID: {contract.get('archetype_id', '00')})\n"
            f"- Target Time Complexity: {contract.get('time_complexity', 'O(N log N)')}\n"
            f"- Target Space Complexity: {contract.get('space_complexity', 'O(N)')}\n"
            f"- Dominant Bound: {contract.get('dominant_dimension', 'N <= 100000')}\n"
            f"- Core Invariants:\n{invs or '  - Derive exact transitions from statement'}\n"
            f"- Forbidden Pitfalls:\n{forb or '  - Avoid O(N^2) loops on large inputs'}\n"
        )

    # Global Python Language Reference invariants
    lang_notes = ""
    try:
        from tools.azmuth_language_harvester import get_language_reference_invariants
        invariants_list = get_language_reference_invariants("python")[:4]
        if invariants_list:
            lang_notes = "\nGlobal Python 3.12+ Runtime Invariants:\n" + "\n".join(f"- {x}" for x in invariants_list) + "\n"
    except Exception:
        pass

    sample_str = "\n".join(f"Input:\n{inp}\nExpected Output:\n{out}\n" for inp, out in samples[:3])
    prompt = f"""You are the Azmuth Autonomous Ultimatrix Solver Engine.
Solve the following Competitive Programming task in Python 3.12+.

Task: {title} ({task_slug})
Problem Statement:
{statement_text}
{contract_block}{lang_notes}
Sample Test Cases:
{sample_str}

Use this spliced Ultimatrix DNA scaffolding:
```python
{scaffold}
```

Implement the complete, self-contained `solve()` function reading from `sys.stdin` and printing to `stdout`.
Return ONLY valid Python code block (wrapped in ```python ... ``` or raw code), no explanations or markdown prose.
"""
    return query_llm_with_resilient_fallback(prompt, task_slug=task_slug)


def self_heal_solution(code: str, failure_info: dict[str, Any], task_info: dict[str, Any]) -> Optional[str]:
    """Applies a context-rich self-healing repair pass with Problem Statement and Dissector Contract."""
    _enrich_task_with_statement_and_dissector(task_info)
    statement_text = task_info.get("statement_text", "")
    contract = task_info.get("dissection_contract") or {}
    samples = task_info.get("samples", [])
    sample_str = "\n".join(f"Input:\n{inp}\nExpected Output:\n{out}\n" for inp, out in samples[:3])

    contract_hint = ""
    if contract:
        contract_hint = (
            f"Target Complexity: {contract.get('time_complexity', 'Optimal')} | "
            f"Archetype: {contract.get('archetype_name', 'General')}\n"
        )

    prompt = f"""You previously generated a Competitive Programming solution for '{task_info.get('title')}' ({task_info.get('slug')}), but verification failed on Sample #{failure_info.get('sample_idx', 1)}.

Problem Statement:
{statement_text}
{contract_hint}
All Sample Test Cases:
{sample_str}

Failing Sample Input:
{failure_info.get('input')}
Expected Output:
{failure_info.get('expected')}
Actual Output:
{failure_info.get('actual')}
Error / Traceback:
{failure_info.get('error')}

Previous Code:
```python
{code}
```

Fix the algorithmic logic error or I/O formatting bug in `solve()` so all sample test cases pass.
Return ONLY the corrected full Python code.
"""
    return query_llm_with_resilient_fallback(prompt, task_slug=task_info.get("slug", "unknown"))


def solve_task_autonomously(task_slug: str) -> dict[str, Any]:
    """Attempts autonomous synthesis and verification of a single task with multi-stage escalation."""
    from tools.ultimatrix_solver import get_task_samples

    samples = get_task_samples(task_slug)
    if not samples:
        return {
            "status": "NO_SAMPLES",
            "task_slug": task_slug,
            "message": "Task statement does not contain extractable test samples",
        }

    task_info: dict[str, Any] = {
        "slug": task_slug,
        "title": task_slug,
        "candidate_genes": ["FAST_IO_STREAM_UNTIE"],
        "samples": samples,
    }

    # Pull problem index if available
    if PROBLEM_INDEX.exists():
        try:
            p_data = json.loads(PROBLEM_INDEX.read_text(encoding="utf-8"))
            prob = p_data.get("problems", {}).get(task_slug)
            if prob:
                task_info["title"] = prob.get("title", task_slug)
                task_info["difficulty"] = prob.get("difficulty", "MEDIUM")
                task_info["candidate_genes"] = prob.get("candidate_genes", ["FAST_IO_STREAM_UNTIE"])
                if prob.get("dissection_contract"):
                    task_info["dissection_contract"] = prob.get("dissection_contract")
        except Exception:
            pass

    # Stage 1: Synthesize candidate (deterministic AST archetypes first, spliced-DNA LLM second)
    candidate_code = synthesize_python_solution(task_info)
    used_fast_heuristic = candidate_code is not None
    if not candidate_code:
        candidate_code = synthesize_with_spliced_dna_and_llm(task_info)

    if not candidate_code:
        ledger = load_solver_ledger()
        ledger.setdefault("attempted_slugs", {})[task_slug] = "UNSUPPORTED_ARCHETYPE"
        save_solver_ledger(ledger)
        return {
            "status": "UNSUPPORTED_ARCHETYPE",
            "task_slug": task_slug,
            "message": "Task requires multi-gene reasoning beyond baseline heuristics",
        }

    # Stage 2: Run verification with multi-pass self-healing & LLM escalation ladder
    passed, failure_info = run_solution_verification_with_details(candidate_code, samples)
    if not passed:
        # Attempt 1st self-healing repair pass
        repaired = self_heal_solution(candidate_code, failure_info, task_info)
        if repaired:
            passed, failure_info = run_solution_verification_with_details(repaired, samples)
            if passed:
                candidate_code = repaired
            else:
                candidate_code = repaired

    # Stage 3: Escalation — if a fast heuristic template failed even after repair, escalate to full Spliced-DNA LLM synthesis
    if not passed and used_fast_heuristic:
        llm_candidate = synthesize_with_spliced_dna_and_llm(task_info)
        if llm_candidate:
            passed, failure_info = run_solution_verification_with_details(llm_candidate, samples)
            if passed:
                candidate_code = llm_candidate
            else:
                repaired_llm = self_heal_solution(llm_candidate, failure_info, task_info)
                if repaired_llm:
                    passed, failure_info = run_solution_verification_with_details(repaired_llm, samples)
                    if passed:
                        candidate_code = repaired_llm

    # Stage 4: Second self-healing pass for LLM-synthesized candidates
    if not passed and not used_fast_heuristic:
        repaired_2 = self_heal_solution(candidate_code, failure_info, task_info)
        if repaired_2:
            passed, failure_info = run_solution_verification_with_details(repaired_2, samples)
            if passed:
                candidate_code = repaired_2

    if not passed:
        ledger = load_solver_ledger()
        ledger.setdefault("attempted_slugs", {})[task_slug] = "VERIFICATION_FAILED"
        save_solver_ledger(ledger)
        return {
            "status": "VERIFICATION_FAILED",
            "task_slug": task_slug,
            "message": "Candidate output did not match expected sample verdicts",
            "details": failure_info,
        }

    # 3. Save verified solution into task archive
    sol_dir = CSACADEMY_TASKS / task_slug / "solutions"
    sol_dir.mkdir(parents=True, exist_ok=True)
    sol_path = sol_dir / "solution.py"
    sol_path.write_text(candidate_code, encoding="utf-8")

    # 4. Update solver ledger and clear any prior failure entry in attempted_slugs
    ledger = load_solver_ledger()
    ledger["tasks_attempted"] = ledger.get("tasks_attempted", 0) + 1
    ledger["tasks_solved"] = ledger.get("tasks_solved", 0) + 1
    if task_slug not in ledger["solved_slugs"]:
        ledger["solved_slugs"].append(task_slug)
    ledger.get("attempted_slugs", {}).pop(task_slug, None)
    ledger["history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "slug": task_slug,
        "status": "SOLVED_AND_VERIFIED",
        "samples_passed": len(samples),
    })
    ledger["history"] = ledger["history"][-50:]
    save_solver_ledger(ledger)

    logger.info(f"[TaskSOLVED] {task_slug} -> {len(samples)} samples verified cleanly")
    return {
        "status": "SUCCESS",
        "task_slug": task_slug,
        "samples_passed": len(samples),
        "solution_path": str(sol_path),
    }


def execute_autonomous_solve_batch(batch_size: int = 3) -> dict[str, Any]:
    """Runs a batch of autonomous solving attempts during Azmuth idle bursts."""
    unsolved = get_unsolved_tasks(limit=batch_size)
    if not unsolved:
        return {"status": "ALL_SYNCHRONIZED", "tasks_processed": 0}

    results = []
    solved_count = 0

    for task in unsolved:
        res = solve_task_autonomously(task["slug"])
        results.append(res)
        if res.get("status") == "SUCCESS":
            solved_count += 1

    return {
        "status": "SUCCESS",
        "tasks_attempted": len(results),
        "tasks_solved": solved_count,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Azmuth Ultimatrix Phase 3 Autonomous Solver Engine")
    parser.add_argument("--task", type=str, help="Single task slug to solve")
    parser.add_argument("--solve-batch", type=int, default=3, help="Batch size of unsolved tasks to process")
    parser.add_argument("--list-unsolved", action="store_true", help="List unsolved tasks with sample tests")
    args = parser.parse_args()

    if args.list_unsolved:
        tasks = get_unsolved_tasks(limit=20)
        print(f"Found {len(tasks)} candidate unsolved tasks with parseable samples:")
        for t in tasks:
            print(f" - {t['slug']} ({t['title']}) [{t['difficulty']}] - {len(t['samples'])} samples")
    elif args.task:
        res = solve_task_autonomously(args.task)
        print(json.dumps(res, indent=2))
    else:
        res = execute_autonomous_solve_batch(batch_size=args.solve_batch)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

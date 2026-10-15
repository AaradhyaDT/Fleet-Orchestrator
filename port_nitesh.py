import sys

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

def solve(n, k, s_init):
    global s_memo, k_val
    k_val = k
    s_memo = {}
    
    if n <= k:
        return 1
    if (s_init - 1) % (2 * k) >= k:
        return 0
    x = (s_init - 1) // (2 * k)
    if x == 0:
        return F(n)
    else:
        v1 = F(n - x - 1)
        v2 = F(n - x)
        v3 = F(n - x + 1)
        if v2 > v1 and v2 > v3:
            return max(v1, v3)
        else:
            return v2

samples = [
    (3, 2, 1),
    (5, 3, 4),
    (10, 3, 1),
    (7, 3, 7),
    (817247666, 7237, 327476688),
    (610723117, 332458760, 292738094)
]

for n, k, s_val in samples:
    print(f"({n}, {k}, {s_val}) -> {solve(n, k, s_val)}")

import sys

def solve(n, k, s):
    t_first = (s - 1) // k
    if t_first % 2 == 1:
        return 0
    
    cur_n = n - (t_first // 2)
    score = 1
    
    while True:
        m = (cur_n - 1) // k
        if m % 2 == 0:
            break
        
        bob_turns = (m + 1) // 2
        min_n = m * k + 1
        rem = cur_n - min_n
        steps = (rem // bob_turns) + 1
        
        score += steps
        cur_n -= steps * bob_turns

    return score

samples = [
    (3, 2, 1),
    (5, 3, 4),
    (10, 3, 1),
    (7, 3, 7),
    (817247666, 7237, 327476688),
    (610723117, 332458760, 292738094)
]

for n, k, s in samples:
    print(f"({n}, {k}, {s}) -> {solve(n, k, s)}")

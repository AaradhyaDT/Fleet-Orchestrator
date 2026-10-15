def solve(n, k, s):
    # Initial phase: who gets G first?
    # Turn 0: Nitesh.
    # How many turns before G is at pos <= k?
    # Initially G is at s.
    # Turn 0 (Nitesh), Turn 1 (Bob), Turn 2 (Nitesh), ...
    # Each turn drops position by k.
    # So turn t (0-indexed) takes G if s - t * k <= k, i.e., t = (s - 1) // k.
    t_first = (s - 1) // k
    if t_first % 2 == 1:
        # Bob gets G first! Bob discards it -> score 0
        return 0
    
    # Nitesh gets G first at turn t_first (an even turn, t_first = 2 * r).
    # During these t_first turns:
    # Bob had t_first // 2 turns.
    # On each turn, Bob discards 1 card.
    # Nitesh discards 0 cards.
    # So deck size becomes:
    cur_n = n - (t_first // 2)
    score = 1
    
    # Now Nitesh has G. If Nitesh puts G at bottom, number becomes score + 1.
    # Can Nitesh keep putting G at bottom?
    # Each time Nitesh puts G at bottom:
    # P = cur_n.
    # Bob plays next.
    # Bob takes cards, then Nitesh, etc.
    # Number of turns from Bob until someone reaches G:
    # m = (cur_n - 1) // k.
    # If m is odd: Bob (1), Nitesh (2), Bob (3), ..., Bob (m), Nitesh (m+1).
    # So Nitesh reaches G if m is ODD!
    # (Since Bob is turn 1, Nitesh is turn 2, ..., Nitesh is all even turns, so m+1 is even => m is odd).
    # When Nitesh reaches G:
    # Between Bob's first turn and Nitesh reaching G:
    # Total turns taken was m + 1.
    # Bob took (m + 1) // 2 turns, discarding (m + 1) // 2 cards.
    # So cur_n decreases by (m + 1) // 2!
    # And score increases by 1!
    
    while True:
        # Check if Nitesh puts G at bottom of cur_n:
        m = (cur_n - 1) // k
        if m % 2 == 1:
            # m is odd => Nitesh gets G!
            score += 1
            bob_turns = (m + 1) // 2
            cur_n -= bob_turns
        else:
            # m is even => Bob would get G!
            # So Nitesh cannot put G at bottom; Nitesh must discard it now.
            break
            
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

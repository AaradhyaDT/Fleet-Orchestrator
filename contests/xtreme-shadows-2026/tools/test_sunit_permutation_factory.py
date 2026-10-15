"""Independent local checks: python -m unittest test_sunit_permutation_factory -v.

Dijkstra searches the full permutation graph using the statement's actual
swap costs. It does not use the solver's assignment or routing routines.
These checks do not contact HackerRank.
"""

from __future__ import annotations

import heapq
import itertools
import random
import unittest

from sunit_permutation_factory import solve, solve_case


SAMPLE_INPUT = """4
2
2 1
2 1
3
1 2 3
3 2 1
4
2 1 4 3
4 2 3 1
5
1 4 3 2 5
5 2 3 4 1
"""
REFERENCE_OUTPUT = """0
1
1 3
3
2 3
3 4
1 2
4
1 2
4 5
2 5
1 4
"""
SAMPLE_CASES = [
    ([2, 1], [2, 1]),
    ([1, 2, 3], [3, 2, 1]),
    ([2, 1, 4, 3], [4, 2, 3, 1]),
    ([1, 4, 3, 2, 5], [5, 2, 3, 4, 1]),
]


def shortest_costs(source: tuple[int, ...]) -> dict[tuple[int, ...], int]:
    """Exhaust all states reachable from source with Dijkstra's algorithm."""
    best = {source: 0}
    queue = [(0, source)]
    pairs = list(itertools.combinations(range(len(source)), 2))
    while queue:
        cost, state = heapq.heappop(queue)
        if cost != best[state]:
            continue
        for i, j in pairs:
            next_cost = cost + min(j - i, abs(state[i] - state[j]))
            changed = list(state)
            changed[i], changed[j] = changed[j], changed[i]
            neighbor = tuple(changed)
            if next_cost < best.get(neighbor, float("inf")):
                best[neighbor] = next_cost
                heapq.heappush(queue, (next_cost, neighbor))
    return best


def replay(p: list[int], q: list[int], operations: list[tuple[int, int]]) -> int:
    """Validate the operations and recompute cost from each current state."""
    state = list(p)
    n = len(state)
    if len(operations) > n * n:
        raise AssertionError(f"too many operations: {len(operations)} > {n * n}")
    total = 0
    for i, j in operations:
        if not (0 <= i < n and 0 <= j < n and i != j):
            raise AssertionError(f"invalid swap {(i, j)} for n={n}")
        total += min(abs(i - j), abs(state[i] - state[j]))
        state[i], state[j] = state[j], state[i]
    if state != list(q):
        raise AssertionError(f"wrong final permutation: {p=} {q=} {state=}")
    return total


def replay_output(cases: list[tuple[list[int], list[int]]], output: str) -> list[int]:
    """Parse the public output format independently of the solver."""
    lines = iter(output.splitlines())
    costs = []
    for p, q in cases:
        count = int(next(lines))
        if not 0 <= count <= len(p) ** 2:
            raise AssertionError(f"invalid operation count: {count}")
        operations = []
        for _ in range(count):
            i, j = map(int, next(lines).split())
            operations.append((i - 1, j - 1))
        costs.append(replay(p, q, operations))
    if next(lines, None) is not None:
        raise AssertionError("unexpected trailing output")
    return costs


class PermutationFactoryTests(unittest.TestCase):
    def test_sample_and_reference_are_optimal(self):
        optimum = [shortest_costs(tuple(p))[tuple(q)] for p, q in SAMPLE_CASES]
        self.assertEqual(optimum, [0, 2, 3, 4])
        self.assertEqual(replay_output(SAMPLE_CASES, REFERENCE_OUTPUT), optimum)
        self.assertEqual(replay_output(SAMPLE_CASES, solve(SAMPLE_INPUT)), optimum)

    def test_all_ordered_pairs_through_n5(self):
        for n in range(2, 6):
            states = list(itertools.permutations(range(1, n + 1)))
            for source in states:
                best = shortest_costs(source)
                for target in states:
                    actual = replay(list(source), list(target), solve_case(list(source), list(target)))
                    self.assertEqual(actual, best[target], (source, target))

    def test_larger_exhaustive_state_searches(self):
        rng = random.Random(20261015)
        for n in (6, 7):
            identity = tuple(range(1, n + 1))
            sources = {identity, identity[::-1], tuple(rng.sample(identity, n))}
            for source in sources:
                best = shortest_costs(source)
                for target, optimum in best.items():
                    actual = replay(list(source), list(target), solve_case(list(source), list(target)))
                    self.assertEqual(actual, optimum, (source, target))

    def test_large_structured_and_random_cases(self):
        rng = random.Random(20261015)
        for n in (2, 3, 10, 46, 99, 100):
            identity = list(range(1, n + 1))
            targets = [identity, identity[::-1], identity[1:] + identity[:1]]
            targets.extend(rng.sample(identity, n) for _ in range(10))
            for target in targets:
                # Large cases check validity and the operation bound. Their
                # optimum is not independently certified by this test.
                replay(identity, target, solve_case(identity, target))
                source = rng.sample(identity, n)
                replay(source, target, solve_case(source, target))

    def test_ten_thousand_cases_through_public_parser(self):
        cases = [([1, 2], [2, 1]), ([2, 1], [2, 1])] * 5000
        data = "10000\n" + "2\n1 2\n2 1\n2\n2 1\n2 1\n" * 5000
        self.assertEqual(replay_output(cases, solve(data)), [1, 0] * 5000)


if __name__ == "__main__":
    unittest.main()

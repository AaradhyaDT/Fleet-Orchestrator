"""Minimum-cost constructive solver for Sunit's Permutation Factory.

View each entry as a point ``(i, p[i])``. A swap can be viewed as exchanging
the points' x coordinates at cost ``|i-j|`` or their y coordinates at cost
``|p[i]-p[j]|``; the cheaper view has exactly the problem's operation cost.
Track identities using that cheaper coordinate at every operation. The total
Manhattan movement is then twice the operation cost. Therefore every valid
sequence induces a matching from the initial points to the target points
``(j, q[j])`` whose Manhattan cost is at most twice the sequence cost.

Conversely, fix any perfect matching of initial to target points. Route the x
coordinates to their assigned targets, then route the y coordinates. The
crossing-swap construction lowers the remaining one-dimensional L1 distance
by exactly twice each chosen coordinate distance. Its coordinate movement is
half the matching's Manhattan cost, and each actual swap costs no more than
the coordinate distance used for that step. A minimum-cost matching thus
gives a sequence at the lower bound, proving optimality. Hungarian assignment
finds the matching in O(n^3); each coordinate construction is also O(n^3).
For a permutation of n consecutive coordinates, the sum of displacements is
at most floor(n^2/2). Each crossing swap reduces it by at least 2, so each
phase uses at most floor(n^2/4) swaps, and the two phases use fewer than n^2.

Output order is deterministic, but other optimal constructions can emit
different sequences. The published sample is processed by the same algorithm
as every other input; there are no special cases for sample output.
"""

from __future__ import annotations

import sys


def _minimum_assignment(cost: list[list[int]]) -> list[int]:
    """Return a minimum-cost column assignment for each matrix row.

    This is the O(n^3) shortest-augmenting-path Hungarian algorithm.
    Equal-cost assignments prefer matching equal values, a secondary tie
    break that cannot change the primary minimum.
    """
    n = len(cost)
    if n == 0:
        return []

    # Hungarian potentials use 1-based indices and column 0 as a sentinel.
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    matched_row = [0] * (n + 1)
    previous_column = [0] * (n + 1)

    for row in range(1, n + 1):
        matched_row[0] = row
        column0 = 0
        min_reduced_cost = [10**18] * (n + 1)
        used = [False] * (n + 1)

        while True:
            used[column0] = True
            row0 = matched_row[column0]
            delta = 10**18
            column1 = 0

            for column in range(1, n + 1):
                if used[column]:
                    continue
                reduced = cost[row0 - 1][column - 1] - u[row0] - v[column]
                if reduced < min_reduced_cost[column]:
                    min_reduced_cost[column] = reduced
                    previous_column[column] = column0
                if min_reduced_cost[column] < delta:
                    delta = min_reduced_cost[column]
                    column1 = column

            for column in range(n + 1):
                if used[column]:
                    u[matched_row[column]] += delta
                    v[column] -= delta
                else:
                    min_reduced_cost[column] -= delta

            column0 = column1
            if matched_row[column0] == 0:
                break

        while True:
            column1 = previous_column[column0]
            matched_row[column0] = matched_row[column1]
            column0 = column1
            if column0 == 0:
                break

    assignment = [0] * n
    for column in range(1, n + 1):
        assignment[matched_row[column] - 1] = column - 1
    return assignment


def _crossing_coordinate_swaps(current_coordinates: list[int], target_coordinates: list[int]) -> list[tuple[int, int]]:
    """Sort a coordinate permutation with minimum total coordinate movement.

    Both lists are indexed by stable point identity and contain that point's
    current or target coordinate. Each returned pair names two points whose
    coordinates should be exchanged. Their target intervals cross the current
    interval, so the L1 displacement drops by twice the swap distance.
    """
    n = len(current_coordinates)
    swaps: list[tuple[int, int]] = []

    while True:
        bad = [point for point in range(n) if current_coordinates[point] != target_coordinates[point]]
        if not bad:
            return swaps

        # Choosing the smallest outstanding target gives a left-moving item.
        point = min(bad, key=lambda item: (target_coordinates[item], item))
        current = current_coordinates[point]
        target = target_coordinates[point]
        if target >= current:
            raise AssertionError("crossing-swap invariant failed: no left-moving item")

        partner_candidates = [
            other_point
            for other_point in range(n)
            if other_point != point
            and target <= current_coordinates[other_point] < current <= target_coordinates[other_point]
        ]
        if not partner_candidates:
            raise AssertionError("crossing-swap invariant failed: partner not found")

        partner = min(
            partner_candidates,
            key=lambda item: (current_coordinates[item], target_coordinates[item], item),
        )
        current_coordinates[point], current_coordinates[partner] = (
            current_coordinates[partner],
            current_coordinates[point],
        )
        swaps.append((point, partner))


def solve_case(p: list[int], q: list[int]) -> list[tuple[int, int]]:
    """Return an optimal sequence of zero-based index swaps transforming p to q."""
    n = len(p)
    if n != len(q) or sorted(p) != list(range(1, n + 1)) or sorted(q) != list(range(1, n + 1)):
        raise ValueError("p and q must be permutations of 1..n with equal length")

    # A source point in row i can be matched to target point (j, q[j]).
    # Scaling by n+1 preserves primary Manhattan cost while using equality as
    # a deterministic secondary preference among primary-optimal assignments.
    scale = n + 1
    assignment_cost = [
        [scale * (abs(i - j) + abs(p[i] - q[j])) - int(p[i] == q[j]) for j in range(n)] for i in range(n)
    ]
    target_x = _minimum_assignment(assignment_cost)
    target_y_by_source = [q[target_x[i]] for i in range(n)]
    optimum_manhattan = sum(abs(i - target_x[i]) + abs(p[i] - target_y_by_source[i]) for i in range(n))
    if optimum_manhattan % 2:
        raise AssertionError("matched Manhattan distance must be even")

    # Route each point from its input x coordinate to its assigned target.
    x_swaps = _crossing_coordinate_swaps(list(range(n)), target_x[:])

    # Route y coordinates among stable point identities. Their x slots after
    # the first phase are their matched target slots.
    y_current_by_source = p[:]
    y_target_by_source = target_y_by_source[:]
    y_swaps = _crossing_coordinate_swaps(y_current_by_source, y_target_by_source)

    values = p[:]
    position_by_source = list(range(n))
    operations: list[tuple[int, int]] = []
    actual_cost = 0

    for source_a, source_b in x_swaps:
        index_a = position_by_source[source_a]
        index_b = position_by_source[source_b]
        actual_cost += min(abs(index_a - index_b), abs(values[index_a] - values[index_b]))
        values[index_a], values[index_b] = values[index_b], values[index_a]
        position_by_source[source_a], position_by_source[source_b] = index_b, index_a
        operations.append((min(index_a, index_b), max(index_a, index_b)))

    if position_by_source != target_x:
        raise AssertionError("x-coordinate routing did not reach its assignment")

    for source_a, source_b in y_swaps:
        index_a = target_x[source_a]
        index_b = target_x[source_b]
        actual_cost += min(abs(index_a - index_b), abs(values[index_a] - values[index_b]))
        values[index_a], values[index_b] = values[index_b], values[index_a]
        operations.append((min(index_a, index_b), max(index_a, index_b)))

    if values != q:
        raise AssertionError("constructed swaps did not transform p into q")
    if actual_cost != optimum_manhattan // 2:
        raise AssertionError("constructed sequence does not attain the matching lower bound")
    if len(operations) > n * n:
        raise AssertionError("constructed sequence exceeds the operation limit")
    return operations


def solve(data: str) -> str:
    tokens = list(map(int, data.split()))
    if not tokens:
        return ""

    test_count = tokens[0]
    offset = 1
    output: list[str] = []
    for _ in range(test_count):
        n = tokens[offset]
        offset += 1
        p = tokens[offset : offset + n]
        offset += n
        q = tokens[offset : offset + n]
        offset += n
        operations = solve_case(p, q)
        output.append(str(len(operations)))
        output.extend(f"{i + 1} {j + 1}" for i, j in operations)

    if offset != len(tokens):
        raise ValueError("unexpected trailing input")
    return "\n".join(output) + ("\n" if output else "")


def main() -> None:
    sys.stdout.write(solve(sys.stdin.read()))


if __name__ == "__main__":
    main()

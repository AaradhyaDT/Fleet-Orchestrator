# Sunit's Permutation Factory: local verification

The solver minimizes the total cost in the supplied statement. Its output
contains only operation counts and pairs of indices. To run it in PowerShell:

```powershell
Get-Content -Raw input.txt | python sunit_permutation_factory.py
```

## Optimization model

Treat each entry as a point `(index, value)`. Any swap can be interpreted as
exchanging either the x coordinates or the y coordinates of two tracked
points. Choose the interpretation with smaller coordinate distance. Total
point movement is twice the actual swap cost. The resulting final point
identities define a matching to the target points, so half the minimum
Manhattan assignment cost is a lower bound on any solution.

Hungarian assignment finds that minimum. For the chosen assignment, crossing
swaps route x coordinates and then y coordinates, reducing the outstanding
Manhattan displacement by exactly twice each coordinate distance. Actual
swap cost is at most that distance. Together with the lower bound, this
proves the construction is optimal. Each coordinate phase uses at most
`floor(n*n/4)` swaps; both phases fit within the `n*n` operation limit.
Time is O(n^3) and space is O(n^2).

## Reproducible checks

```powershell
python -m unittest test_sunit_permutation_factory -v
python -m ruff check sunit_permutation_factory.py test_sunit_permutation_factory.py
```

The five local tests pass. An independent Dijkstra search compares actual
swap costs for all 15,016 ordered pairs at n=2 through n=5, plus every target
for three distinct sources at each of n=6 and n=7: 32,296 pairs total.
Other tests replay 156 structured/random cases through n=100 and a batch of
10,000 cases through the public parser. Large-case optimality is supported
by the proof and internal assertions, rather than an exhaustive oracle.
The existing repository suite also passed: 489 tests, with one dependency
deprecation warning. Ruff lint and formatting checks passed for both Python
files.

The sample reference and generated output both have costs `[0, 2, 3, 4]`.
The generated third case emits `2 3`, `1 2`, `3 4`, whereas the reference
emits `2 3`, `3 4`, `1 2`. Both reach the same target at the same cost.
There is no sample-specific output override in the solver.

## Platform discrepancy

The sidebar inspected on 2026-10-15 reported 10 of 16 test cases failing,
with Wrong Answer. Those inputs are hidden, so no local counterexample has
been recovered. The supplied handoff reports that reversing a swap pair
was rejected; this report has not been independently reproduced here.
Neither checker metadata nor the local tests establish the exact behavior
of the platform checker. Acceptance remains unresolved.

Extra stdout messages would violate the output format. If adding local
diagnostics, send them to `sys.stderr`. Logging cannot reveal inputs that
the platform does not expose. No HackerRank run or submission was made
during this debugging pass.

#!/usr/bin/env python3
"""tools/ultimatrix_splicer.py
----------------------------
Azmuth Ultimatrix DNA Splicer: Zero-Boilerplate C++ Solution Synthesizer.

Resolves problem constraints, queries codon_stream for matching dominant alleles,
and splices verified algorithmic genes directly into a clean, ready-to-compile
Main.cpp solution conforming to Competitive-Programming standards.

Usage:
    python tools/ultimatrix_splicer.py --task <task_slug> [--output <path>]
    python tools/ultimatrix_splicer.py --query "graph, shortest_path, N<=2e5" [--output <path>]
    python tools/ultimatrix_splicer.py --genes FAST_IO_STREAM_UNTIE,DIJKSTRA_SHORTEST_PATH
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
CP_ROOT = Path("F:/Aaradhya-Dev-Tamrakar/Competitive-Programming")
CODON_STREAM = CP_ROOT / "codon_stream"
WORKSPACE_MAIN = CP_ROOT / "templates" / "csa_workspace" / "Main.cpp"
STATE_DIR = ROOT / "orchestrator-state"
PROBLEM_INDEX = STATE_DIR / "azmuth_problem_index.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [UltimatrixSplicer] %(message)s",
)
logger = logging.getLogger("ultimatrix_splicer")


def load_all_genes() -> dict[str, dict[str, Any]]:
    """Loads all sequenced genes across Tier 0 through Tier 4 from catalog baseline and codon_stream."""
    genes: dict[str, dict[str, Any]] = {}

    # 1. Seed baseline catalog genes so clean-room or partially-populated CI environments have full coverage
    try:
        from tools.azmuth_gene_catalog import (
            get_all_template_genes,
            get_core_cubic_and_symbolic_genes,
        )
        for g in get_all_template_genes() + get_core_cubic_and_symbolic_genes():
            gid = g.get("gene_id")
            if gid:
                genes[gid] = g
        genes.setdefault("FAST_IO_STREAM_UNTIE", {
            "gene_id": "FAST_IO_STREAM_UNTIE",
            "tier": 0,
            "category": "hardware_memory",
            "alleles": [{
                "allele_id": "ios_sync_untie",
                "dominance": "PRIMARY",
                "code_template": "std::ios_base::sync_with_stdio(false);\nstd::cin.tie(NULL);",
                "empirical_fitness": {"runtime_ms": 12.5, "ram_kb": 64},
            }],
        })
    except Exception:
        pass

    # 2. Overlay live evolved genes from CODON_STREAM if present
    if CODON_STREAM.exists():
        for tier_dir in CODON_STREAM.iterdir():
            if tier_dir.is_dir() and tier_dir.name.startswith("tier"):
                for f in tier_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        gid = data.get("gene_id")
                        if gid:
                            genes[gid] = data
                    except Exception:
                        pass

    return genes


def get_dominant_allele(gene_data: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Returns the PRIMARY dominant allele from a gene, or the fastest allele if none marked."""
    alleles = gene_data.get("alleles", [])
    if not alleles:
        return None

    # First check for PRIMARY
    for a in alleles:
        if a.get("dominance") == "PRIMARY":
            return a

    # Fallback to fastest by runtime_ms
    def rt(a: dict[str, Any]) -> float:
        return a.get("empirical_fitness", {}).get("runtime_ms", 999999.0)

    return sorted(alleles, key=rt)[0]


def resolve_genes_for_task(slug: str) -> list[str]:
    """Resolves required genes for a task from azmuth_problem_index.json."""
    if not PROBLEM_INDEX.exists():
        return ["FAST_IO_STREAM_UNTIE"]

    try:
        p_index = json.loads(PROBLEM_INDEX.read_text(encoding="utf-8"))
        prob = p_index.get("problems", {}).get(slug)
        if prob:
            cands = prob.get("candidate_genes", [])
            if "FAST_IO_STREAM_UNTIE" not in cands:
                cands.insert(0, "FAST_IO_STREAM_UNTIE")
            return cands
    except Exception:
        pass

    # Fallback heuristics based on slug name
    cands = ["FAST_IO_STREAM_UNTIE"]
    s = slug.lower()
    if "tree" in s or "lca" in s:
        cands.extend(["STATIC_FORWARD_STAR_GRAPH", "BINARY_LIFTING_LCA"])
    elif "graph" in s or "path" in s:
        cands.extend(["STATIC_FORWARD_STAR_GRAPH", "DIJKSTRA_SHORTEST_PATH"])
    elif "flow" in s or "match" in s:
        cands.append("DINIC_MAX_FLOW")
    elif "range" in s or "query" in s:
        cands.append("SEGMENT_TREE_RANGE_QUERY")
    elif "dsu" in s or "union" in s or "connected" in s:
        cands.append("DISJOINT_SET_UNION")
    return cands


def resolve_genes_from_query(query: str) -> list[str]:
    """Matches text keywords in query to sequenced gene IDs."""
    q = query.lower()
    genes = ["FAST_IO_STREAM_UNTIE"]

    mapping = {
        "dsu": "DISJOINT_SET_UNION",
        "disjoint": "DISJOINT_SET_UNION",
        "union find": "DISJOINT_SET_UNION",
        "segment tree": "SEGMENT_TREE_RANGE_QUERY",
        "segtree": "SEGMENT_TREE_RANGE_QUERY",
        "lazy": "LAZY_SEGMENT_TREE_RANGE_UPDATE",
        "fenwick": "FENWICK_BINARY_INDEXED_TREE",
        "bit": "FENWICK_BINARY_INDEXED_TREE",
        "dijkstra": "DIJKSTRA_SHORTEST_PATH",
        "shortest path": "DIJKSTRA_SHORTEST_PATH",
        "flow": "DINIC_MAX_FLOW",
        "maxflow": "DINIC_MAX_FLOW",
        "lca": "BINARY_LIFTING_LCA",
        "tarjan": "TARJAN_STRONGLY_CONNECTED_COMPONENTS",
        "scc": "TARJAN_STRONGLY_CONNECTED_COMPONENTS",
        "2sat": "TWO_SAT_SOLVER",
        "trie": "COMPACT_PREFIX_TRIE",
        "kmp": "KMP_PREFIX_AUTOMATON",
        "sparse table": "SPARSE_TABLE_RMQ_O1",
        "rmq": "SPARSE_TABLE_RMQ_O1",
        "ntt": "NUMBER_THEORETIC_TRANSFORM_NTT",
        "fwht": "FAST_WALSH_HADAMARD_FWHT",
        "convex hull": "MONOTONE_CHAIN_CONVEX_HULL",
        "hld": "HEAVY_LIGHT_DECOMPOSITION_HLD",
        "tree decomposition": "CENTROID_DECOMPOSITION_TREE",
        "matrix exp": "MATRIX_EXPONENTIATION",
        "sieve": "LINEAR_SIEVE_PRIME_FACTORIZATION",
        "hash": "SPLITMIX64_ANTI_HASH",
        "sliding window": "MONOTONIC_DEQUE_SLIDING_WINDOW",
        "two pointer": "TWO_POINTER_SLIDING_WINDOW",
        "knuth": "KNUTH_OPTIMIZATION_DP",
        "cht": "CONVEX_HULL_TRICK_CHILE_CHAO",
    }

    for key, gid in mapping.items():
        if key in q and gid not in genes:
            genes.append(gid)

    return genes


def splice_dna(gene_ids: list[str], task_title: str = "Competitive Programming Task") -> str:
    """Splices dominant allele code templates into standard C++ boilerplate."""
    all_genes = load_all_genes()

    header_scaffolding = """#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <queue>
#include <deque>
#include <stack>
#include <bitset>
#include <iomanip>
#include <cassert>
#include <chrono>

using namespace std;

// --- Types & Aliases ---
using ll = long long;
using ull = unsigned long long;
using ld = long double;
using pii = pair<int, int>;
using pll = pair<ll, ll>;
using vi = vector<int>;
using vll = vector<ll>;
using vpii = vector<pii>;
using vpll = vector<pll>;

// --- Constants ---
constexpr int INF = 1e9 + 7;
constexpr ll INF64 = 1e18 + 7;
constexpr int MOD = 1e9 + 7;
constexpr int MOD9 = 998244353;
constexpr ld EPS = 1e-9;

// --- Macros ---
#define all(x) (x).begin(), (x).end()
#define rall(x) (x).rbegin(), (x).rend()
#define sz(x) static_cast<int>((x).size())
"""

    pragmas: list[str] = []
    structures: list[str] = []
    metadata_notes: list[str] = []

    for gid in gene_ids:
        g = all_genes.get(gid)
        if not g:
            continue

        allele = get_dominant_allele(g)
        if not allele:
            continue

        aid = allele.get("allele_id", "default")
        code = allele.get("code_template", "").strip()
        fitness = allele.get("empirical_fitness", {})
        rt = fitness.get("runtime_ms", "N/A")
        ram = fitness.get("ram_kb", "N/A")

        metadata_notes.append(
            f"// [Ultimatrix Gene: {gid}] -> Allele '{aid}' (Dominance: {allele.get('dominance')}, {rt}ms, {ram}KB)"
        )

        if code.startswith("#pragma GCC"):
            pragmas.append(code)
        elif gid == "FAST_IO_STREAM_UNTIE":
            # Handled in main()
            pass
        else:
            # Strip redundant `#pragma once` or `#include` lines from individual gene structures
            cleaned_lines = []
            for line in code.splitlines():
                stripped = line.strip()
                if stripped.startswith("#pragma once"):
                    continue
                if stripped.startswith("#include <") and ">" in stripped:
                    continue
                cleaned_lines.append(line)
            clean_code = "\n".join(cleaned_lines).strip()
            if clean_code:
                structures.append(f"// --- Begin Gene: {gid} ({aid}) ---\n{clean_code}\n// --- End Gene: {gid} ---")

    # Assemble complete C++ code
    out_lines = []
    out_lines.append(f"// ==========================================================")
    out_lines.append(f"//  ULTIMATRIX SYNTHESIZED DNA STREAM: {task_title}")
    out_lines.append(f"//  Assembled by Azmuth Autonomous DNA Splicer (Phase 2)")
    out_lines.append(f"// ==========================================================")
    out_lines.extend(metadata_notes)
    out_lines.append("")

    if pragmas:
        out_lines.extend(pragmas)
        out_lines.append("")

    out_lines.append(header_scaffolding)

    if structures:
        out_lines.append("// ==========================================================")
        out_lines.append("//  SPLICED ALGORITHMIC STRUCTURES & LOGIC")
        out_lines.append("// ==========================================================")
        out_lines.append("\n\n".join(structures))
        out_lines.append("")

    # Solve function and main driver
    out_lines.append("""// ==========================================================
//  TASK LOGIC
// ==========================================================
void solve() {
    // Spliced structures are declared above and ready for immediate deployment.
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    int t = 1;
    // cin >> t; // Uncomment if multi-testcase task
    while (t--) {
        solve();
    }
    return 0;
}
""")

    return "\n".join(out_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Azmuth Ultimatrix DNA Splicer")
    parser.add_argument("--task", type=str, help="Problem slug from CS Academy or HackerRank")
    parser.add_argument("--query", type=str, help="Natural language or comma-separated constraints/keywords")
    parser.add_argument("--genes", type=str, help="Comma-separated list of exact Gene IDs")
    parser.add_argument("--output", type=str, help="Path to write generated C++ file (defaults to stdout)")

    args = parser.parse_args()

    gene_ids: list[str] = []
    title = "Generic Algorithmic Challenge"

    if args.task:
        title = f"Task: {args.task}"
        gene_ids = resolve_genes_for_task(args.task)
    elif args.query:
        title = f"Query: {args.query}"
        gene_ids = resolve_genes_from_query(args.query)
    elif args.genes:
        title = f"Custom Gene Strand"
        gene_ids = [g.strip().upper() for g in args.genes.split(",") if g.strip()]
    else:
        # Default sample run
        title = "Demo Splicing: Graph Shortest Path with DSU"
        gene_ids = ["FAST_IO_STREAM_UNTIE", "DISJOINT_SET_UNION", "DIJKSTRA_SHORTEST_PATH"]

    code = splice_dna(gene_ids, task_title=title)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(code, encoding="utf-8")
        logger.info(f"Successfully spliced {len(gene_ids)} genes into {out_path}")
    else:
        print(code)


if __name__ == "__main__":
    main()

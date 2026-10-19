"""Canonical Ecosystem Name Mapping & Indirection Resolver Engine.

Provides high-speed (<2ms) deterministic resolution of repository names,
aliases, physical disk paths, GitHub remotes, and Azmuth universe bindings
across Aaradhya's tool ecosystem.

Eliminates filesystem path discrepancies (e.g. 'spark' vs 'SPARK', 'fleet' vs 'Fleet-Orchestrator')
without requiring physical directory renames.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


@dataclass
class ResolvedEcosystemTarget:
    canonical_name: str
    display_name: str
    local_path: Path
    exists_on_disk: bool
    github_repo: str
    azmuth_universe: str
    category: str
    aliases: List[str]


class EcosystemResolver:
    """High-speed path and repository identity resolver."""

    def __init__(self, schema_path: Path | None = None):
        if schema_path is None:
            # Default to local schema in Fleet-Orchestrator
            schema_path = Path(__file__).resolve().parent.parent / "schemas" / "ecosystem.names.json"
        self.schema_path = schema_path
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}
        self._root_dir = Path("F:/Aaradhya-Dev-Tamrakar")
        self._load_registry()

    def _load_registry(self) -> None:
        if not self.schema_path.exists():
            return
        with open(self.schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._root_dir = Path(data.get("root_directory", "F:/Aaradhya-Dev-Tamrakar"))
        self._registry = data.get("canonical_registry", {})

        for c_name, meta in self._registry.items():
            self._alias_map[c_name.lower()] = c_name
            self._alias_map[meta.get("display_name", "").lower()] = c_name
            folder = meta.get("default_folder_name", "")
            if folder:
                self._alias_map[folder.lower()] = c_name
                self._alias_map[Path(folder).name.lower()] = c_name

            for alias in meta.get("aliases", []):
                self._alias_map[alias.lower()] = c_name

    def resolve(self, query: str) -> Optional[ResolvedEcosystemTarget]:
        """Resolve any folder, slug, alias, or path into its canonical target."""
        if not query:
            return None

        # Clean query
        q_clean = query.strip()
        # If it's a full path, extract basename or match folder
        p = Path(q_clean)
        lookup_key = p.name.lower() if len(p.parts) > 1 else q_clean.lower()

        canonical_key = self._alias_map.get(lookup_key)
        if not canonical_key:
            # Try direct lowercase
            canonical_key = self._alias_map.get(q_clean.lower().replace("-", "").replace("_", ""))

        if not canonical_key or canonical_key not in self._registry:
            # If not in registry, fallback to raw directory check under root
            candidate_path = self._root_dir / q_clean
            if candidate_path.exists():
                return ResolvedEcosystemTarget(
                    canonical_name=q_clean.lower(),
                    display_name=q_clean,
                    local_path=candidate_path,
                    exists_on_disk=True,
                    github_repo="",
                    azmuth_universe="u0_ecosystem_mesh",
                    category="unregistered",
                    aliases=[q_clean],
                )
            return None

        entry = self._registry[canonical_key]
        rel_folder = entry.get("default_folder_name", canonical_key)
        full_path = self._root_dir / rel_folder

        return ResolvedEcosystemTarget(
            canonical_name=entry.get("canonical_name", canonical_key),
            display_name=entry.get("display_name", canonical_key),
            local_path=full_path,
            exists_on_disk=full_path.exists(),
            github_repo=entry.get("github_repo", ""),
            azmuth_universe=entry.get("azmuth_universe", "u0_ecosystem_mesh"),
            category=entry.get("category", "general"),
            aliases=entry.get("aliases", []),
        )

    def list_all_targets(self) -> List[ResolvedEcosystemTarget]:
        """Enumerate all registered canonical targets."""
        results = []
        for c_name in self._registry:
            target = self.resolve(c_name)
            if target:
                results.append(target)
        return results


def run_resolver_cli() -> None:
    """CLI to inspect repository resolutions."""
    import argparse
    parser = argparse.ArgumentParser(description="Canonical Ecosystem Resolver CLI")
    parser.add_argument("query", nargs="?", help="Repository name, folder, or alias to resolve")
    parser.add_argument("--all", action="store_true", help="List all canonical mappings")
    args = parser.parse_args()

    resolver = EcosystemResolver()

    if args.all or not args.query:
        print("=" * 80)
        print("  🌐 AARADHYA ECOSYSTEM CANONICAL NAME REGISTRY")
        print("=" * 80)
        targets = resolver.list_all_targets()
        for t in targets:
            status = "✅ OK" if t.exists_on_disk else "⚠️ MISSING"
            print(f"[{t.canonical_name}] {t.display_name}")
            print(f"  • Path:       {t.local_path} ({status})")
            print(f"  • Remote:     https://github.com/{t.github_repo}")
            print(f"  • Universe:   {t.azmuth_universe}")
            print(f"  • Aliases:    {', '.join(t.aliases[:4])}")
            print("-" * 80)
        print(f"Total Canonical Entries: {len(targets)}")
        return

    target = resolver.resolve(args.query)
    if not target:
        print(f"[-] Could not resolve query '{args.query}'.")
        return

    print("=" * 80)
    print(f"  RESOLVED TARGET: {target.canonical_name.upper()}")
    print("=" * 80)
    print(f"- Display Name:   {target.display_name}")
    print(f"- Local Path:     {target.local_path} (Exists: {target.exists_on_disk})")
    print(f"- GitHub Repo:    {target.github_repo}")
    print(f"- Azmuth Cart.:   {target.azmuth_universe}")
    print(f"- Category:       {target.category}")
    print(f"- Aliases:        {target.aliases}")
    print("=" * 80)


if __name__ == "__main__":
    run_resolver_cli()

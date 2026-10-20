"""Presentation copy and layered inspectors; no execution or state writes."""

from functools import wraps


VIEW_GUIDES = {
    "pipeline": (
        "Pipeline", "Follow sources through filtering, analysis, and benchmarking.",
        "Select a stage or source to see its purpose and recorded state. Scan GitHub refreshes source data; A100 burst requests cloud work.",
    ),
    "dag": (
        "Causal graph (DAG)", "Explore directed relationships between monitored signals.",
        "Select a signal to inspect its drivers and downstream effects. Shock previews a signal change in this diagram; it does not prove causation.",
    ),
    "genes": (
        "Gene lab", "Compare reusable algorithms (genes) and their implementation variants (alleles).",
        "Select a gene or variant to inspect benchmarks and lineage. Mutate and race creates variants and runs local comparisons. T0–T5 are catalogue categories, not quality scores.",
    ),
    "ingestion": (
        "Ingestion", "Review recorded incoming activity and its analysis routes.",
        "Select an event to inspect its source, time, and recorded outcome. An event is a ledger record, not proof that a job is currently running. A100 burst requests cloud work.",
    ),
}

OPERATIONS_GUIDE = (
    "Operating modes\n"
    "Whisper: 5-minute idle requirement, 30-minute burst cooldown, 1 task per burst.\n"
    "Balanced: 3-minute idle requirement, 5-minute cooldown, 1 task per burst.\n"
    "Turbo: 45-second idle requirement, 30-second cooldown, up to 3 tasks per burst.\n"
    "Modes update the daemon's local configuration. RAM safeguards may downshift the mode. Pause controls daemon scheduling; use Cancel job for the GUI's active job.\n\n"
    "Signal threshold (|Z|)\n"
    "Sets the signal threshold used by the diagram and DAG synthesis. Higher values show fewer signals. Z is the signal's deviation score; it is not a probability or confidence percentage.\n\n"
    "Counts and freshness\n"
    "Token count: configured entries observed in the GitHub sensor pool; health and usable capacity are unknown unless measured.\n"
    "Genes: loaded catalogue entries. Mutations: mutations_applied in the mutation ledger. Benchmarks: tournaments_run in the arena ledger. These are recorded totals, not active jobs.\n"
    "Ledgers refresh every two seconds. Updated shows the last successful refresh; stale retains the last good data.\n\n"
    "Actions\n"
    "Scan GitHub reads external GitHub data and updates its local cache. Synthesize DAG updates local analysis. Harvest task collects algorithm material and updates the local catalogue; it may read external sources. Verify cycle reconciles files and can call Gemini and apply generated repairs when gaps are found. A100 burst starts the cloud burst launcher.\n"
    "Job details retain captured output and failures. Stopping waiting for an in-process job leaves it executing and blocks conflicting actions until it ends."
)


def layered_inspector(renderer):
    """Keep existing tagged technical rendering behind a consistent summary."""
    @wraps(renderer)
    def render(self, *args, **kwargs):
        key = (renderer.__name__, repr(args), repr(kwargs))
        same = getattr(self, "_detail_key", None) == key
        scroll = self.inspector_text.yview()[0] if same else 0.0
        renderer(self, *args, **kwargs)
        self._layer_inspector(key, args)
        self.inspector_text.yview_moveto(scroll)
    return render

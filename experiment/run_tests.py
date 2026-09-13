"""Run the bounded embedding experiments; save exact transcripts and metadata."""
import json
from pathlib import Path
import platform
import subprocess

here = Path(__file__).resolve().parent
results = {"platform": platform.platform(), "runs": []}
results["upstream_commit"] = subprocess.check_output(
    ["git", "-C", str(here.parent / "gprolog"), "rev-parse", "HEAD"], text=True).strip()
for repetition in range(1, 21):
    for mode in ("nested", "processes"):
        run = subprocess.run([str(here / "controller"), mode],
                             capture_output=True, text=True, timeout=25, check=True)
        expected = ("PASS nested queries: a1 b1 b2 a2 (LIFO)" if mode == "nested"
                    else "PASS independent processes: a1 b1 a2 b2 (non-LIFO)")
        if run.stderr or not run.stdout.rstrip().endswith(expected):
            raise RuntimeError(f"Unexpected result: {run.stdout}\n{run.stderr}")
        results["runs"].append(dict(repetition=repetition, mode=mode,
                                    stdout=run.stdout, returncode=run.returncode))
(here / "results.json").write_text(json.dumps(results, indent=2) + "\n")
print("PASS: 40 runs (20 nested-query + 20 independent-process)")

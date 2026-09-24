"""Live progress bar for a GAN fine-tuning run. Run it in your own terminal:

    cd G:\\Capstone\\backend
    .venv\\Scripts\\python.exe scripts\\watch_training.py

Repaints in place roughly once a second. Ctrl+C to stop watching -- it only
reads the log, so stopping this never touches the training run itself.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

STEP_RE = re.compile(r"^step (\d+)/(\d+)\s+d_loss=([\d.eE+-]+)\s+g_loss=([\d.eE+-]+)(?:\s+r1=([\d.eE+-]+))?")
EVAL_RE = re.compile(r"\[eval\] step (\d+).*?FID=([\d.]+|None)")

BAR_WIDTH = 44


def human(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:
        return "--"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def parse(log: Path):
    step = total = 0
    d_loss = g_loss = r1 = "-"
    evals: list[tuple[int, str]] = []
    try:
        text = log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in text.splitlines():
        m = STEP_RE.match(line)
        if m:
            step, total = int(m.group(1)), int(m.group(2))
            d_loss, g_loss = m.group(3), m.group(4)
            r1 = m.group(5) or "-"
            continue
        e = EVAL_RE.search(line)
        if e:
            evals.append((int(e.group(1)), e.group(2)))
    return step, total, d_loss, g_loss, r1, evals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=str(Path(__file__).resolve().parents[1] / "storage" / "models" / "finetune_run.log"))
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    log = Path(args.log)
    # (timestamp, step) samples for a rolling rate, so the ETA reflects the
    # last few minutes rather than an average dragged down by startup.
    samples: list[tuple[float, int]] = []
    printed_lines = 0

    while True:
        parsed = parse(log)
        if parsed is None:
            sys.stdout.write(f"\rwaiting for {log} ...")
            sys.stdout.flush()
            time.sleep(args.interval)
            continue

        step, total, d_loss, g_loss, r1, evals = parsed
        now = time.time()
        if not samples or samples[-1][1] != step:
            samples.append((now, step))
        samples = [s for s in samples if now - s[0] <= 300] or samples[-1:]

        rate = eta = float("nan")
        if len(samples) >= 2 and samples[-1][1] > samples[0][1]:
            rate = (samples[-1][0] - samples[0][0]) / (samples[-1][1] - samples[0][1])
            eta = rate * max(total - step, 0)

        frac = step / total if total else 0.0
        filled = int(frac * BAR_WIDTH)
        bar = "#" * filled + "-" * (BAR_WIDTH - filled)

        trend = ""
        if len(evals) >= 2:
            scored = [(s, float(v)) for s, v in evals if v != "None"]
            if len(scored) >= 2:
                delta = scored[-1][1] - scored[-2][1]
                trend = f"  {'DOWN (good)' if delta < 0 else 'UP (worse)'} {delta:+.1f}"

        lines = [
            f"[{bar}] {frac*100:5.1f}%   step {step}/{total}",
            f"  d_loss={d_loss:<10} g_loss={g_loss:<10} r1={r1}",
            f"  {rate:.2f}s/step   elapsed-rate ETA {human(eta)}",
            f"  FID: " + (" -> ".join(f"{s}:{v}" for s, v in evals[-6:]) if evals else "(none yet)") + trend,
        ]

        # Repaint in place: jump back up over what we printed last time.
        if printed_lines:
            sys.stdout.write(f"\033[{printed_lines}A")
        for line in lines:
            sys.stdout.write("\033[2K" + line + "\n")
        sys.stdout.flush()
        printed_lines = len(lines)

        if step and total and step >= total:
            print("\nrun complete")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped watching (training is unaffected)")

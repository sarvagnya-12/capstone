"""Live progress view for an ESRGAN training run (app/ml/sr/train_esrgan.py).
Run it in your own terminal:

    cd G:\\Capstone\\backend
    .venv\\Scripts\\python.exe scripts\\watch_esrgan.py

Repaints in place every couple of seconds. Ctrl+C to stop watching -- it only
reads the log and metrics files, so stopping this never touches training.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
STEP_RE = re.compile(r"^step (\d+)/(\d+)\s+(psnr|gan)\s+(.*?)\s+([\d.]+) s/step(?:\s+vram ([\d.]+)GB)?")
LOSS_RE = re.compile(r"(\w+)=([\d.eE+-]+)")
PHASE_RE = re.compile(r"=> ([\d,]+) PSNR steps \+ ([\d,]+) GAN steps")
BAR_WIDTH = 40


def human(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:
        return "--"
    h, rem = divmod(int(seconds), 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}m"


def bar(done: int, total: int) -> str:
    frac = min(done / total, 1.0) if total else 0.0
    filled = int(frac * BAR_WIDTH)
    return f"[{'#' * filled}{'-' * (BAR_WIDTH - filled)}] {frac * 100:5.1f}%  {done:,}/{total:,}"


def read_state(log: Path):
    try:
        text = log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    state = {"step": 0, "total": 0, "psnr_steps": 0, "gan_steps": 0, "phase": "starting",
             "losses": {}, "sps": {}, "vram": "-", "done": "done. weights in" in text}
    for line in text.splitlines():
        if m := PHASE_RE.search(line):
            state["psnr_steps"] = int(m.group(1).replace(",", ""))
            state["gan_steps"] = int(m.group(2).replace(",", ""))
        elif m := STEP_RE.match(line):
            state["step"], state["total"], state["phase"] = int(m.group(1)), int(m.group(2)), m.group(3)
            state["losses"] = dict(LOSS_RE.findall(m.group(4)))
            state["sps"][m.group(3)] = float(m.group(5))
            state["vram"] = m.group(6) or "-"
    return state


def read_metrics(path: Path) -> list[dict]:
    try:
        with path.open(newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def render(state, metrics, gan_sps_guess: float, log: Path) -> str:
    lines = [f"ESRGAN training  --  {log}", ""]
    if state is None:
        return "\n".join(lines + ["waiting for log file..."])

    step, psnr_steps, gan_steps = state["step"], state["psnr_steps"], state["gan_steps"]
    total = state["total"] or (psnr_steps + gan_steps)
    psnr_sps = state["sps"].get("psnr", 0.0)
    gan_sps = state["sps"].get("gan", gan_sps_guess)
    remaining = max(psnr_steps - step, 0) * psnr_sps + min(gan_steps, total - max(step, psnr_steps)) * gan_sps

    lines.append(f"Overall    {bar(step, total)}")
    lines.append(f"L1 phase   {bar(min(step, psnr_steps), psnr_steps)}")
    lines.append(f"GAN phase  {bar(max(step - psnr_steps, 0), gan_steps)}")
    lines.append("")
    status = "FINISHED" if state["done"] else f"{state['phase'].upper()} phase"
    gan_note = "" if "gan" in state["sps"] else f" (GAN est. {gan_sps_guess})"
    lines.append(f"{status}   speed {state['sps'].get(state['phase'], 0):.3f} s/step{gan_note}   "
                 f"vram {state['vram']}GB   time left ~{human(0 if state['done'] else remaining)}")
    if state["losses"]:
        lines.append("losses: " + "  ".join(f"{k}={v}" for k, v in state["losses"].items()))

    lines += ["", f"{'validation':<12}{'PSNR':>8}{'SSIM':>9}{'VGG dist':>10}   (PSNR/SSIM higher, VGG lower = better)"]
    for row in metrics[-8:] if len(metrics) <= 8 else metrics[:1] + metrics[-7:]:
        lines.append(f"{row['step']:<12}{float(row['psnr']):>8.2f}{float(row['ssim']):>9.4f}{float(row['vgg_distance']):>10.3f}")
    lines += ["", "Ctrl+C stops watching only; training keeps running."]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-name", default="shoes512")
    parser.add_argument("--log", type=Path, help="Defaults to storage/esrgan/<run>_train.log")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--gan-sps", type=float, default=0.66,
                        help="Assumed GAN-phase s/step until it is measured (0.66 on the RTX 4050 at batch 16)")
    parser.add_argument("--once", action="store_true", help="Print once and exit")
    args = parser.parse_args()

    log = args.log or BACKEND_ROOT / "storage" / "esrgan" / f"{args.run_name}_train.log"
    metrics_path = BACKEND_ROOT / "storage" / "esrgan" / "results" / args.run_name / "metrics.csv"

    try:
        while True:
            screen = render(read_state(log), read_metrics(metrics_path), args.gan_sps, log)
            if args.once:
                print(screen)
                return 0
            sys.stdout.write("\x1b[2J\x1b[H" + screen + "\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

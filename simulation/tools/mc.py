"""Monte Carlo local search on die positions, exact 64-grid checks, real score objective.

Each try jitters every die by a uniform random offset in [-jitter, +jitter] mm around the CURRENT BEST,
keeps only layouts that pass every rule, scores them on the three binding workloads
(skewed_compute, tensor_training, memory_stream) at the official 64 x 64 mesh, and moves the best when a
try scores lower. Score = max((GPU-25)/(104.59-25), (HBM-25)/(97.68-25)).

Usage: mc.py start.json --jitter 0.5 --evals 40 --seed 1 --log out.jsonl [--dies G0,H3,...] [--shrink 0.5]
--shrink multiplies the jitter every time 8 tries in a row fail to improve (default: no shrink).
Writes <log>.best.json on every improvement. Needs CRYO_HILL pointing at a clone of
github.com/Czaja107/chiplet-thermal-simulator and fast.py next to this file."""
import json, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import fast

REFG, REFH, AMB = 104.59, 97.68, 25.0
WLS = ["skewed_compute", "tensor_training", "memory_stream"]


def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


start = json.loads(Path(sys.argv[1]).read_text())["placements_mm"]
jitter = arg("--jitter", 0.5, float)
budget = arg("--evals", 40, int)
seed = arg("--seed", 1, int)
shrink = arg("--shrink", 1.0, float)
dies = arg("--dies", ",".join(start)).split(",")
log = Path(arg("--log", f"mc_s{seed}.jsonl"))
rng = random.Random(seed)


def score(res):
    gpu = max(v for p in res["peaks"].values() for d, v in p.items() if d[0] == "G")
    hbm = max(v for p in res["peaks"].values() for d, v in p.items() if d[0] == "H")
    return max((gpu - AMB) / (REFG - AMB), (hbm - AMB) / (REFH - AMB)), gpu, hbm


def evaluate(lay, note, n):
    res = fast.estimate(lay, 64, workers=2, workloads=WLS)
    s, gpu, hbm = score(res)
    with log.open("a") as f:
        f.write(json.dumps({"n": n, "seed": seed, "note": note, "score": s, "gpu": gpu, "hbm": hbm,
                            "peaks": res["peaks"], "layout": lay, "t": round(time.time() - t0)}) + "\n")
    print(f"[{n}/{budget}] {note:14s} score {s:.5f} gpu {gpu:.2f} hbm {hbm:.2f} ({time.time()-t0:.0f}s)", flush=True)
    return s


t0 = time.time()
best_lay = {d: [round(x, 3), round(y, 3)] for d, (x, y) in start.items()}
best = evaluate(best_lay, "start", 1)
Path(str(log) + ".best.json").write_text(json.dumps({"placements_mm": best_lay, "score": best}, indent=1))
n, fails, tries = 1, 0, 0
while n < budget:
    cand = dict(best_lay)
    for d in dies:
        cand[d] = [round(best_lay[d][0] + rng.uniform(-jitter, jitter), 3), round(best_lay[d][1] + rng.uniform(-jitter, jitter), 3)]
    tries += 1
    if not fast.legal(cand)[0]:
        continue
    n += 1
    s = evaluate(cand, f"jitter {jitter:.2f}", n)
    if s < best - 1e-6:
        best, best_lay, fails = s, cand, 0
        Path(str(log) + ".best.json").write_text(json.dumps({"placements_mm": best_lay, "score": best}, indent=1))
    else:
        fails += 1
        if shrink < 1 and fails >= 8:
            jitter, fails = round(jitter * shrink, 3), 0
print(json.dumps({"best_score": best, "evals": n, "legal_tries": tries, "layout": best_lay}))

#!/usr/bin/env bash
# Regenerate every number, table and figure of the paper from the data in this package.
# Needs only Python; no benchmark run, no special hardware.
set -e
cd "$(dirname "$0")"
mkdir -p phaseR

echo "[1/3] analyse_rev5_main.py  -- ratios, interaction deltas, bootstrap  (~1 min)"
python3 analyse_rev5_main.py > phaseR/stage1.log

echo "[2/3] pooling and sensitivity analyses                                (~15 min)"
echo "      skip with:  SKIP_SLOW=1 ./reproduce.sh   (uses the shipped intermediate JSON)"
if [ "${SKIP_SLOW:-0}" != "1" ]; then
  python3 analyse_rev6.py      > phaseR/stage2a.log
  python3 analyse_rev6_pool.py > phaseR/stage2b.log
  python3 analyse_rev7.py      > phaseR/stage2c.log
fi

echo "[3/3] make_rev5_tex.py      -- numbers.tex, the seven tables, the figures"
python3 make_rev5_tex.py

echo
echo "Done. Outputs are in rev5/ : numbers.tex and tab_*.tex."

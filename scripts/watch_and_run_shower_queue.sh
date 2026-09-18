#!/usr/bin/env bash
# Guard: wait for the in-flight 6asin resume (PID or progress) to finish,
# then start the full sequential queue (6asin skip-fast -> journey -> rank x3).
set -u
cd "$(dirname "$0")/.." || exit 1
echo "===== GUARD start $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log

# 1) wait until survey-shower-liner-6asin-n1000 reaches 1000 completed
for i in $(seq 1 300); do
  C=$(.venv/bin/python -c "
import json
try:
    r = json.load(open('jobs/survey-shower-liner-6asin-n1000/result.json'))
    print(r['stats']['n_completed_trials'])
except Exception:
    print(0)
" 2>/dev/null)
  if [ "${C:-0}" -ge 1000 ]; then
    echo "===== GUARD: 6asin reached 1000 at $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log
    break
  fi
  sleep 60
done

# 2) small settle so the finishing matraix process releases the job dir
sleep 10
# 3) start the sequential queue (6asin is complete -> first run_job is a no-op)
nohup bash scripts/run_shower_liner_queue.sh >> logs/queue_shower_liner.log 2>&1 &
echo "===== GUARD: queue relaunched PID=$! $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log

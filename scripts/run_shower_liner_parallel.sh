#!/usr/bin/env bash
# Parallel execution of the remaining shower-liner jobs (each n_concurrent=30).
# 6asin shelf-choice is already running separately; this starts journey + rank x3
# in parallel. Run with nohup so it survives session turns.
set -u
cd "$(dirname "$0")/.." || exit 1
export $(grep DEEPSEEK_API_KEY .env | xargs)

run_job() {
  local job=$1 task=$2
  echo "===== START $job $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log
  export MATRIX_SURVEY_TASK_PATH="$task"
  rm -f "jobs/$job/lock.json"
  .venv/bin/matraix run -c "configs/jobs/application-task-job-recipe/$job.yaml" --max-cost-usd 12 >> "logs/queue_shower_liner.log" 2>&1
  echo "===== DONE  $job $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log
}

run_job survey-shower-liner-journey-n1000 application/tasks/survey_shower-liner-6asin-journey &
P1=$!
run_job survey-shower-liner-rank-a-first-n1000 application/tasks/survey_shower-liner-6asin-rank-a-first &
P2=$!
run_job survey-shower-liner-rank-c-first-n1000 application/tasks/survey_shower-liner-6asin-rank-c-first &
P3=$!
run_job survey-shower-liner-rank-f-first-n1000 application/tasks/survey_shower-liner-6asin-rank-f-first &
P4=$!

wait $P1 $P2 $P3 $P4
echo "===== PARALLEL QUEUE COMPLETE $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log

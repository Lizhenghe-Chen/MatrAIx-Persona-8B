#!/usr/bin/env bash
# Run the 3 rank-position arms in parallel (journey already done).
set -u
cd "$(dirname "$0")/.." || exit 1
export $(grep DEEPSEEK_API_KEY .env | xargs)

run_job() {
  local job=$1 task=$2
  echo "===== START $job $(date '+%H:%M:%S') =====" >> logs/queue_rank.log
  export MATRIX_SURVEY_TASK_PATH="$task"
  rm -f "jobs/$job/lock.json"
  .venv/bin/matraix run -c "configs/jobs/application-task-job-recipe/$job.yaml" --max-cost-usd 12 >> "logs/rank_$job.log" 2>&1
  echo "===== DONE  $job $(date '+%H:%M:%S') =====" >> logs/queue_rank.log
}

run_job survey-shower-liner-rank-a-first-n1000 application/tasks/survey_shower-liner-6asin-rank-a-first &
P1=$!
run_job survey-shower-liner-rank-c-first-n1000 application/tasks/survey_shower-liner-6asin-rank-c-first &
P2=$!
run_job survey-shower-liner-rank-f-first-n1000 application/tasks/survey_shower-liner-6asin-rank-f-first &
P3=$!

wait $P1 $P2 $P3
echo "===== RANK QUEUE COMPLETE $(date '+%H:%M:%S') =====" >> logs/queue_rank.log

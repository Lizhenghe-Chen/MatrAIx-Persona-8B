#!/usr/bin/env bash
# Sequential execution queue for the shower-liner experiment suite.
# Each job runs with n_concurrent_trials=30 (from its YAML) and is waited to
# completion before the next starts. Run with nohup so it survives session turns.
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

# 0) resume the shelf-choice job (continues from existing trials)
run_job survey-shower-liner-6asin-n1000 application/tasks/survey_shower-liner-6asin

# 1) journey
run_job survey-shower-liner-journey-n1000 application/tasks/survey_shower-liner-6asin-journey

# 2) rank-position arms
run_job survey-shower-liner-rank-a-first-n1000 application/tasks/survey_shower-liner-6asin-rank-a-first
run_job survey-shower-liner-rank-c-first-n1000 application/tasks/survey_shower-liner-6asin-rank-c-first
run_job survey-shower-liner-rank-f-first-n1000 application/tasks/survey_shower-liner-6asin-rank-f-first

echo "===== QUEUE COMPLETE $(date '+%H:%M:%S') =====" >> logs/queue_shower_liner.log

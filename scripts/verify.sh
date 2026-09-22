#!/usr/bin/env bash
set -euo pipefail
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM-offscreen}"

VERIFY_DAYTONA="${VERIFY_DAYTONA-0}"
ALLOW_DAYTONA_MUTATION="${ALLOW_DAYTONA_MUTATION-0}"
VERIFY_CODE_ONLY="${VERIFY_CODE_ONLY-0}"
export GA_VERIFICATION_RUN=1
export GA_VERIFICATION_PROFILE="$([[ "$VERIFY_CODE_ONLY" == "1" ]] && printf code-only || printf full)"
for flag in VERIFY_DAYTONA ALLOW_DAYTONA_MUTATION VERIFY_CODE_ONLY; do
    value="${!flag}"
    if [[ "$value" != "0" && "$value" != "1" ]]; then
        printf '%s must be exactly 0 or 1\n' "$flag" >&2
        exit 1
    fi
done
if [[ "$VERIFY_DAYTONA" != "$ALLOW_DAYTONA_MUTATION" ]]; then
    printf '%s\n' "VERIFY_DAYTONA and ALLOW_DAYTONA_MUTATION must both be 0 or both be 1" >&2
    exit 1
fi
if [[ "$VERIFY_DAYTONA" == "1" ]]; then
    printf '%s\n' "Daytona infrastructure smoke is retired; follow G-PRODUCT for one approved source-bound football acceptance after credential rotation." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
VERIFICATION_DIR="$REPO_ROOT/.verification"
LOG_DIR="$VERIFICATION_DIR/logs"
GATE_RESULTS="$VERIFICATION_DIR/gates.tsv"
export GA_VERIFICATION_SESSION_ID="${GA_VERIFICATION_SESSION_ID-$(date -u +%Y%m%dT%H%M%S)-$$}"

unsafe_log_path() {
    printf 'unsafe verification log path: %s\n' "$1" >&2
    exit 1
}

if [[ -L "$VERIFICATION_DIR" ]] || [[ -e "$VERIFICATION_DIR" && ! -d "$VERIFICATION_DIR" ]]; then
    unsafe_log_path "$VERIFICATION_DIR"
fi
mkdir -p -- "$VERIFICATION_DIR"
VERIFICATION_PHYSICAL="$(cd -P -- "$VERIFICATION_DIR" && pwd)"
if [[ "$VERIFICATION_PHYSICAL" != "$VERIFICATION_DIR" ]]; then
    unsafe_log_path "$VERIFICATION_DIR"
fi
rm -f -- "$VERIFICATION_DIR/receipt.json"

if [[ -L "$LOG_DIR" ]] || [[ -e "$LOG_DIR" && ! -d "$LOG_DIR" ]]; then
    unsafe_log_path "$LOG_DIR"
fi
mkdir -p -- "$LOG_DIR"
LOG_PHYSICAL="$(cd -P -- "$LOG_DIR" && pwd)"
if [[ "$LOG_PHYSICAL" != "$VERIFICATION_PHYSICAL/logs" ]]; then
    unsafe_log_path "$LOG_DIR"
fi
rm -f "$LOG_DIR"/*.log
if [[ -L "$GATE_RESULTS" ]] || [[ -e "$GATE_RESULTS" && ! -f "$GATE_RESULTS" ]]; then
    unsafe_log_path "$GATE_RESULTS"
fi
: > "$GATE_RESULTS"
cd "$REPO_ROOT"
GATE_SOURCE_COMMIT="$(git rev-parse HEAD)"

fail_gate() {
    local gate="$1"
    local command="$2"
    local detail="${3:-command exited nonzero}"
    printf 'FAILED gate: %s (%s)\n' "$gate" "$detail" >&2
    printf 'Corrective command: %s\n' "$command" >&2
    exit 1
}

run_gate() {
    local gate="$1"
    local command="$2"
    local log="$LOG_DIR/$gate.log"
    local -a pipeline_status

    printf '==> %s\n' "$gate"
    printf 'Command: %s\n' "$command"
    set +e
    bash -c "$command" 2>&1 | tee "$log"
    pipeline_status=("${PIPESTATUS[@]}")
    set -e
    if (( pipeline_status[1] != 0 )); then
        fail_gate "$gate" "$command" "log writer exit ${pipeline_status[1]}"
    fi
    if (( pipeline_status[0] != 0 )); then
        fail_gate "$gate" "$command" "exit ${pipeline_status[0]}"
    fi
    touch -- "$log"
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$GA_VERIFICATION_SESSION_ID" "$GATE_SOURCE_COMMIT" "$gate" \
        "${pipeline_status[0]}" "$command" >> "$GATE_RESULTS"
}

BACKEND_COMMAND="python3 -m pytest -q backend/tests"
CODE_ONLY_EXCLUSIONS="$REPO_ROOT/backend/tests/code_only_exclusions.txt"
if [[ "$VERIFY_CODE_ONLY" == "1" ]]; then
    while IFS= read -r test_file; do
        [[ -z "$test_file" || "$test_file" == \#* ]] && continue
        BACKEND_COMMAND+=" --ignore=$test_file"
    done < "$CODE_ONLY_EXCLUSIONS"
fi
run_gate "backend" "$BACKEND_COMMAND"

SIDECAR_COMMAND="python3 -m pytest -q research-addon/tests"
run_gate "sidecar" "$SIDECAR_COMMAND"

FRONTEND_TEST_COMMAND="npm --prefix frontend test -- --run"
run_gate "frontend-tests" "$FRONTEND_TEST_COMMAND"

run_gate "lint" "npm --prefix frontend run lint"
run_gate "typecheck-app" "cd frontend && npx tsc -p tsconfig.app.json --noEmit --incremental false"
run_gate "typecheck-node" "cd frontend && npx tsc -p tsconfig.node.json --noEmit --incremental false"
run_gate "build" "npm --prefix frontend run build"
run_gate "backend-startup" "python3 -c 'from backend.app.main import app'"
if [[ "$VERIFY_CODE_ONLY" == "1" ]]; then
    run_gate "prod-audit" "npm --prefix frontend audit --omit=dev --audit-level=high"
    python3 -m backend.scripts.write_lane_receipt
    printf '%s\n' "Code-only verification passed; restore documented artifacts before running release gates."
    exit 0
fi
run_gate "manifest" "python3 -m pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py"
run_gate "runtime-options" "python3 -m pytest -q backend/tests/test_runtime_options.py"
run_gate "preflight-negatives" "python3 -m pytest -q backend/tests/test_release_preflight.py -k reject"
run_gate "prod-audit" "npm --prefix frontend audit --omit=dev --audit-level=high"
rm -f -- "$GATE_RESULTS"
python3 -m backend.scripts.write_verification_evidence --record-verifier-success

printf '%s\n' "Daytona provider operation skipped; G-PRODUCT remains a separate explicitly approved acceptance."

printf 'All required verification gates passed. Logs: %s\n' "$LOG_DIR"

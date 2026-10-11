#!/usr/bin/env bash
# Aqui operator console, one command (T50): the live backend with its warm models, the built console on the
# same origin, and a supervisor that restarts the backend if it dies. From anywhere:
#
#   app/start.sh start   [server args]   build the console if stale, start detached (no-op if already running)
#   app/start.sh status                  PIDs, URL, worker and model state, the question a run waits on
#   app/start.sh stop    [--force]       stop supervisor and backend (refuses while a run is active)
#   app/start.sh restart [--force] [server args]   replace the running backend, managed or not, when idle
#   app/start.sh build                   rebuild the console only; no backend restart needed
#
# Console: http://127.0.0.1:5178/ (also http://127.0.0.1:8788/), /api on the same origin. Server args go to
# app/dev/live_server.py (e.g. --question-timeout 300, --no-landmarks) and are remembered for the next start
# (runs/app/live_server.args; delete it to go back to the defaults).
# Logs: runs/app/live_server.log (backend), runs/app/supervisor.log (starts, exits, restarts), runs/app/build.log.
# Env: AQUI_PORT (8788), AQUI_CONSOLE_PORT (5178), AQUI_NO_BUILD=1 to serve app/dist as it is,
# AQUI_STATE (runs/app) for the pid files and logs of a second, test instance.
# Everything runs from main() on the last line, so editing this file never derails a running supervisor.
set -u
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$SELF")/.." && pwd)"
cd "$ROOT" || exit 1
PORT="${AQUI_PORT:-8788}"
CONSOLE_PORT="${AQUI_CONSOLE_PORT:-5178}"
STATE="${AQUI_STATE:-$ROOT/runs/app}"  # pid files and logs (uploads always go to runs/app/)
case "$STATE" in /*) ;; *) STATE="$ROOT/$STATE" ;; esac
SUP_PID="$STATE/supervisor.pid"
SRV_PID="$STATE/live_server.pid"
STOP_FLAG="$STATE/supervisor.stop"
ARGS_FILE="$STATE/live_server.args"
LOG="$STATE/live_server.log"
SUP_LOG="$STATE/supervisor.log"
PY="$ROOT/.venv/bin/python"

note() { printf '[supervisor %s] %s\n' "$(date '+%F %T')" "$*" >> "$SUP_LOG"; }
cmdline() { tr '\0' ' ' < "/proc/$1/cmdline" 2>/dev/null; }
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
is_server() { alive "${1:-}" && cmdline "$1" | grep -q 'app/dev/live_server.py'; }
pid_of() { [ -f "$1" ] && cat "$1" 2>/dev/null; }
server_pid() { local p; p="$(pid_of "$SRV_PID")"; is_server "$p" && echo "$p"; }
port_pid() { ss -ltnpH "sport = :$1" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2; }

# Every supervisor of this port: `bash .../start.sh __supervise <port> ...`. Older ones carried no port and
# belonged to 8788. Found by command line, so a duplicate never hides behind a stale pid file.
supervisors() {
  local pid cmd
  for pid in $(pgrep -f 'start\.sh[^ ]* __supervise' 2>/dev/null); do
    cmd="$(cmdline "$pid")"
    case "$cmd" in bash\ *start.sh*\ __supervise*) ;; *) continue ;; esac
    case "$cmd" in
      *"__supervise $PORT "*) echo "$pid" ;;
      *"__supervise "|*"__supervise --"*) [ "$PORT" = 8788 ] && echo "$pid" ;;
    esac
  done
}

# Why a restart would hurt now: a run not finished, or an evaluation batch driving the server. Empty when idle.
busy() {
  if pgrep -f '[d]rive_warmup.py drive' > /dev/null; then echo "a drive_warmup.py batch is running"; return; fi
  AQUI_JSON="$(curl -s -m 3 "http://127.0.0.1:$PORT/api/runs" 2>/dev/null)" python3 - <<'PY'
import json, os
try:
    runs = json.loads(os.environ["AQUI_JSON"])
except ValueError:
    raise SystemExit
active = ["%s (%s)" % (r.get("run_id"), r.get("status")) for r in runs if r.get("status") not in ("finished", "failed")]
print("active runs: " + ", ".join(active) if active else "")
PY
}

# Rebuild app/dist when a source is newer. Builds into dist.next and swaps, so a failed build never breaks the
# console being served.
build() {
  [ "${AQUI_NO_BUILD:-0}" = 1 ] && return 0
  local index="app/dist/index.html" newer
  if [ -f "$index" ] && [ "${AQUI_FORCE_BUILD:-0}" = 1 ]; then
    echo "Rebuilding app/dist (the running backend serves the new files at once) ..."
  elif [ -f "$index" ]; then
    newer="$(find app/src app/public app/index.html app/package.json app/vite.config.ts design_system/components/src \
             -newer "$index" -type f -print -quit 2>/dev/null)"
    [ -z "$newer" ] && return 0
    echo "Console sources changed ($newer); rebuilding app/dist ..."
  else
    echo "Building the console into app/dist ..."
  fi
  if (cd app && { echo "== build $(date '+%F %T')"; npm run -s prebuild && npx tsc --noEmit \
        && npx vite build --outDir dist.next --emptyOutDir; } >> "$STATE/build.log" 2>&1) \
     && grep -qs '"EquiScene"' app/dist.next/assets/*.js; then  # keepNames: the panorama replaces EquiScene by name
    rm -rf app/dist.prev && { [ ! -d app/dist ] || mv app/dist app/dist.prev; } && mv app/dist.next app/dist
    echo "Console built."
  else
    rm -rf app/dist.next
    if [ -f "$index" ]; then echo "WARNING: console build failed ($STATE/build.log); serving the previous build."
    else echo "WARNING: console build failed ($STATE/build.log); /api works, the page does not."; fi
  fi
}

supervise() {  # runs detached under setsid; restarts the backend whenever it exits, until stop
  shift  # the port marker: it only names this supervisor in ps
  echo $$ > "$SUP_PID"
  rm -f "$STOP_FLAG"
  local child="" code backoff=2 started ran
  trap 'touch "$STOP_FLAG"; is_server "$child" && kill -TERM "$child" 2>/dev/null' TERM INT HUP
  note "supervisor $$ up; live_server.py --port $PORT --console-port $CONSOLE_PORT $*"
  while [ ! -f "$STOP_FLAG" ]; do
    started=$(date +%s)
    "$PY" -u app/dev/live_server.py --port "$PORT" --console-port "$CONSOLE_PORT" "$@" >> "$LOG" 2>&1 < /dev/null &
    child=$!
    echo "$child" > "$SRV_PID"
    note "live server pid $child started"
    while :; do wait "$child"; code=$?; alive "$child" || break; done  # a trapped signal interrupts wait
    [ -f "$STOP_FLAG" ] && { note "live server pid $child stopped (exit $code)"; break; }
    ran=$(( $(date +%s) - started ))
    if [ "$ran" -gt 120 ]; then backoff=2; else backoff=$(( backoff * 2 > 60 ? 60 : backoff * 2 )); fi
    note "live server pid $child exited with $code after ${ran}s; restarting in ${backoff}s"
    sleep "$backoff" & wait $!
  done
  [ "$(pid_of "$SUP_PID")" = "$$" ] && rm -f "$SUP_PID" "$SRV_PID"
  note "supervisor $$ down"
}

start() {
  local sups existing saved
  sups="$(supervisors)"
  if [ -n "$sups" ]; then echo "Already running (supervisor $(echo $sups))."; status; return 0; fi
  existing="$(port_pid "$PORT")"
  if [ -n "$existing" ]; then
    echo "Port $PORT is taken by PID $existing: $(cmdline "$existing")"
    echo "Use 'app/start.sh restart' to replace an idle live server with the supervised one."
    return 1
  fi
  if [ $# -gt 0 ]; then printf '%s\n' "$@" > "$ARGS_FILE"; elif [ -f "$ARGS_FILE" ]; then mapfile -t saved < "$ARGS_FILE"; set -- "${saved[@]}"; fi
  [ -x "$PY" ] || { echo "Missing $PY: run tools/setup_env.sh first."; return 1; }
  build
  rm -f "$STOP_FLAG"
  setsid nohup bash "$SELF" __supervise "$PORT" "$@" >> "$SUP_LOG" 2>&1 < /dev/null &
  for _ in $(seq 1 100); do
    [ -n "$(supervisors)" ] && [ -n "$(server_pid)" ] && break
    sleep 0.1
  done
  for _ in $(seq 1 600); do  # the HTTP port opens after the imports (a few s); models keep warming after that
    curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/api/status" && break
    [ -n "$(server_pid)" ] || break
    sleep 0.5
  done
  status
}

stop_pid() {  # TERM, wait up to 20 s, then KILL; only ever our own supervisor or live server
  local pid="$1" i
  alive "$pid" || return 0
  kill -TERM "$pid" 2>/dev/null
  for i in $(seq 1 40); do alive "$pid" || return 0; sleep 0.5; done
  echo "PID $pid ignored TERM; sending KILL."
  kill -KILL "$pid" 2>/dev/null
}

stop() {
  local force=0 reason sups srv other pid
  [ "${1:-}" = "--force" ] && force=1
  reason="$(busy)"
  if [ -n "$reason" ] && [ "$force" = 0 ]; then echo "Not stopping: $reason. Wait, or pass --force."; return 1; fi
  touch "$STOP_FLAG"  # every supervisor of this state stops at its next check, even one missing from the pid file
  sups="$(supervisors)"
  for pid in $sups; do kill -TERM "$pid" 2>/dev/null; done  # each one stops its backend, then exits
  srv="$(server_pid)"
  [ -n "$srv" ] && stop_pid "$srv"
  other="$(port_pid "$PORT")"
  if [ -n "$other" ]; then
    if is_server "$other"; then
      echo "Stopping the live server PID $other on port $PORT."
      stop_pid "$other"
    else
      echo "Port $PORT is held by PID $other ($(cmdline "$other")), which is not the app's live server: left alone."
      return 1
    fi
  fi
  for _ in $(seq 1 150); do [ -z "$(supervisors)" ] && break; sleep 0.5; done
  if [ -n "$(supervisors)" ]; then echo "Supervisor(s) $(echo $(supervisors)) still running; run stop again."; return 1; fi
  rm -f "$SUP_PID" "$SRV_PID"
  echo "Stopped."
}

status() {
  local sups srv
  sups="$(supervisors)"; srv="$(server_pid)"
  echo "supervisor: ${sups:-not running}   live server: ${srv:-$(port_pid "$PORT" | sed 's/^/unmanaged pid /')}" | tr '\n' ' '; echo
  [ "$(echo $sups | wc -w)" -gt 1 ] && echo "WARNING: more than one supervisor; run app/start.sh restart when idle."
  [ -z "$sups$srv$(port_pid "$PORT")" ] && { echo "Not running. Start it with: app/start.sh start"; return 3; }
  local console="http://127.0.0.1:$PORT/"
  [ -n "$(port_pid "$CONSOLE_PORT")" ] && console="http://127.0.0.1:$CONSOLE_PORT/ (also http://127.0.0.1:$PORT/)"
  echo "console: $console"
  AQUI_JSON="$(curl -s -m 3 "http://127.0.0.1:$PORT/api/status" 2>/dev/null)" python3 - <<'PY'
import json, os
try:
    s = json.loads(os.environ["AQUI_JSON"])
except ValueError:
    raise SystemExit("api: not answering yet (starting up?); see runs/app/live_server.log")
models = [m for m in s.get("models", []) if m.get("state") != "disabled"]
resident = [m for m in models if m.get("state") == "resident"]
failed = [m["id"] for m in models if m.get("state") == "failed"]
gpu = s.get("gpu") or {}
warm = "warm" if s.get("worker") == "online" and len(resident) == len(models) else "NOT warm"
line = "worker: %s (%s) · models %s: %d/%d resident" % (s.get("worker"), "live" if s.get("live") else "mock", warm,
                                                        len(resident), len(models))
if failed:
    line += ", failed: " + ", ".join(failed)
if s.get("warm_s"):
    line += " · warm-up %s s" % s["warm_s"]
if gpu.get("used_gb") is not None:
    line += " · GPU %s/%s GB" % (gpu["used_gb"], gpu.get("total_gb"))
print(line)
q = s.get("current_question")
if s.get("current"):
    line = "current run: %s (%s)" % (s["current"], s.get("current_panorama"))
    if q:
        line += " · WAITING on %s for %s s: %r" % (q["question_id"], q["waiting_s"], q.get("text"))
        if q.get("timeout_in_s") is not None:
            line += " · auto-skip in %s s" % q["timeout_in_s"]
    print(line)
print("queue: %d waiting · question timeout: %s · map tiles: %s" % (
    len(s.get("queue") or []), s.get("question_timeout_s") or "off",
    ", ".join(l["id"] for l in s.get("tile_layers") or []) or "off"))
PY
  echo "logs: $LOG · $SUP_LOG"
}

restart() {
  local force=0 reason
  [ "${1:-}" = "--force" ] && { force=1; shift; }
  reason="$(busy)"
  if [ -n "$reason" ] && [ "$force" = 0 ]; then echo "Not restarting: $reason. Wait, or pass --force."; return 1; fi
  build  # while the old backend still serves: a failed build keeps the previous console
  stop --force || return 1
  AQUI_NO_BUILD=1 start "$@"
}

main() {
  mkdir -p "$STATE"
  case "${1:-status}" in
    start) shift; start "$@" ;;
    stop) shift; stop "$@" ;;
    restart) shift; restart "$@" ;;
    status) status ;;
    build) AQUI_FORCE_BUILD=1 build ;;
    __supervise) shift; supervise "$@" ;;
    *) sed -n '2,17p' "$SELF"; return 2 ;;
  esac
}
main "$@"; exit $?

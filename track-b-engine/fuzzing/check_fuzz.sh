#!/usr/bin/env bash
# check_fuzz.sh — quick liveness check for the AFL++ baseline runs.
# Confirms processes are alive and execs_done advances over a sample window.
set -u

echo "afl-fuzz procs: $(pgrep -c afl-fuzz)"
echo "tmux sessions : $(tmux ls 2>/dev/null | wc -l)"
now=$(date +%s)

for t in leak2 leak4 leak5 clean; do
    f="$HOME/fuzz/$t/findings/default/fuzzer_stats"
    if [ ! -f "$f" ]; then
        echo "$t: NO STATS FILE"
        continue
    fi
    rt=$(sed -n 's/^run_time *: *//p' "$f")
    lu=$(sed -n 's/^last_update *: *//p' "$f")
    cc=$(sed -n 's/^corpus_count *: *//p' "$f")
    age=$(( now - lu ))
    printf "%-6s run_time=%ss corpus=%s last_update=%ss ago\n" "$t" "$rt" "$cc" "$age"
done

echo "--- 60s execs_done delta (leak5) ---"
f="$HOME/fuzz/leak5/findings/default/fuzzer_stats"
e1=$(sed -n 's/^execs_done *: *//p' "$f")
sleep 60
e2=$(sed -n 's/^execs_done *: *//p' "$f")
echo "execs_done: $e1 -> $e2  delta=$(( e2 - e1 ))"
if [ "$e2" -gt "$e1" ]; then echo "STATUS: ALIVE (advancing)"; else echo "STATUS: STALLED (no progress)"; fi

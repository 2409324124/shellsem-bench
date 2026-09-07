#!/bin/bash
set -Eeuo pipefail
list=$1; out=$2
tmp=$(mktemp -d "$(dirname -- "$out")/.supervisor.XXXXXX")
pids=(); groups=(); done_jobs=()
cleanup() {
  local p
  for p in "${groups[@]}"; do kill -TERM -- "-$p" 2>/dev/null || :; done
  sleep .15
  for p in "${groups[@]}"; do kill -KILL -- "-$p" 2>/dev/null || :; done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null || :; done
  rm -rf -- "$tmp"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
mkdir "$tmp/stderr"
mapfile -d '' -t tasks < "$list"
for ((start=0;start<${#tasks[@]};start+=4)); do
  end=$((start+4)); ((end<=${#tasks[@]})) || end=${#tasks[@]}
  for ((i=start;i<end;i++)); do
    printf -v name '%06d' "$i"
    setsid /usr/local/bin/worker -- "${tasks[i]}" > "$tmp/$i.out" 2> "$tmp/stderr/$name.log" &
    pids[i]=$!; groups+=("${pids[i]}"); done_jobs[i]=0
  done
  remaining=$((end-start))
  while ((remaining)); do
    for ((i=start;i<end;i++)); do
      if ((done_jobs[i])); then continue; fi
      if ! kill -0 "${pids[i]}" 2>/dev/null; then
        if wait "${pids[i]}"; then rc=0; else rc=$?; fi
        done_jobs[i]=1; remaining=$((remaining-1))
        if ((rc)); then exit "$rc"; fi
        kill -TERM -- "-${pids[i]}" 2>/dev/null || :
        kill -KILL -- "-${pids[i]}" 2>/dev/null || :
      fi
    done
    if ((remaining)); then sleep .03; fi
  done
done
: > "$tmp/aggregate.bin"
for ((i=0;i<${#tasks[@]};i++)); do cat "$tmp/$i.out" >> "$tmp/aggregate.bin"; rm "$tmp/$i.out"; done
mv -T -- "$tmp" "$out"

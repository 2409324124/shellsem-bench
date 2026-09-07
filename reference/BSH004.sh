#!/bin/bash
set -Eeuo pipefail
list=$1; out=$2
tmp=$(mktemp -d "$(dirname -- "$out")/.jobs.XXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
mkdir "$tmp/stderr"
mapfile -d '' -t tasks < "$list"
pids=(); codes=()
for ((start=0; start<${#tasks[@]}; start+=4)); do
  end=$((start+4)); ((end<=${#tasks[@]})) || end=${#tasks[@]}
  for ((i=start;i<end;i++)); do
    printf -v name '%06d' "$i"
    /usr/local/bin/worker -- "${tasks[i]}" > "$tmp/$i.out" 2> "$tmp/stderr/$name.log" &
    pids[i]=$!
  done
  for ((i=start;i<end;i++)); do
    if wait "${pids[i]}"; then codes[i]=0; else codes[i]=$?; fi
  done
done
for ((i=0;i<${#tasks[@]};i++)); do if ((codes[i])); then exit "${codes[i]}"; fi; done
: > "$tmp/aggregate.bin"
for ((i=0;i<${#tasks[@]};i++)); do cat "$tmp/$i.out" >> "$tmp/aggregate.bin"; rm "$tmp/$i.out"; done
mv -T -- "$tmp" "$out"

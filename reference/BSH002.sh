#!/bin/bash
set -Eeuo pipefail
out=$1
if /usr/local/bin/source-stage 2> "$out/source.stderr" | /usr/local/bin/filter-stage 2> "$out/filter.stderr" | /usr/local/bin/sink-stage > "$out/stdout.bin" 2> "$out/sink.stderr"; then
  status=("${PIPESTATUS[@]}")
else
  status=("${PIPESTATUS[@]}")
fi
pipeline=0
for x in "${status[@]}"; do if (( x != 0 )); then pipeline=$x; fi; done
printf 'source_rc=%d\nfilter_rc=%d\nsink_rc=%d\npipeline_rc=%d\n' "${status[0]}" "${status[1]}" "${status[2]}" "$pipeline"
for i in 1 0 2; do if (( status[i] != 0 )); then exit "${status[i]}"; fi; done

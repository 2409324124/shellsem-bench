collect() {
    local count=0 first=0 scan=0 framing=0 item fd pid rc
    exec {fd}< <(scanner -- "$1" </dev/null)
    pid=$!
    while :; do
        item=''
        if IFS= read -r -d '' -u "$fd" item; then
            count=$((count+1))
            if worker -- "$item" </dev/null {fd}<&-; then
                :
            else
                rc=$?
                if ((first==0)); then first=$rc; fi
            fi
        else
            if [[ -n $item ]]; then framing=65; fi
            break
        fi
    done
    exec {fd}<&-
    if wait "$pid"; then scan=0; else scan=$?; fi
    printf 'count=%d scan=%d worker=%d framing=%d\n' "$count" "$scan" "$first" "$framing" >&3
    if ((scan)); then return "$scan"; fi
    if ((framing)); then return "$framing"; fi
    return "$first"
}

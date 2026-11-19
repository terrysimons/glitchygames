#!/bin/bash
# Measures every llama.cpp build build_llama_cpp.sh made on this Raspberry Pi with the AI service's
# models and settings (ansible/roles/ai_models and ai_service defaults: keep them equal):
#   [AI_CORES=N[,N...]|none] [GAME=NAME] [THREADS=N[,N...]] [DEPTHS=N[,N...]] \
#       [CACHE_TYPE_K=T[,T...]] [CACHE_TYPE_V=T[,T...]] [BONSAI_CONTEXT=N] [QWEN_CONTEXT=N] \
#       [MEMORY_LIMIT=SIZE] [QWEN_SLEEP_SECONDS=N] benchmark_llama_cpp.sh [WORK_ROOT] [CONFIGURATION...]
# MEMORY_LIMIT (such as 2500M) runs this script, and so both servers, in a systemd user scope
# with that much memory and no swap (MemoryMax, MemorySwapMax=0; the user manager is handed the
# memory controller), to stand in for a smaller Pi on a bigger one: what a 4 GB Pi with a desktop
# and a game has left for the models. The page cache of the model files counts against it, so the
# kernel drops and re-reads model pages as a small Pi would. With it, once both servers are up,
# they take turns (Bonsai answers, Qwen embeds, an image, again), each step timed with the
# servers' major page faults (model pages read back from disk) and the scope's memory, peak and
# out-of-memory kills. The game named with GAME stays outside the limit. Before the servers start,
# the model files are dropped from the page cache, so their pages are read inside the limit and
# count against it (the kernel charges a cached page to whichever cgroup first read it).
# QWEN_SLEEP_SECONDS gives the Qwen server --sleep-idle-seconds N, so it unloads after N idle
# seconds (the service's own setting), and the turns wait that long after each embedding before
# Bonsai's next answer: the scope's memory then shows Bonsai alone, and the next embedding
# includes Qwen's reload.
# WORK_ROOT defaults to ~/ai-spike; with no configurations it measures each llama.cpp-*-* folder
# there that holds a build. Cores are placed as the service places them
# (plans/lucid-circuit-linux.md 6.2: ranked by cpu_capacity, the game on the first, the mirror on
# the second, the AI on the rest; on a Pi 5 the AI gets cores 2-3), worked out by the helper's
# placement command. This script and everything it starts run on the AI's cores. AI_CORES names
# other cores, or AI_CORES=none runs unpinned. GAME names a game already running (such as
# GAME=bitmappy, matched against its command line): every thread of it is moved to the game's
# core and the summary says so; the game isn't started here, since a desktop game needs the
# display session a script over SSH lacks. THREADS (default: the AI's core count, as the service's
# AI_THREADS) is how many cores llama.cpp may use: a list such as THREADS=2,3,4 runs llama-bench
# once per count, and the servers run with the last count in the list. DEPTHS (default 0) is how many tokens llama-bench puts in the KV cache before
# timing each test: at depth 0 the cache is empty, so only a deeper test shows what reading a full
# cache costs each token; a list such as DEPTHS=0,4096 times each depth. The fill isn't timed and
# llama-bench reuses it across repetitions, but it takes as long as reading that much prompt: about
# six minutes per 4,096 tokens on two Pi 5 threads, once or twice per depth, cache pair and thread
# count (the prompt and generation tests use different context sizes, which can force a refill).
# CACHE_TYPE_K and CACHE_TYPE_V (default q8_0, the service's for every model:
# plans/lucid-circuit-linux.md 6.5) are the KV cache element types: each one of f32 f16 bf16 q8_0
# q4_0 q4_1 iq4_nl q5_0 q5_1 (b12167's list, common/arg.cpp), or a list of them. The two lists pair
# up by position (CACHE_TYPE_V left unset follows CACHE_TYPE_K), so CACHE_TYPE_K=f16,q8_0 times
# f16/f16 then q8_0/q8_0, not every mix; llama-bench runs each model once per pair, and both
# servers use the last pair, as with THREADS. A quantized V cache needs flash attention, which is
# on for both. BONSAI_CONTEXT (default 131072, the service's) and
# QWEN_CONTEXT (default 8192) are the servers' context sizes. Left at their defaults, the servers
# run with the service's settings. For each build:
#   1. llama-bench: prompt reading (pp512) and answer writing (tg128) speeds, three runs each, for
#      Bonsai 2 2B and Qwen3-Embedding 0.6B, every layer offered to the backend
#   2. llama-server with the service's settings (128K context, flash attention, vision file, an
#      8-bit KV cache for both models) or the
#      context and cache settings above: does it load, how much memory it holds and where it goes
#      (model, KV cache, the linear-attention layers' recurrent state, compute buffers, printed at
#      log verbosity 4: b12167 counts library INFO lines as TRACE, which the default 3 drops), does
#      it answer a sum, a fact and an image correctly, and how many graph splits it reports (more
#      than 1 means work bounced between CPU and GPU)
#   3. the embedding server: its dimensions, and whether similar phrases score closer
# Power and clock are sampled every second for the whole run, tagged with the step running, into
# power.csv (synced line by line, so a reset keeps the readings from just before it), and summed
# up at the end with every kernel voltage message logged during the run: a Pi short of power or
# too hot slows down, and its numbers then mean nothing. The sampler lives as long as this script,
# not as a separate service, which systemd stops when its user has no session (seen 2026-11-18).
# Results: WORK_ROOT/results/<time>/ (summary.txt, power.csv, the raw llama-bench JSON, each
# server's log). Nothing else should be busy beyond the game named with GAME.
set -u

# A memory limit means running again inside a scope that has it, with the same arguments
if [ -n "${MEMORY_LIMIT:-}" ] && [ -z "${BENCHMARK_MEMORY_SCOPE:-}" ]; then
    if ! [[ "$MEMORY_LIMIT" =~ ^[1-9][0-9]*[KMG]$ ]]; then
        echo "MEMORY_LIMIT must be a size such as 2500M or 3G" >&2
        exit 64
    fi
    exec systemd-run --user --scope --quiet -p MemoryMax="$MEMORY_LIMIT" -p MemorySwapMax=0 \
        env BENCHMARK_MEMORY_SCOPE=1 "$0" "$@"
fi

work_root=${1:-$HOME/ai-spike}
shift $(( $# > 0 ? 1 : 0 ))
# Beside this script: parses what llama.cpp prints, and places the cores
helper=$(dirname "$0")/summarize_llama_cpp_results.py

# Where the service would put each part, as lines such as "ai 2,3"; nothing on a one-core machine
placement=$(python3 "$helper" placement) || exit 1
game_cores=$(awk '$1 == "game" {print $2}' <<< "$placement")
case "${AI_CORES:-}" in
    "") ai_cores=$(awk '$1 == "ai" {print $2}' <<< "$placement") ;;
    none) ai_cores="" ;;
    *)
        if ! [[ "$AI_CORES" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
            echo "AI_CORES must be core numbers such as 2,3, or none" >&2
            exit 64
        fi
        ai_cores=$AI_CORES ;;
esac
if [ -n "$ai_cores" ]; then
    # This shell, so everything it starts: llama-bench, both servers, the power sampler
    taskset -cp "$ai_cores" $$ > /dev/null || { echo "could not pin to cores $ai_cores" >&2; exit 64; }
fi
# Every match, not the first: "uv run bitmappy" is a wrapper whose child is the game itself
game_pids=()
if [ -n "${GAME:-}" ]; then
    mapfile -t game_pids < <(pgrep -f -- "$GAME" | grep -vx "$$")
    if [ "${#game_pids[@]}" -eq 0 ]; then
        echo "no running process matches GAME=$GAME" >&2
        exit 64
    fi
    if [ -n "$game_cores" ]; then
        for game_pid in "${game_pids[@]}"; do
            taskset -acp "$game_cores" "$game_pid" > /dev/null \
                || { echo "could not move $GAME (pid $game_pid) to core $game_cores" >&2; exit 64; }
        done
    fi
fi
# The cores this shell may use, after the pin: the AI's count, or every core when unpinned
threads=${THREADS:-$(nproc)}
if ! [[ "$threads" =~ ^[1-9][0-9]*(,[1-9][0-9]*)*$ ]]; then
    echo "THREADS must be a count or a comma-separated list of counts, such as 3 or 2,3,4" >&2
    exit 64
fi
server_threads=${threads##*,}
bonsai_context=${BONSAI_CONTEXT:-131072}
qwen_context=${QWEN_CONTEXT:-8192}
depths=${DEPTHS:-0}
if ! [[ "$depths" =~ ^(0|[1-9][0-9]*)(,(0|[1-9][0-9]*))*$ ]]; then
    echo "DEPTHS must be a token count or a comma-separated list of them, such as 0,4096" >&2
    exit 64
fi
IFS=, read -r -a cache_types_k <<< "${CACHE_TYPE_K:-q8_0}"
IFS=, read -r -a cache_types_v <<< "${CACHE_TYPE_V:-${CACHE_TYPE_K:-q8_0}}"
if [ "${#cache_types_k[@]}" -ne "${#cache_types_v[@]}" ]; then
    echo "CACHE_TYPE_K and CACHE_TYPE_V must list the same number of types: they pair up by position" >&2
    exit 64
fi
# The servers use the last pair
cache_type_k=${cache_types_k[-1]}
cache_type_v=${cache_types_v[-1]}
for context in "$bonsai_context" "$qwen_context"; do
    if ! [[ "$context" =~ ^[1-9][0-9]*$ ]]; then
        echo "BONSAI_CONTEXT and QWEN_CONTEXT must be token counts, such as 32768" >&2
        exit 64
    fi
done
for cache_type in "${cache_types_k[@]}" "${cache_types_v[@]}"; do
    case "$cache_type" in
        f32|f16|bf16|q8_0|q4_0|q4_1|iq4_nl|q5_0|q5_1) ;;
        *) echo "CACHE_TYPE_K and CACHE_TYPE_V must be one of f32 f16 bf16 q8_0 q4_0 q4_1 iq4_nl q5_0 q5_1" >&2
           exit 64 ;;
    esac
done
if [ "$bonsai_context:$qwen_context:$cache_type_k:$cache_type_v" = "131072:8192:q8_0:q8_0" ]; then
    server_settings="the service's settings"
else
    server_settings="context $bonsai_context (Bonsai), $qwen_context (Qwen); KV cache K $cache_type_k, V $cache_type_v"
fi
models=$work_root/models
results=$work_root/results/$(date +%Y%m%d-%H%M%S)
mkdir -p "$models" "$results" || exit 1
summary=$results/summary.txt

bonsai_file=Ternary-Bonsai-2-2B-Q2_0.gguf
vision_file=Ternary-Bonsai-2-2B-mmproj-Q8_0.gguf
qwen_file=Qwen3-Embedding-0.6B-Q8_0.gguf
bonsai_port=23332
qwen_port=23336

say() { echo "$*" | tee -a "$summary"; }

# Pinned revisions and SHA-256 sums from ansible/roles/ai_models/defaults/main.yml
fetch() {  # repository revision file sha256
    if [ ! -f "$models/$3" ]; then
        echo "downloading $3"
        curl -sSfL -o "$models/$3.part" "https://huggingface.co/$1/resolve/$2/$3" || exit 1
        mv "$models/$3.part" "$models/$3"
    fi
    echo "$4  $models/$3" | sha256sum -c --quiet - || exit 1
}
fetch prism-ml/Ternary-Bonsai-2-2B-gguf a6032a5089ac27e96be3a80c7b42d1ad0bd89887 \
    "$bonsai_file" c2893fa6f951daee8b7263d5f49b455e57989ef56417a22125b03566dc560650
fetch prism-ml/Ternary-Bonsai-2-2B-gguf a6032a5089ac27e96be3a80c7b42d1ad0bd89887 \
    "$vision_file" ac9934e8d7966d0d62442c202ec8fdad99a045dea79366c1a4a246a46f5c0533
fetch Qwen/Qwen3-Embedding-0.6B-GGUF 370f27d7550e0def9b39c1f16d3fbaa13aa67728 \
    "$qwen_file" 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439

# One reading at this instant; between steps the governor may have stepped the clock down, so the
# clock under load comes from power.csv, not from these
thermal_state() {
    temperature=$(awk '{printf "%.1f C", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
    throttled=$(vcgencmd get_throttled 2>/dev/null || echo "throttled=unknown (no vcgencmd)")
    echo "$temperature, $throttled"
}

# What step is running, read by the sampler for each line
phase_file=$results/phase
echo setup > "$phase_file"
phase() { echo "$1" > "$phase_file"; }

power_samples=$results/power.csv
started_epoch=$(date +%s)
sample_power() {
    echo 'epoch,phase,clock_mhz,temperature_c,throttled,supply_volts,core_volts,load' > "$power_samples"
    while :; do
        printf '%s,%s,%s,%s,%s,%s,%s,%s\n' \
            "$(date +%s)" \
            "$(cat "$phase_file")" \
            "$(vcgencmd measure_clock arm | awk -F= '{printf "%d", $2/1000000}')" \
            "$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp)" \
            "$(vcgencmd get_throttled | cut -d= -f2)" \
            "$(vcgencmd pmic_read_adc EXT5V_V | sed 's/.*=//; s/V$//')" \
            "$(vcgencmd measure_volts core | sed 's/.*=//; s/V$//')" \
            "$(cut -d' ' -f1 /proc/loadavg)" >> "$power_samples"
        sync "$power_samples"
        sleep 1
    done
}
sample_power &
sampler=$!
trap 'kill "$sampler" 2>/dev/null' EXIT

if [ "$#" -gt 0 ]; then
    configurations=("$@")
else
    configurations=()
    for directory in "$work_root"/llama.cpp-*-*; do
        [ -x "$directory/build/bin/llama-bench" ] && configurations+=("${directory##*-}")
    done
fi
if [ "${#configurations[@]}" -eq 0 ]; then
    echo "no builds in $work_root: run build_llama_cpp.sh first" >&2
    exit 1
fi

say "host: $(hostname)  $(uname -sr)  page size $(getconf PAGESIZE)  $(nproc) cores"
say "memory: $(free -m | awk '/^Mem:/ {print $2 " MiB total, " $7 " MiB available"}')"
# This script's cgroup: the limited scope when MEMORY_LIMIT is set
cgroup=/sys/fs/cgroup$(sed -n 's/^0:://p' /proc/self/cgroup)
if [ -n "${MEMORY_LIMIT:-}" ]; then
    say "memory limit: $(cat "$cgroup/memory.max") bytes, swap $(cat "$cgroup/memory.swap.max") (the servers and this script; the game outside)"
fi
say "models on: $(findmnt -no SOURCE --target "$models")"
qwen_sleep=${QWEN_SLEEP_SECONDS:-}
if [ -n "$qwen_sleep" ] && ! [[ "$qwen_sleep" =~ ^[1-9][0-9]*$ ]]; then
    echo "QWEN_SLEEP_SECONDS must be a whole number of seconds, such as 30" >&2
    exit 64
fi
say "load before: $(cut -d' ' -f1-3 /proc/loadavg)"
say "configurations: ${configurations[*]}"
say "cores: AI ${ai_cores:-not pinned}; the service would place game ${game_cores:-none}, AI $(awk '$1 == "ai" {print $2}' <<< "$placement")"
for game_pid in "${game_pids[@]}"; do
    say "game: pid $game_pid ($(ps -o args= -p "$game_pid" | cut -c1-60)), its threads on cores $(taskset -acp "$game_pid" | sed 's/.*: //' | sort -u | paste -sd' ' -)"
done
say "threads: llama-bench $threads; servers $server_threads (on $(nproc) cores)"
cache_pairs=()
for index in "${!cache_types_k[@]}"; do cache_pairs+=("${cache_types_k[$index]}/${cache_types_v[$index]}"); done
say "llama-bench: KV cache ${cache_pairs[*]}; depths $depths"
say "servers: $server_settings"

# Where each server's memory goes, from its log at verbosity 4: model, KV cache, recurrent state and
# compute buffers, without the log's timestamp and level, nor the empty per-layer mapped buffers
# Qwen's log lists. "CPU_Mapped" is the model file mapped (pages the kernel can drop and re-read);
# "CPU_REPACK" is weights copied into a faster layout, ordinary memory that must stay
memory_lines() {  # log
    grep -E 'model buffer size|KV buffer size|RS buffer size|compute buffer size|llama_kv_cache: size|llama_memory_recurrent: size' "$1" \
        | grep -v '=  *0\.00 MiB$' \
        | sed -E 's/^[0-9.]+ [A-Z] +//; s/^/  memory: /' | tee -a "$summary"
}

wait_ready() {  # port log pid
    for _ in $(seq 1 180); do
        kill -0 "$3" 2>/dev/null || { say "  server exited"; tail -20 "$2" | tee -a "$summary"; return 1; }
        [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$1/health")" = 200 ] && return 0
        sleep 1
    done
    say "  not ready after 180 s"; return 1
}
resident() { ps -o rss= -p "$1" | awk '{printf "%d MiB", $1/1024}'; }
# Pages a process had to read back from disk (field 12 of /proc/PID/stat; the name has no spaces)
major_faults() { awk '{print $12}' "/proc/$1/stat" 2>/dev/null; }
# How many more since an earlier reading, or "?" once the process is gone
faults_since() {  # pid earlier
    local now
    now=$(major_faults "$1")
    if [[ "$now" =~ ^[0-9]+$ && "$2" =~ ^[0-9]+$ ]]; then echo "+$(( now - $2 ))"; else echo "?"; fi
}
# The scope's memory now and at its peak, its out-of-memory kills, and how much is file pages
scope_memory() {
    awk -v current="$(cat "$cgroup/memory.current")" -v peak="$(cat "$cgroup/memory.peak" 2>/dev/null || echo 0)" \
        '$1 == "anon" {anon = $2} $1 == "file" {file = $2}
         END {printf "scope %d MiB (anon %d, file %d), peak %d MiB", current/1048576, anon/1048576, file/1048576, peak/1048576}' \
        "$cgroup/memory.stat"
    printf ', oom kills %s' "$(awk '$1 == "oom_kill" {print $2}' "$cgroup/memory.events")"
}

image=$(python3 "$helper" image)

ask() {  # label expected request-json
    reply=$(curl -s --max-time 900 "http://127.0.0.1:$bonsai_port/v1/chat/completions" \
        -H 'Content-Type: application/json' -d "$3")
    echo "$reply" > "$results/$configuration-ask-$1.json"
    echo "$reply" | python3 "$helper" answer "$1" "$2" | tee -a "$summary"
}

for configuration in "${configurations[@]}"; do
    bin=$(echo "$work_root"/llama.cpp-*-"$configuration"/build/bin)
    say ""
    say "=== $configuration ($bin)"
    "$bin/llama-server" --version 2>&1 | tail -1 | tee -a "$summary"
    "$bin/llama-server" --list-devices 2>&1 | grep -vE '^(load_backend|ggml_)' | tee -a "$summary"

    say "-- llama-bench  [$(thermal_state)]"
    for model in "$bonsai_file" "$qwen_file"; do
        generate=128
        [ "$model" = "$qwen_file" ] && generate=0
        phase "$configuration-bench-${model%%-*}"
        for index in "${!cache_types_k[@]}"; do
            type_k=${cache_types_k[$index]}; type_v=${cache_types_v[$index]}
            run=$results/$configuration-bench-${model%.gguf}-kv-$type_k-$type_v
            "$bin/llama-bench" -m "$models/$model" -p 512 -n "$generate" -ngl 99 -fa 1 -t "$threads" -r 3 \
                -ctk "$type_k" -ctv "$type_v" -d "$depths" -o json > "$run.json" 2> "$run.log"
            python3 "$helper" bench "$run.json" "$model" | tee -a "$summary"
        done
        # Which CPU code llama.cpp loaded (a build with every variant names the one it chose)
        grep -m1 -E 'load_backend|CPU : ' "$run.log" | sed 's/^/  log: /' | tee -a "$summary"
    done
    say "   after: [$(thermal_state)]"

    if [ -n "${MEMORY_LIMIT:-}" ]; then
        say "-- model files out of the page cache, so the limit counts them"
        python3 "$helper" evict "$models/$bonsai_file" "$models/$vision_file" "$models/$qwen_file" | tee -a "$summary"
    fi
    phase "$configuration-bonsai-server"
    say "-- Bonsai 2B server, $server_settings  [$(thermal_state)]"
    "$bin/llama-server" --host 127.0.0.1 --port "$bonsai_port" \
        --model "$models/$bonsai_file" --mmproj "$models/$vision_file" --alias bonsai-2-2b \
        --threads "$server_threads" \
        --gpu-layers 99 --parallel 1 --no-webui --flash-attn on \
        --ctx-size "$bonsai_context" --n-predict -1 --cache-ram 4096 \
        --cache-type-k "$cache_type_k" --cache-type-v "$cache_type_v" --log-verbosity 4 \
        --chat-template-kwargs '{"reasoning_effort":"medium"}' > "$results/$configuration-bonsai.log" 2>&1 &
    bonsai=$!
    if wait_ready "$bonsai_port" "$results/$configuration-bonsai.log" "$bonsai"; then
        say "  loaded: $(resident "$bonsai") resident, on cores $(taskset -cp "$bonsai" | sed 's/.*: //')"
        grep -E 'load_backend|system_info|graph splits' \
            "$results/$configuration-bonsai.log" | sed 's/^/  log: /' | tee -a "$summary"
        memory_lines "$results/$configuration-bonsai.log"
        ask sum 391 '{"messages":[{"role":"user","content":"What is 17 times 23? Reply with the number only."}]}'
        ask fact canberra '{"messages":[{"role":"user","content":"What is the capital of Australia? One word."}]}'
        ask image blue "{\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"What two colours are in this image, left then right? Answer in a few words.\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$image\"}}]}]}"
        say "  after the questions: $(resident "$bonsai") resident  [$(thermal_state)]"
    fi

    phase "$configuration-qwen-server"
    say "-- Qwen 0.6B embedding server, $server_settings"
    "$bin/llama-server" --host 127.0.0.1 --port "$qwen_port" \
        --model "$models/$qwen_file" --alias qwen3-embedding-0.6b --gpu-layers 99 \
        --threads "$server_threads" \
        --parallel 1 --no-webui --embedding --pooling last \
        --ctx-size "$qwen_context" --ubatch-size "$qwen_context" --flash-attn on \
        ${qwen_sleep:+--sleep-idle-seconds "$qwen_sleep"} \
        --cache-type-k "$cache_type_k" --cache-type-v "$cache_type_v" --log-verbosity 4 \
        > "$results/$configuration-qwen.log" 2>&1 &
    qwen=$!
    if wait_ready "$qwen_port" "$results/$configuration-qwen.log" "$qwen"; then
        say "  loaded: $(resident "$qwen") resident"
        memory_lines "$results/$configuration-qwen.log"
        curl -s "http://127.0.0.1:$qwen_port/v1/embeddings" -H 'Content-Type: application/json' \
            -d '{"input":["a red apple","a green apple","a diesel locomotive"]}' \
            | python3 "$helper" embeddings | tee -a "$summary"
        kill -0 "$bonsai" 2>/dev/null && say "  both loaded: Bonsai $(resident "$bonsai"), Qwen $(resident "$qwen"); $(free -m | awk '/^Mem:/ {print $7}') MiB available"
        if [ -n "${MEMORY_LIMIT:-}" ] && kill -0 "$bonsai" 2>/dev/null; then
            phase "$configuration-taking-turns"
            say "-- taking turns under the limit: $(scope_memory)"
            embed() {
                curl -s -o /dev/null -w '%{http_code} in %{time_total} s' "http://127.0.0.1:$qwen_port/v1/embeddings" \
                    -H 'Content-Type: application/json' -d '{"input":["a red apple","a green apple","a diesel locomotive"]}'
            }
            for step in sum embed image embed fact embed; do
                bonsai_faults=$(major_faults "$bonsai"); qwen_faults=$(major_faults "$qwen")
                case "$step" in
                    sum) ask turns-sum 391 '{"messages":[{"role":"user","content":"What is 17 times 23? Reply with the number only."}]}' ;;
                    fact) ask turns-fact canberra '{"messages":[{"role":"user","content":"What is the capital of Australia? One word."}]}' ;;
                    image) ask turns-image blue "{\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"What two colours are in this image, left then right? Answer in a few words.\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$image\"}}]}]}" ;;
                    embed)
                        say "  embed: $(embed)"
                        if [ -n "$qwen_sleep" ]; then
                            sleep $(( qwen_sleep + 5 ))
                            say "    after Qwen's $qwen_sleep s idle: Qwen $(resident "$qwen"); $(scope_memory)"
                        fi ;;
                esac
                say "    pages read back: Bonsai $(faults_since "$bonsai" "$bonsai_faults"), Qwen $(faults_since "$qwen" "$qwen_faults"); $(scope_memory)"
                kill -0 "$bonsai" 2>/dev/null || { say "  Bonsai is gone (killed)"; break; }
                kill -0 "$qwen" 2>/dev/null || { say "  Qwen is gone (killed)"; break; }
            done
        fi
    fi
    kill "$bonsai" "$qwen" 2>/dev/null
    # Only the servers: a bare wait would also wait for the sampler, which never ends
    wait "$bonsai" "$qwen" 2>/dev/null
    phase idle
done

say ""
say "-- power, every second of the run"
python3 "$helper" power "$power_samples" | tee -a "$summary"
say "-- kernel voltage messages during the run"
voltage_messages=$(journalctl -k --since "@$started_epoch" --no-pager 2>/dev/null \
    | grep -iE 'voltage|throttl' || true)
if [ -n "$voltage_messages" ]; then
    echo "$voltage_messages" | sed 's/^/  /' | tee -a "$summary"
else
    say "  none"
fi
say ""
say "results: $results"

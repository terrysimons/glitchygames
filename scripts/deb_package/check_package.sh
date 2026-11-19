#!/bin/sh
# Checks a .deb of the local AI service inside a container (`nox -s deb-package`, noxfile.py):
#   check_package.sh installed DEB   on the release that built it, with systemd running: install,
#                                    the server and its CPU variant, the sidecar, an upgrade while
#                                    a unit runs (Review focus 4), and dpkg -r
#   check_package.sh refused DEB     on an older release: apt must refuse it
# plans/lucid-circuit-linux.md, sections 6.7 and 7. Exits 1 at the first check that fails.
set -eu

program=/opt/glitchygames/ai
package=glitchygames-ai
setup_unit=ai.glitchygames.setup.service
probe_unit=ai.glitchygames.upgrade-probe.service
user=player

say() {
    echo "deb-package: $1"
}

fail() {
    echo "deb-package: FAILED: $1" >&2
    exit 1
}

# Over IPv4, as the image was built (scripts/deb_package/Dockerfile)
apt_get() {
    DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::ForceIPv4=true "$@"
}

release() {
    # shellcheck source=/dev/null  # the container's own file
    . /etc/os-release && echo "$PRETTY_NAME"
}

# Every file under the user's data folder, with its SHA-256
user_data() {
    # shellcheck disable=SC2016  # $HOME is the user's, expanded by their shell
    runuser -u "$user" -- sh -c 'cd "$HOME/.local/share/glitchygames/ai" && find . -type f -exec sha256sum {} + | sort'
}

check_refused() {
    deb=$1
    apt_get update -qq
    if apt_get install -y "$deb" > /tmp/install.log 2>&1; then
        fail "$(release) installed it: its Depends allow this release"
    fi
    grep -q 'libc6' /tmp/install.log || fail "refused, but not for glibc: $(cat /tmp/install.log)"
    say "$(release) refuses it: $(grep -m 1 'libc6' /tmp/install.log | sed 's/^ *//')"
}

check_installed() {
    deb=$1
    [ "$(dpkg-deb --field "$deb" Architecture)" = "$(dpkg --print-architecture)" ] \
        || fail "the package is for $(dpkg-deb --field "$deb" Architecture), this is $(dpkg --print-architecture)"

    # A logged-in user, as far as systemd is concerned: their manager runs
    systemctl is-system-running --wait > /dev/null || true
    loginctl enable-linger "$user"
    attempts=0
    until systemctl --user --machine="$user@" is-system-running > /dev/null 2>&1; do
        attempts=$(( attempts + 1 ))
        [ "$attempts" -lt 30 ] || fail "$user's systemd manager never started"
        sleep 1
    done

    apt_get update -qq
    apt_get install -y "$deb" 2>&1 | tee /tmp/install.log
    grep -q 'next login' /tmp/install.log || fail "postinst said nothing of the next login"
    [ "$(systemctl --global is-enabled "$setup_unit")" = enabled ] || fail "$setup_unit is not enabled"
    say "installed on $(release); $setup_unit is enabled for every user"

    runtime=$(echo "$program"/runtime/*)
    [ -x "$runtime/bin/llama-server" ] || fail "no single runtime with llama-server: $runtime"
    "$runtime/bin/llama-server" --version > /tmp/version.log 2>&1 || fail "llama-server --version: $(cat /tmp/version.log)"
    say "$(grep -m 1 version /tmp/version.log)"
    # llama-server logs the CPU variant it loads at --log-verbosity 4 (ansible/roles/llama_cpp)
    "$runtime/bin/llama-server" --log-verbosity 4 --list-devices > /tmp/devices.log 2>&1 || true
    grep -q "load_backend: loaded CPU backend from $runtime/bin/libggml-cpu-" /tmp/devices.log \
        || fail "no CPU variant loaded from the runtime: $(cat /tmp/devices.log)"
    say "$(grep -m 1 'load_backend: loaded CPU backend' /tmp/devices.log)"
    runuser -u "$user" -- env PYTHONPATH="$program/sidecar/site" \
        "$program/sidecar/python/bin/python3.14" -c 'import glitchygames_ai_service' \
        || fail "the sidecar cannot import glitchygames_ai_service"
    say "the sidecar imports glitchygames_ai_service"

    # Review focus 4: an upgrade while a unit runs stops it, and keeps the user's data
    # shellcheck disable=SC2016  # $HOME is the user's, expanded by their shell
    runuser -u "$user" -- sh -c '
        root="$HOME/.local/share/glitchygames/ai"
        mkdir -p "$root/models" "$root/config" "$root/history"
        echo model > "$root/models/kept.gguf"
        echo key > "$root/config/worker-api-key"
        echo line > "$root/history/console.jsonl"'
    data_before=$(user_data)
    version=$(dpkg-deb --field "$deb" Version)
    work=$(mktemp -d)
    dpkg-deb --raw-extract "$deb" "$work/root"
    sed -i "s/^Version: .*/Version: $version+upgrade1/" "$work/root/DEBIAN/control"
    dpkg-deb --root-owner-group --build "$work/root" "$work/upgrade.deb" > /dev/null
    systemd-run --user --machine="$user@" --unit="$probe_unit" sleep infinity
    systemctl --user --machine="$user@" is-active --quiet "$probe_unit" || fail "the probe unit did not start"
    apt_get install -y "$work/upgrade.deb"
    [ "$(dpkg-query --show --showformat='${Version}' "$package")" = "$version+upgrade1" ] \
        || fail "the upgrade did not install"
    if systemctl --user --machine="$user@" is-active --quiet "$probe_unit"; then
        fail "$probe_unit still runs after the upgrade"
    fi
    [ "$(user_data)" = "$data_before" ] || fail "the upgrade changed $user's data"
    [ "$(systemctl --global is-enabled "$setup_unit")" = enabled ] || fail "the upgrade disabled $setup_unit"
    say "the upgrade stopped the running unit and kept $user's models, keys and history"

    dpkg --remove "$package"
    [ ! -e "$program" ] || fail "dpkg -r left $(find "$program" | head -20)"
    left=$(find /usr/lib/systemd/user /etc/systemd/user -name 'ai.glitchygames.*' 2>/dev/null)
    [ -z "$left" ] || fail "dpkg -r left $left"
    [ "$(user_data)" = "$data_before" ] || fail "dpkg -r changed $user's data"
    say "dpkg -r left nothing under $program or among the units, and kept $user's data"
}

case "${1:-}" in
    installed) check_installed "$2" ;;
    refused) check_refused "$2" ;;
    *) fail "usage: check_package.sh installed|refused DEB" ;;
esac
say "passed"

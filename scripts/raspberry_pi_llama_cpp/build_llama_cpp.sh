#!/bin/bash
# Builds llama-server and llama-bench on a Raspberry Pi for one backend, each in its own work folder
# named for its tag and configuration, so builds never share a source tree or a CMake cache:
#   build_llama_cpp.sh cpu|vulkan [WORK_ROOT] [JOBS]
# gives WORK_ROOT/llama.cpp-<tag>-<configuration>/ (source) with build/ inside it. WORK_ROOT
# defaults to ~/ai-spike; JOBS, the compiles run at once, to every core. The tag and commit are
# the ones ansible/roles/llama_cpp pins: keep them equal. Vulkan needs libvulkan-dev, glslc and
# spirv-headers installed (sudo; the script refuses without them). Run on the Pi itself;
# benchmark_llama_cpp.sh measures what this builds.
#
# build/ is emptied before every build. A power loss mid-build (seen 2026-11-17 on the
# overclocked 16 GB Pi 5) left zero-byte object files newer than their sources; make took them as
# up to date and the link then failed with "undefined reference to ggml_abort"
set -u

tag=b12167
commit=240d68fcfe0c2a1f298c8e18ca181368b1914259
repository=https://github.com/ggml-org/llama.cpp.git

configuration=${1:-}
work_root=${2:-$HOME/ai-spike}
jobs=${3:-$(nproc)}

# The options ansible/roles/llama_cpp always sets, less what only a Mac needs
base_options=(
    -DCMAKE_BUILD_TYPE=Release
    -DBUILD_SHARED_LIBS=OFF
    -DLLAMA_OPENSSL=OFF
    -DLLAMA_BUILD_TESTS=OFF
    -DLLAMA_BUILD_EXAMPLES=OFF
    -DLLAMA_BUILD_UI=OFF
    -DLLAMA_USE_PREBUILT_UI=OFF
)
case "$configuration" in
    cpu)
        configuration_options=(-DGGML_VULKAN=OFF)
        ;;
    vulkan)
        missing=()
        for package in libvulkan-dev glslc spirv-headers; do
            dpkg -s "$package" >/dev/null 2>&1 || missing+=("$package")
        done
        if [ "${#missing[@]}" -gt 0 ]; then
            echo "missing packages: ${missing[*]} (sudo apt-get install ${missing[*]})" >&2
            exit 1
        fi
        configuration_options=(-DGGML_VULKAN=ON)
        ;;
    *)
        echo "usage: build_llama_cpp.sh cpu|vulkan [WORK_ROOT] [JOBS]" >&2
        exit 64
        ;;
esac

source_directory=$work_root/llama.cpp-$tag-$configuration
build_directory=$source_directory/build
mkdir -p "$work_root" || exit 1

if [ ! -d "$source_directory/.git" ]; then
    git clone --quiet --depth=1 --branch "$tag" "$repository" "$source_directory" || exit 1
fi
fetched_commit=$(git -C "$source_directory" rev-parse HEAD) || exit 1
if [ "$fetched_commit" != "$commit" ]; then
    echo "$tag is $fetched_commit, not the pinned $commit" >&2
    exit 1
fi

rm -rf "$build_directory" || exit 1
echo "configure $configuration: ${base_options[*]} ${configuration_options[*]}"
cmake -S "$source_directory" -B "$build_directory" "${base_options[@]}" "${configuration_options[@]}" \
    > "$source_directory/configure.log" 2>&1 || { tail -40 "$source_directory/configure.log"; exit 1; }
# What the CPU backend was built for (NEON, dot product, i8mm...) and whether Vulkan was found
grep -iE 'ARM|NEON|DOTPROD|MATMUL_INT8|SVE|Vulkan|glslc' "$source_directory/configure.log" | head -20

started=$(date +%s)
cmake --build "$build_directory" --target llama-server llama-bench --parallel "$jobs" \
    > "$source_directory/build.log" 2>&1 || { tail -40 "$source_directory/build.log"; exit 1; }
echo "built $configuration in $(( $(date +%s) - started )) s"
"$build_directory/bin/llama-server" --version 2>&1 | tail -2

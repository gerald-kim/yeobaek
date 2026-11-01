#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 3 ]]; then
    echo "Usage: $0 /path/RIDIBatang.otf /path/libron-ttf-directory /path/new-output-directory" >&2
    exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ridi=$(realpath -- "$1")
latin=$(realpath -- "$2")
out=$(realpath -m -- "$3")
[[ -f "$ridi" && -d "$latin" ]] || { echo 'Missing font input' >&2; exit 2; }
[[ ! -e "$out" ]] || { echo 'Output already exists; choose a fresh directory' >&2; exit 2; }
mkdir -p -- "$(dirname -- "$out")"
image='ghcr.io/nicoverbruggen/fntbld-oci@sha256:e17bde151d7da793aee02badfdc3973b4e6ec9d61c7baf9f1287b8fe2b89c521'
exec docker run --rm --network none --user "$(id -u):$(id -g)" \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$root:/work:ro" -v "$ridi:/inputs/RIDIBatang.otf:ro" \
    -v "$latin:/inputs/libron:ro" -v "$(dirname -- "$out"):/output" \
    -w /work "$image" python3 build.py --ridi /inputs/RIDIBatang.otf \
    --libron-dir /inputs/libron --output "/output/$(basename -- "$out")"

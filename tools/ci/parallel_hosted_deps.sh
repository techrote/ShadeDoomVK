#!/usr/bin/env bash
# Overlap independent system packages and hash-pinned ZMusic downloads on hosted CI.
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

case "${RUNNER_OS:-}" in
  Windows) exit 0 ;;
  Linux) platform=linux ;;
  macOS) platform=macos ;;
  *) echo "Unsupported CI runner OS: ${RUNNER_OS:-unset}" >&2; exit 2 ;;
esac

: "${RUNNER_TEMP:?RUNNER_TEMP must be defined by Actions}"
system_log=$(mktemp "$RUNNER_TEMP/sdvk-system-deps.XXXXXX")
zmusic_log=$(mktemp "$RUNNER_TEMP/sdvk-zmusic-deps.XXXXXX")

# Independent package trees: OS package manager vs hash-checked build/deps/zmusic.
# Both start before either wait; neither failure can be masked by the other.
(
  if [[ -n "${SDVK_SYSTEM_DEPS_COMMAND:-}" ]]; then
    bash -euo pipefail -c "$SDVK_SYSTEM_DEPS_COMMAND"
  fi
) >"$system_log" 2>&1 &
system_pid=$!
python3 tools/fetch_build_deps.py --platform "$platform" --output build/deps >"$zmusic_log" 2>&1 &
zmusic_pid=$!

system_rc=0
zmusic_rc=0
wait "$system_pid" || system_rc=$?
wait "$zmusic_pid" || zmusic_rc=$?

echo '=== System dependencies ==='
cat "$system_log"
echo '=== Hash-pinned ZMusic dependencies ==='
cat "$zmusic_log"
echo "System dependencies exit status: $system_rc; ZMusic exit status: $zmusic_rc"
if (( system_rc != 0 || zmusic_rc != 0 )); then
  echo 'Hosted dependencies failed; configure/build must not start.' >&2
  exit 1
fi

#!/usr/bin/env bash
# Preserve the existing renderer-software-vulkan.tar.xz member/archive contract.
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

if (( $# > 2 )); then
  echo 'Usage: package_renderer_evidence.sh [build-root] [output.tar.xz]' >&2
  exit 2
fi
build_root=${1:-build}
archive=${2:-build/renderer-software-vulkan.tar.xz}

sdvk_evidence_dirs=()
for sdvk_evidence_dir in renderer-native renderer-sdvk008-control renderer-sdvk008-preflight renderer-sdvk009-content renderer-sdvk009-publication renderer-sdvk010 renderer-sdvk150 renderer-sdvk153 renderer-sdvk158; do
  if [[ -d "$build_root/$sdvk_evidence_dir" ]]; then
    sdvk_evidence_dirs+=("$sdvk_evidence_dir")
  fi
done

if (( ${#sdvk_evidence_dirs[@]} > 0 )); then
  mkdir -p "$(dirname "$archive")"
  echo 'Lossless tar.xz: level 6, 64 MiB dictionary, 2 xz threads; no file filtering'
  XZ_OPT='-6 --threads=2 --lzma2=dict=64MiB' tar -cJf "$archive" -C "$build_root" "${sdvk_evidence_dirs[@]}"
fi

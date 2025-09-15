#!/bin/bash
#
#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
# Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
# SPDX-License-Identifier: LPGL
#
#

# Require OWNER as the first argument; allow REPO as optional (defaults to "PyLegacy")
OWNER="${1:-}"
REPO="${2:-PyLegacy}"
if [[ -z "$OWNER" ]]; then
  echo "Usage: $0 OWNER [REPO]"
  exit 1
fi

PER_PAGE=100
PAGE=1
DELETED=0
export GH_PAGER=cat

while : ; do
  # Get up to 100 failed runs per page
  RUN_IDS=$(gh api "/repos/$OWNER/$REPO/actions/runs?status=failure&per_page=$PER_PAGE&page=$PAGE" \
    --jq '.workflow_runs[] | select(.conclusion=="failure") | .id')

  if [[ -z "$RUN_IDS" ]]; then
    break
  fi

  for RUN_ID in $RUN_IDS; do
    echo "Deleting failed run: $RUN_ID"
    gh api -X DELETE "/repos/$OWNER/$REPO/actions/runs/$RUN_ID"
    ((DELETED++))
  done

  ((PAGE++))
done

echo "Total deleted: $DELETED"
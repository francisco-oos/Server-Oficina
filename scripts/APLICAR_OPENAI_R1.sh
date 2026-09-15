#!/usr/bin/env bash
set -euo pipefail

EXPECTED="0945a438a69ce33b34d532c2b7be7157b88f943b"
CURRENT="$(git rev-parse HEAD)"

if [[ "$CURRENT" != "$EXPECTED" ]]; then
  echo "Base incorrecta. HEAD=$CURRENT; se esperaba $EXPECTED" >&2
  exit 2
fi
git diff --quiet || {
  echo "El árbol tiene cambios locales." >&2
  exit 3
}

git apply --check OPENAI_ALPHA4_R1.patch
git apply OPENAI_ALPHA4_R1.patch

echo "OpenAI R1 aplicado. Ejecute todos los gates antes de push."

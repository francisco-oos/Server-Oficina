#!/usr/bin/env bash
# Funciones de nombrado y protección de releases. Sólo leen; se prueban sin root
# desde tests/test_deploy_contract.py.
#
# Una release instalada nunca se reutiliza ni se sobrescribe: el directorio
# combina VERSION, instante de instalación y commit. Así reinstalar la misma
# VERSION (p. ej. dos candidatos 0.2.0-alpha.1) no pisa en caliente el código
# que `current` está ejecutando y el rollback siempre apunta a bytes intactos.

release_id() {  # release_id SRC STAMP
  local src=$1 stamp=$2 version commit="" dirty=""
  version=$(tr -d '[:space:]' < "$src/VERSION")
  if [[ ! "$version" =~ ^[0-9A-Za-z][0-9A-Za-z.-]*$ ]]; then
    echo "VERSION inválida: '$version'" >&2
    return 1
  fi
  if [[ ! "$stamp" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
    echo "STAMP inválido: '$stamp'" >&2
    return 1
  fi
  if command -v git >/dev/null 2>&1; then
    commit=$(git -c safe.directory="$src" -C "$src" rev-parse --short=12 HEAD 2>/dev/null || true)
    if [[ -n "$commit" && -n "$(git -c safe.directory="$src" -C "$src" status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
      dirty=".dirty"
    fi
  fi
  printf '%s+%s%s%s\n' "$version" "$stamp" "${commit:+.g$commit}" "$dirty"
}

assert_new_release() {  # assert_new_release RELEASE PREVIOUS
  local release=$1 previous=$2
  if [[ -n "$previous" && "$(realpath -m "$release")" == "$(realpath -m "$previous")" ]]; then
    echo "RELEASE_COLLISION: $release es la release activa; no se sobrescribe en caliente" >&2
    return 1
  fi
  if [[ -e "$release" || -L "$release" ]]; then
    echo "RELEASE_COLLISION: $release ya existe; una release instalada no se reutiliza" >&2
    return 1
  fi
}

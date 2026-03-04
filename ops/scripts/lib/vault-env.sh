#!/usr/bin/env bash
# vault-env.sh -- Shared vault root detection for EngramR hooks/scripts.
#
# Source this file from any hook or script to get find_vault_root().
#
# Detection priority:
#   1. Walk up from CWD looking for .arscontexta marker (file or directory)
#   2. git rev-parse --show-toplevel
#   3. PROJECT_DIR environment variable (set by Claude Code)
#   4. Current working directory
#
# Usage:
#   source "$(dirname "$0")/../../ops/scripts/lib/vault-env.sh"
#   VAULT_ROOT="$(find_vault_root)"

find_vault_root() {
    # 1. Walk up from CWD for .arscontexta marker
    local dir
    dir="$(pwd)"
    while [ "$dir" != "/" ]; do
        if [ -e "$dir/.arscontexta" ]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    # 2. Git root fallback
    local git_root
    git_root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [ -n "$git_root" ]; then
        echo "$git_root"
        return 0
    fi

    # 3. PROJECT_DIR env var (set by Claude Code hooks)
    if [ -n "${PROJECT_DIR:-}" ]; then
        echo "$PROJECT_DIR"
        return 0
    fi

    # 4. Current directory as last resort
    pwd
}

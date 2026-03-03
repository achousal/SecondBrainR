#!/usr/bin/env bash
# section-check.sh -- Run integrity checks on code sections
#
# Reads ops/sections.yaml for section definitions and runs targeted checks.
#
# Usage:
#   section-check.sh                    # all sections, summary only
#   section-check.sh core-lib           # single section, verbose
#   section-check.sh --affected core-lib  # section + its dependents
#   section-check.sh --changed          # auto-detect from git diff
#   section-check.sh --validate-skills  # internal: validate skill structure
#   section-check.sh --check-skill-refs # internal: check skill module references
#   section-check.sh --check-doc-links  # internal: check doc internal links
#   section-check.sh --check-templates  # internal: validate template files
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed
#   2 = configuration error

set -uo pipefail

# shellcheck source=lib/vault-env.sh
source "$(dirname "$0")/lib/vault-env.sh"
VAULT_ROOT="$(find_vault_root)"
cd "$VAULT_ROOT"

SECTIONS_FILE="ops/sections.yaml"

# -----------------------------------------------------------------------
# Color output (respects NO_COLOR)
# -----------------------------------------------------------------------
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' BLUE='' BOLD='' RESET=''
fi

# -----------------------------------------------------------------------
# Internal validation subcommands (called by sections.yaml checks)
# -----------------------------------------------------------------------

validate_skills() {
    local pass=0 fail=0
    while IFS= read -r -d '' skill_dir; do
        local skill_file="$skill_dir/SKILL.md"
        local name
        name=$(basename "$skill_dir")
        if [[ ! -f "$skill_file" ]]; then
            echo "FAIL: $name -- missing SKILL.md"
            fail=$((fail + 1))
            continue
        fi
        # Check required frontmatter fields
        local has_name has_desc
        has_name=$(grep -c '^name:' "$skill_file" 2>/dev/null || echo 0)
        has_desc=$(grep -c '^description:' "$skill_file" 2>/dev/null || echo 0)
        if [[ "$has_name" -eq 0 || "$has_desc" -eq 0 ]]; then
            echo "FAIL: $name -- missing required frontmatter (name, description)"
            fail=$((fail + 1))
        else
            pass=$((pass + 1))
        fi
    done < <(find .claude/skills -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    echo ""
    if [[ "$fail" -eq 0 ]]; then
        echo "PASS: $pass skills validated"
    else
        echo "FAIL: $fail/$((pass + fail)) skills have issues"
    fi
    return "$fail"
}

check_skill_refs() {
    # Check that module names referenced in skills exist in the Python library
    local pass=0 fail=0
    local src_dir="_code/src/engram_r"
    while IFS= read -r -d '' skill_file; do
        local name
        name=$(basename "$(dirname "$skill_file")")
        # Extract Python module references (engram_r.module_name patterns)
        local refs
        refs=$(grep -oE 'engram_r\.[a-zA-Z_]+' "$skill_file" 2>/dev/null | sort -u || true)
        for ref in $refs; do
            local mod_name="${ref#engram_r.}"
            if [[ ! -f "$src_dir/$mod_name.py" ]]; then
                echo "FAIL: $name references $ref but $src_dir/$mod_name.py not found"
                fail=$((fail + 1))
            fi
        done
    done < <(find .claude/skills -name 'SKILL.md' -print0 2>/dev/null)
    if [[ "$fail" -eq 0 ]]; then
        echo "PASS: all skill module references resolve"
        pass=1
    fi
    return "$fail"
}

check_doc_links() {
    # Check that markdown links between docs resolve
    local pass=0 fail=0
    while IFS= read -r -d '' doc_file; do
        # Extract relative markdown links: [text](path.md) or [text](path.md#anchor)
        local doc_dir
        doc_dir=$(dirname "$doc_file")
        while IFS= read -r link; do
            [[ -z "$link" ]] && continue
            # Decode percent-encoded characters (e.g., %20 -> space)
            local decoded_link
            decoded_link=$(printf '%b' "${link//%/\\x}")
            local target="$doc_dir/$decoded_link"
            if [[ ! -f "$target" ]]; then
                echo "FAIL: $(basename "$doc_file") -> $link (not found)"
                fail=$((fail + 1))
            fi
        done < <(grep -oE '\]\([^)#]+' "$doc_file" 2>/dev/null | sed 's/\](//' | grep -v '^https\?://' | grep -v '^#' || true)
    done < <(find docs -name '*.md' -print0 2>/dev/null)
    if [[ "$fail" -eq 0 ]]; then
        echo "PASS: all doc links resolve"
        pass=1
    fi
    return "$fail"
}

check_templates() {
    # Verify template files have required YAML frontmatter
    local pass=0 fail=0
    while IFS= read -r -d '' tmpl; do
        local name
        name=$(basename "$tmpl")
        if ! head -1 "$tmpl" | grep -q '^---'; then
            echo "FAIL: $name -- missing YAML frontmatter"
            fail=$((fail + 1))
        else
            pass=$((pass + 1))
        fi
    done < <(find _code/templates -name '*.md' -maxdepth 1 -print0 2>/dev/null)
    if [[ "$fail" -eq 0 ]]; then
        echo "PASS: $pass templates validated"
    fi
    return "$fail"
}

# Handle internal subcommands
case "${1:-}" in
    --validate-skills)  validate_skills; exit $? ;;
    --check-skill-refs) check_skill_refs; exit $? ;;
    --check-doc-links)  check_doc_links; exit $? ;;
    --check-templates)  check_templates; exit $? ;;
esac

# -----------------------------------------------------------------------
# Parse sections.yaml via Python (robust, no awk/yq fragility)
# -----------------------------------------------------------------------

if [[ ! -f "$SECTIONS_FILE" ]]; then
    echo "Error: $SECTIONS_FILE not found" >&2
    exit 2
fi

# Helper: query sections.yaml via Python + pyyaml
_py_sections() {
    (cd "$VAULT_ROOT/_code" && uv run python -c "
import yaml, sys
with open('$VAULT_ROOT/$SECTIONS_FILE') as f:
    data = yaml.safe_load(f)
sections = data.get('sections', {})
query = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else ''

if query == 'names':
    for name in sections:
        print(name)

elif query == 'checks':
    sect = sections.get(arg, {})
    for check in sect.get('checks', []):
        print(check['name'] + '|' + check['cmd'])

elif query == 'label':
    print(sections.get(arg, {}).get('label', arg))

elif query == 'dependents':
    # Find sections whose depends_on includes arg
    for name, sect in sections.items():
        if arg in sect.get('depends_on', []):
            print(name)

elif query == 'paths':
    for p in sections.get(arg, {}).get('paths', []):
        print(p)
" "$@" 2>/dev/null)
}

get_section_names() {
    _py_sections names
}

get_section_checks() {
    _py_sections checks "$1"
}

get_section_label() {
    _py_sections label "$1"
}

get_section_dependents() {
    _py_sections dependents "$1"
}

get_section_paths() {
    _py_sections paths "$1"
}

# -----------------------------------------------------------------------
# Detect changed sections from git
# -----------------------------------------------------------------------

detect_changed_sections() {
    local changed_files
    changed_files=$(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only HEAD 2>/dev/null || echo "")
    if [[ -z "$changed_files" ]]; then
        echo ""
        return
    fi

    local all_sections
    all_sections=$(get_section_names)
    local changed_sections=""

    for sect in $all_sections; do
        local paths
        paths=$(get_section_paths "$sect")
        for path in $paths; do
            if echo "$changed_files" | grep -q "^${path}"; then
                changed_sections="$changed_sections $sect"
                break
            fi
        done
    done
    echo "$changed_sections" | xargs
}

# -----------------------------------------------------------------------
# Run checks for a section
# -----------------------------------------------------------------------

run_section() {
    local section="$1"
    local verbose="${2:-false}"
    local label
    label=$(get_section_label "$section")
    local section_pass=0
    local section_fail=0

    printf "\n${BOLD}${BLUE}  %s${RESET} (%s)\n" "$label" "$section"
    printf "  %s\n" "$(printf '%.0s-' {1..40})"

    while IFS='|' read -r check_name check_cmd; do
        [[ -z "$check_name" ]] && continue
        printf "  %-20s " "$check_name"

        local output exit_code
        output=$(eval "$check_cmd" 2>&1) && exit_code=0 || exit_code=$?

        if [[ "$exit_code" -eq 0 ]]; then
            printf "${GREEN}PASS${RESET}\n"
            section_pass=$((section_pass + 1))
        else
            printf "${RED}FAIL${RESET}\n"
            section_fail=$((section_fail + 1))
        fi

        if [[ "$verbose" == "true" && -n "$output" ]]; then
            echo "$output" | head -20 | sed 's/^/    /'
        elif [[ "$exit_code" -ne 0 && -n "$output" ]]; then
            # Always show failure output (truncated)
            echo "$output" | tail -10 | sed 's/^/    /'
        fi
    done < <(get_section_checks "$section")

    printf "  %s\n" "$(printf '%.0s-' {1..40})"
    if [[ "$section_fail" -eq 0 ]]; then
        printf "  ${GREEN}%d/%d passed${RESET}\n" "$section_pass" "$((section_pass + section_fail))"
    else
        printf "  ${RED}%d/%d failed${RESET}\n" "$section_fail" "$((section_pass + section_fail))"
    fi

    return "$section_fail"
}

# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

MODE="${1:-all}"
TARGET="${2:-}"
TOTAL_PASS=0
TOTAL_FAIL=0
SECTIONS_RUN=0

printf "\n${BOLD}--=={ section check }==-${RESET}\n"

case "$MODE" in
    --affected)
        if [[ -z "$TARGET" ]]; then
            echo "Usage: section-check.sh --affected <section>" >&2
            exit 2
        fi
        sections_to_run="$TARGET $(get_section_dependents "$TARGET")"
        ;;
    --changed)
        sections_to_run=$(detect_changed_sections)
        if [[ -z "$sections_to_run" ]]; then
            printf "\n  No sections changed since last commit.\n\n"
            exit 0
        fi
        printf "\n  Changed sections: %s\n" "$sections_to_run"
        ;;
    all)
        sections_to_run=$(get_section_names)
        ;;
    *)
        # Single section name
        sections_to_run="$MODE"
        ;;
esac

for sect in $sections_to_run; do
    verbose="false"
    # Verbose for single-section runs
    [[ "$MODE" != "all" && "$MODE" != "--changed" ]] && verbose="true"

    if run_section "$sect" "$verbose"; then
        TOTAL_PASS=$((TOTAL_PASS + 1))
    else
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
    SECTIONS_RUN=$((SECTIONS_RUN + 1))
done

printf "\n${BOLD}  Summary: %d sections, ${GREEN}%d healthy${RESET}${BOLD}" "$SECTIONS_RUN" "$TOTAL_PASS"
if [[ "$TOTAL_FAIL" -gt 0 ]]; then
    printf ", ${RED}%d unhealthy${RESET}" "$TOTAL_FAIL"
fi
printf "${RESET}\n\n"

[[ "$TOTAL_FAIL" -eq 0 ]]

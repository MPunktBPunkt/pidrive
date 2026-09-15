#!/bin/bash
# PiDrive: Markdown-Links und Dokumentations-Waisen prüfen (Auftrag D3 / R8)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

errors=0
warn_orphans=0

# --- Relative Markdown-Links prüfen ---
while IFS= read -r -d '' file; do
    dir="$(dirname "$file")"
    while IFS= read -r link; do
        [[ "$link" =~ ^https?:// ]] && continue
        [[ "$link" =~ ^# ]] && continue
        target="${link%%#*}"
        target="${target%%\?*}"
        [[ -z "$target" ]] && continue
        resolved="$(cd "$dir" && realpath -m "$target" 2>/dev/null || echo "")"
        if [[ -z "$resolved" || ! -e "$resolved" ]]; then
            echo "FEHLER: $file → [$link] (Ziel fehlt)"
            errors=$((errors + 1))
        fi
    done < <(grep -oE '\]\([^)]+\)' "$file" | sed 's/](//;s/)$//' | grep '\.md' || true)
done < <(find . -name '*.md' -not -path './.git/*' -print0)

# --- Waisen: docs/*.md ohne eingehenden Link (Index ausgenommen) ---
index="$ROOT/docs/README.md"
linked=()
while IFS= read -r -d '' doc; do
    rel="${doc#./}"
    [[ "$rel" == "docs/README.md" ]] && continue
    [[ "$rel" == "README.md" ]] && continue
    if ! grep -rqF "$rel" --include='*.md' --exclude="$(basename "$doc")" . 2>/dev/null; then
        # auch Kurzform (nur Dateiname) akzeptieren, wenn eindeutig im Index
        base="$(basename "$doc")"
        if grep -qF "$base" "$index" 2>/dev/null; then
            continue
        fi
        echo "WAISEN: $rel (weder verlinkt noch im Index)"
        warn_orphans=$((warn_orphans + 1))
    fi
done < <(find docs -name '*.md' -print0)

if [[ $errors -gt 0 ]]; then
    echo "---"
    echo "$errors Link-Fehler"
    exit 1
fi

if [[ $warn_orphans -gt 0 ]]; then
    echo "---"
    echo "$warn_orphans Waisen-Dokument(e)"
    exit 1
fi

echo "OK: Alle Markdown-Links gültig, keine Waisen."

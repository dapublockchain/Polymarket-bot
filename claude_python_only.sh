#!/usr/bin/env bash
set -e

echo "▶ Setting Python-only Claude permissions (project-local)..."

mkdir -p .claude

cat << 'JSON' > .claude/settings.local.json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(pytest:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)"
    ]
  }
}
JSON

chmod 600 .claude/settings.local.json

echo "✅ Done."
echo "• Scope: project-local (.claude/settings.local.json)"
echo "• python3 / pytest / pip will not ask again"

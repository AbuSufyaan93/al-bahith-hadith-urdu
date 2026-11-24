#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/AbuSufyaan93/al-bahith-hadith-urdu.git"
MAIN_DIR="/tmp/gh_main_repo"
PAGES_DIR="/tmp/gh_pages_site"

echo "[1/3] Pushing clean ~16.5 MB runtime source to main branch..."
if [ ! -d "$MAIN_DIR/.git" ]; then
  git -C "$MAIN_DIR" init -b main
  git -C "$MAIN_DIR" remote add origin "$REPO_URL"
fi
git -C "$MAIN_DIR" add -A
git -C "$MAIN_DIR" commit -m "feat: الباحث الحديثي (Salafi Urdu + Arabic) minimal local runtime & dual-port 8088/8080 launcher" || true
git -C "$MAIN_DIR" push -u origin main --force

echo "[2/3] Pushing compiled serverless static portal to gh-pages branch..."
if [ ! -d "$PAGES_DIR/.git" ]; then
  git -C "$PAGES_DIR" init -b gh-pages
  git -C "$PAGES_DIR" remote add origin "$REPO_URL"
fi
git -C "$PAGES_DIR" add -A
git -C "$PAGES_DIR" commit -m "deploy: الباحث الحديثي live serverless GitHub Pages portal (48,911 Hadiths + 283,601 Rekhta Lexicon)" || true
git -C "$PAGES_DIR" push -u origin gh-pages --force

echo "[3/3] Enabling / refreshing GitHub Pages on gh-pages root..."
gh api repos/AbuSufyaan93/al-bahith-hadith-urdu/pages -X POST \
  -f "source[branch]=gh-pages" -f "source[path]=/" 2>/dev/null || \
gh api repos/AbuSufyaan93/al-bahith-hadith-urdu/pages -X PUT \
  -f "source[branch]=gh-pages" -f "source[path]=/"

echo "[OK] Both main and gh-pages pushed to $REPO_URL"

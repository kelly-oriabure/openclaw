#!/bin/sh
set -e
SKILLS_DEST=/data/workspace/skills
SKILLS_SRC=/defaults/skills

if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_DEST"
  cp -r "$SKILLS_SRC/." "$SKILLS_DEST/"
fi

exec /entrypoint.sh "$@"

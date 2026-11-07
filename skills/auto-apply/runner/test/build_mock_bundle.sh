#!/bin/bash
# Rebuild test/mock_bundle.js from test/mock_app.jsx (only needed when mock_app.jsx changes; the bundle is committed so
# t_verify.js runs offline — JSA-006). Versions used 2026-10-30: react 18.3.1, react-dom 18.3.1, react-select 5.10.2, esbuild 0.28.2.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"; W="$(mktemp -d)"
cd "$W" && npm init -y >/dev/null && npm i --silent --no-audit --no-fund react@18.3.1 react-dom@18.3.1 react-select@5.10.2 esbuild@0.28.2
cp "$HERE/mock_app.jsx" . && ./node_modules/.bin/esbuild mock_app.jsx --bundle --minify --format=iife \
  --define:process.env.NODE_ENV='"production"' --outfile="$HERE/mock_bundle.js"
echo "wrote $HERE/mock_bundle.js"

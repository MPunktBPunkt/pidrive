#!/usr/bin/env bash
# Einzel-run würde data/*.parquet überschreiben → immer voller Scan.
set -euo pipefail
cd /home/martin/projects/pidrive
.venv-ingest/bin/python tools/ingest/ingest.py --root docs/betrieb

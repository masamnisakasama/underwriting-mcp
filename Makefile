# Underwriting Decision MCP — make targets（§23）
# mock 段階（§27-1〜5）で機能するターゲットを実装。AWS 段階（§27-6〜）は
# 実装後に有効化する。未実装ターゲットは「成功を装わず」明示的に失敗させる。

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install lint format typecheck test test-unit test-integration \
        generate-schemas generate-samples demo dev-mcp synth deploy destroy \
        synth-demo-low-cost package-plugin verify-data-boundary check-live-prereqs smoke-test

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"

lint:
	$(PY) -m ruff check underwriting_core underwriting_app underwriting_mcp lambdas tests scripts deploy/cowork/render_config.py plugin/underwriting-review/skills/review-case/scripts/upload_case.py

format:
	$(PY) -m ruff format underwriting_core underwriting_app underwriting_mcp lambdas tests scripts deploy/cowork/render_config.py plugin/underwriting-review/skills/review-case/scripts/upload_case.py

typecheck:
	$(PY) -m mypy underwriting_core underwriting_app underwriting_mcp lambdas

test:
	$(PY) -m pytest

test-unit:
	$(PY) -m pytest tests/unit

test-integration:
	$(PY) -m pytest tests/integration

generate-schemas:
	$(PY) scripts/generate_schemas.py

generate-samples:
	$(PY) scripts/generate_sample_pdfs.py

# ローカル mock end-to-end デモ（AWS 不要, §27-5）
demo:
	$(PY) scripts/run_mock_demo.py

# ローカル Streamable HTTP MCP サーバ（http://127.0.0.1:8000/mcp, §22.3）
dev-mcp:
	APP_MODE=mock ENVIRONMENT=demo $(PY) -m underwriting_mcp

synth:
	npm run synth -- -c allowHttpForLocalSynth=true

synth-demo-low-cost:
	npm run synth -- -c allowHttpForLocalSynth=true -c deploymentMode=demo-low-cost

deploy:
	npm run deploy

destroy:
	npm run destroy

package-plugin:
	mkdir -p dist
	rm -f dist/underwriting-review-plugin.zip
	cd plugin && ../$(PY) -m zipfile -c ../dist/underwriting-review-plugin.zip underwriting-review

verify-data-boundary:
	$(PY) scripts/verify_data_boundary.py

check-live-prereqs:
	$(PY) scripts/check_live_prereqs.py

smoke-test:
	@if [ "$${RUN_AWS_LIVE_TESTS:-0}" != "1" ]; then \
		echo "Set RUN_AWS_LIVE_TESTS=1 with MCP_URL and MCP_BEARER_TOKEN to run live smoke."; \
		exit 2; \
	fi
	$(PY) scripts/check_live_prereqs.py
	$(PY) scripts/smoke_test_mcp.py

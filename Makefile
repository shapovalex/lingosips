.PHONY: dev build test test-server e2e publish lint

dev:
	uvicorn src.lingosips.api.app:app --reload --host 127.0.0.1 --port 7842 & \
	cd frontend && npm run dev -- --port 5173

build:
	# vite.config.ts outDir is set to '../src/lingosips/static', so build outputs directly there.
	# No cp step needed — running npm run build from frontend/ writes straight to src/lingosips/static/.
	cd frontend && npm run build
	uv build

test:
	uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90
	cd frontend && npm run test -- --coverage

test-server:
	LINGOSIPS_ENV=test uv run uvicorn src.lingosips.api.app:app --host 127.0.0.1 --port 7842 --env-file .env.test

e2e:
	cd frontend && npx playwright test

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

publish:
	make build
	uv publish

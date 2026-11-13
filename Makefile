.PHONY: api web test lint compose-up compose-down

api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && PYTHONPATH=. pytest -q

lint:
	cd frontend && npm run lint

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

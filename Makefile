run:
	uvicorn app.main:app --reload --port 8000

tunnel:
	cloudflared tunnel --url http://localhost:8000

# Deployment Guide — SHARED AI SERVICE

## Docker Deployment
```bash
docker-compose up -d --build
```

## Static Documentation Frontend
The FastAPI Documentation Frontend is served directly via FastAPI static mount at `/documentation`.
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`

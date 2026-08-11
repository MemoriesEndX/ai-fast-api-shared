# Rollback Guide — SHARED AI SERVICE

## Rollback Procedure
```bash
docker-compose down
git checkout HEAD~1
docker-compose up -d --build
```

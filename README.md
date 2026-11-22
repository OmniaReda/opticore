# Opticore

AI-powered FTTH/ODN network design platform (prototype).

- Project context for Claude Code: [`CLAUDE.md`](CLAUDE.md)
- Plan & scope: [`docs/01-plan-and-scope.md`](docs/01-plan-and-scope.md)
- Design Team workflow: [`docs/02-design-team-workflow.md`](docs/02-design-team-workflow.md)
- Reference project analysis: [`docs/03-amiriya-stage1-analysis.md`](docs/03-amiriya-stage1-analysis.md)
- Open questions: [`docs/04-open-questions.md`](docs/04-open-questions.md)

## Quick start
Prerequisites: Docker Desktop (Windows: needs WSL2), Python 3.12, Node.js LTS.

```bash
docker compose up -d db                       # PostGIS on localhost:5432

cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head                          # create / update DB schema
uvicorn app.main:app --reload                 # API on :8000, docs on /docs
pytest                                        # uses its own DB "opticore_test"

cd ../frontend
npm install
npm start                                     # http://localhost:4200 (proxies /api → :8000)
npm run api                                   # regenerate the typed API client after backend API changes
```

Put customer files in `data/` (git-ignored). Uploaded files are stored in `backend/storage/` (git-ignored).

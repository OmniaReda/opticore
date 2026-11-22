# Opticore

AI-powered FTTH/ODN network design platform (prototype).

- Project context for Claude Code: [`CLAUDE.md`](CLAUDE.md)
- Plan & scope: [`docs/01-plan-and-scope.md`](docs/01-plan-and-scope.md)
- Design Team workflow: [`docs/02-design-team-workflow.md`](docs/02-design-team-workflow.md)
- Reference project analysis: [`docs/03-amiriya-stage1-analysis.md`](docs/03-amiriya-stage1-analysis.md)
- Open questions: [`docs/04-open-questions.md`](docs/04-open-questions.md)

## Quick start
```bash
docker compose up -d db
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Put customer files in `data/` (git-ignored).

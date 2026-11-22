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
pip install -r requirements-dev.txt                 # runtime + test/lint tools
alembic upgrade head                          # create / update DB schema
uvicorn app.main:app --reload                 # API on :8000, docs on /docs
pytest                                        # uses its own DB "opticore_test"
ruff check . && mypy app tests scripts ../tools    # lint + strict type check

cd ../frontend
npm install
npm start                                     # http://localhost:4200 (proxies /api → :8000)
npm run api                                   # regenerate the typed API client after backend API changes
```

### DWG support (optional)
DWG drawings are converted to DXF with LibreDWG's `dwg2dxf`, run as a separate program (GPL, never bundled; see [`docs/adr/0001-dwg-conversion.md`](docs/adr/0001-dwg-conversion.md)).
Download `libredwg-0.14-win64.zip` from the [LibreDWG 0.14 release](https://github.com/LibreDWG/libredwg/releases/tag/0.14), unzip it, and point the backend at it, e.g. in `backend/.env`:

```
OPTICORE_DWG2DXF_PATH=C:\Users\<you>\AppData\Local\Programs\libredwg-0.14\dwg2dxf.exe
```

Without it, DXF uploads still work. DWG uploads fail with a message asking for a DXF.

CAD layer names and the Building ID format are configured in [`backend/app/rules/cad_layers.yaml`](backend/app/rules/cad_layers.yaml).

Put customer files in `data/` (git-ignored). Uploaded files are stored in `backend/storage/` (git-ignored).

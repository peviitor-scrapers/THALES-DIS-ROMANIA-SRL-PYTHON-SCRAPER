# VERIFY

How to verify the scraper works.

## Offline

```bash
python3 -m pytest tests/unit tests/consistency
```

Expect: all green, no network needed.

## Live — company

```bash
python3 -c "from scraper.anaf import get_company_from_anaf; print(get_company_from_anaf('37180822'))"
```

Expect: `denumire == "THALES DIS ROMANIA S.R.L."`, `cif == "37180822"`.

## Live — board

```bash
python3 -m pytest tests/e2e
```

Expect: `>= 1` jobs scraped, unique URLs, titles present, Romania-filtered board.

## Live — peviitor SOLR

```bash
curl "https://api.peviitor.ro/v1/scraper/jobs/?cif=37180822&rows=500"
```

Expect: `success: true`. Note CIF `37180822` is shared with other peviitor
scrapers (jobviewtrack, ejobs, olx, multijobs, targuldecariere), so the
total count includes their jobs; confirm the scraped Workday apply-URLs
are present.

## Full pipeline

```bash
python3 -m scraper.index
```

Then check:

- `scraper/jobs.json` exists and has jobs.
- `docs/jobs.md` regenerated with the job list.
- `docs/company.json` mirrors `scraper/config/company.json`.
- SOLR count matches scraped count (minus filtered locations).

## GitHub Pages

```bash
gh api repos/elenab01234/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/pages --jq .html_url
curl -s -o /dev/null -w "%{http_code}\n" https://elenab01234.github.io/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/
```

Expect: `https://elenab01234.github.io/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/` and HTTP `200`.
The site is built from `docs/` on `main` (source: branch `main`, path `/docs`).

## GitHub Actions

For each workflow in `.github/workflows/`, run it from **Actions** → *Run workflow* (on `main`) and check all jobs are green:

| Workflow | Trigger | Ce verifici |
|----------|---------|-------------|
| `job-seeker-ro-spider.yml` | `workflow_dispatch` | Scraperul rulează → job-uri în API + `docs/jobs.md` generat |
| `automation-testing.yml` | `workflow_dispatch` | Toate testele + validare job-uri |

After a successful run, verify via API that the company jobs appear:

```bash
curl -s "https://api.peviitor.ro/v1/scraper/jobs/?cif=37180822&rows=500"
```

Check `docs/jobs.md` was regenerated and jobs are visible on https://peviitor.ro (CIF `37180822`).

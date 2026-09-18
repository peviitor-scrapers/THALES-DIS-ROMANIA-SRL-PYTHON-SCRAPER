# Update Repo About

Keep the GitHub repository metadata up to date.

## Description

Scraper automat pentru locurile de muncă THALES DIS ROMANIA S.R.L. (CIF: 37180822) — extrage
de pe careers.thalesgroup.com (board Phenom) și publică pe peviitor.ro

## Homepage

https://peviitor-scrapers.github.io/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/

## Topics (exactly 2, per TOPICS.md)

- job-seeker-ro-spider
- peviitor-ro

## Workflow file

`.github/workflows/job-seeker-ro-spider.yml`

## How to apply

```bash
gh repo edit peviitor-scrapers/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER \
  --description "Scraper automat pentru locurile de muncă THALES DIS ROMANIA S.R.L. (CIF: 37180822) — extrage de pe careers.thalesgroup.com (board Phenom) și publică pe peviitor.ro" \
  --homepage "https://peviitor-scrapers.github.io/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/"
```

## GitHub Pages

- Source: branch `main`, path `/docs` (static site, no Pages workflow needed).
- Builds automatically on every push to `main` (`build_type: legacy`).
- Site: https://peviitor-scrapers.github.io/THALES-DIS-ROMANIA-SRL-PYTHON-SCRAPER/
- `docs/jobs.md` is regenerated on each scrape and served on the site.
- Homepage on the repo points to the Pages URL (same as the EPAM template).
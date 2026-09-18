# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-09-15

### Added
- Adapted the scraper to **THALES DIS ROMANIA S.R.L.** (CIF `37180822`).
- Jobs source: Thales Phenom-powered careers board — Romania search
  (`https://careers.thalesgroup.com/global/en/romania-search-jobs`), job data
  embedded in HTML as `phApp.ddo` JSON, paginated via `?from=N&s=1`.
- Canonical job URLs use the Workday details path
  (`https://thales.wd3.myworkdayjobs.com/en-US/Careers/details/{slug}_{reqId}`),
  not the apply URLs.

### Changed
- `scraper/config/company.json` and `scraper/config/scraper.json` updated for
  THALES DIS ROMANIA S.R.L.
- `scraper/index.py` rewritten to parse the Phenom embedded JSON instead of
  applytojob HTML.
- README, CONTRIBUTING, AI docs, unit/e2e/consistency tests updated to the
  new company and board.

### Removed
- applytojob parsing (`a.job_title_link`, `tr/td` selectors) and the
  `?department=E-INFRA` filter.

## [1.0.0] - 2026-08-03

### Added
- Python scraper for the E-INFRA S.A. department on the group's applytojob board (`?department=E-INFRA`).
- Publisher to peviitor v1 API: company upsert, job upload, stale-job delete.
- ANAF company validation with CUIScan fallback and cache.
- ANOFM job search mirroring the Node.js template.
- `validate_jobs.py` CLI for head/content URL validation.
- Unit, integration, e2e, and consistency tests.
- GitHub Actions workflows: `job-seeker-ro-spider`, `automation-testing`, deep-validate, recovery.
- GitHub Pages (`docs/`) with generated `jobs.md` and `company.json`.
- AI documentation under `ai/`.

### Fixed
- Location normalization: common spellings (`Bucuresti`, `Turda`, etc.) and case/diacritic variants are no longer dropped to `România`.
- Stale-job deletion is scoped to this scraper's board, so jobs published by other peviitor scrapers under the same CIF are never removed.
- E2E `EXPECTED_MIN_JOBS` and integration tests reflect the E-INFRA department and CIF `38647188`.
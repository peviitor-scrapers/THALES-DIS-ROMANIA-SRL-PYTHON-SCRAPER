"""Unit tests for the Phenom board parser."""

import json

from scraper import index


def _phenom_page_html(phenom_jobs, total_hits=2):
    ddo = {
        "eagerLoadRefineSearch": {
            "status": 200,
            "totalHits": total_hits,
            "data": {"jobs": phenom_jobs},
        }
    }
    return (
        '<html><body><script type="text/javascript">'
        f"phApp.ddo = {json.dumps(ddo)};"
        "phApp.experimentData = {};</script></body></html>"
    )


SAMPLE_JOB_1 = {
    "reqId": "R0330940",
    "title": "Team Manager - Software Engineering",
    "applyUrl": "https://thales.wd3.myworkdayjobs.com/Careers/job/Bucharest/Team-Manager_R0330940/apply",
    "city": "Bucharest",
    "workLocation": "Bucharest",
    "country": "Romania",
    "postedDate": "2026-06-15T00:00:00.000+0000",
}

SAMPLE_JOB_2 = {
    "reqId": "R0330941",
    "title": "C++ Software Engineer - Defence Naval",
    "applyUrl": "https://thales.wd3.myworkdayjobs.com/Careers/job/Bucharest/Cpp-Engineer_R0330941/apply",
    "city": "Bucharest Orhideea",
    "workLocation": "Bucharest Orhideea",
    "country": "Romania",
    "postedDate": "2026-07-01T00:00:00.000+0000",
}


def test_build_listing_url(scraper_config):
    url = index.build_listing_url()
    assert url.startswith("https://")
    assert "careers.thalesgroup.com" in url
    assert "romania-search-jobs" in url
    assert index.build_listing_url(10).endswith("?from=10&s=1")


def test_build_job_url():
    assert index.build_job_url("R0330940").startswith("https://thales.wd3.myworkdayjobs.com/Careers/job/")


def test_extract_location_takes_first_token():
    assert index._extract_location("Bucharest, 060071") == ["Bucharest"]
    assert index._extract_location("Bucharest Orhideea") == ["Bucharest Orhideea"]


def test_extract_location_single_token():
    assert index._extract_location("Romania") == ["România"]


def test_extract_location_missing():
    assert index._extract_location(None) == []
    assert index._extract_location("") == []


def test_parse_api_jobs():
    html = _phenom_page_html([SAMPLE_JOB_1, SAMPLE_JOB_2])
    jobs = index.parse_api_jobs(html)
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Team Manager - Software Engineering"
    assert jobs[0]["url"] == SAMPLE_JOB_1["applyUrl"]
    assert jobs[0]["location"] == ["Bucharest"]
    assert jobs[0]["date"] == SAMPLE_JOB_1["postedDate"]


def test_parse_api_jobs_keeps_duplicate_rows():
    html = _phenom_page_html([SAMPLE_JOB_1, SAMPLE_JOB_1])
    jobs = index.parse_api_jobs(html)
    assert len(jobs) == 2


def test_scrape_all_listings_deduplicates(monkeypatch):
    page_a = _phenom_page_html([SAMPLE_JOB_1, SAMPLE_JOB_2], total_hits=2)
    page_b = _phenom_page_html([SAMPLE_JOB_1], total_hits=2)
    monkeypatch.setattr(index, "fetch_listing", lambda url: page_a if "from=0" in url else page_b)
    jobs = index.scrape_all_listings()
    ids = [j["url"] for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate job URLs found"


def test_parse_api_jobs_empty():
    assert index.parse_api_jobs("<html></html>") == []


def test_parse_api_jobs_no_ddo():
    html = "<html><body><script>var x = 1;</script></body></html>"
    assert index.parse_api_jobs(html) == []


def test_map_to_job_model_adds_company_and_status():
    raw = {"url": SAMPLE_JOB_1["applyUrl"],
           "title": "Team Manager", "location": ["Bucharest"],
           "date": "2026-06-15T00:00:00.000+0000"}
    index.COMPANY_NAME = "THALES DIS ROMANIA S.R.L."
    job = index.map_to_job_model(raw, "37180822")
    assert job["company"] == "THALES DIS ROMANIA S.R.L."
    assert job["cif"] == "37180822"
    assert job["status"] == "scraped"
    assert job["location"] == ["Bucharest"]
    assert job["date"] == "2026-06-15T00:00:00Z"


def test_map_to_job_model_default_date():
    raw = {"url": SAMPLE_JOB_1["applyUrl"], "title": "Team Manager",
           "location": ["Bucharest"]}
    job = index.map_to_job_model(raw, "37180822")
    assert job["date"].endswith("Z")


def test_transform_jobs_for_solr_keeps_required_fields():
    jobs = [{"url": "https://x/job", "title": "Test Job", "location": ["Bucharest"],
             "company": "THALES DIS ROMANIA S.R.L.", "cif": "37180822"}]
    transformed = index.transform_jobs_for_solr({"company": "THALES DIS ROMANIA S.R.L.", "jobs": jobs})
    assert len(transformed["jobs"]) == 1
    t = transformed["jobs"][0]
    assert t["url"]
    assert t["title"]
    assert t["location"] == ["Bucharest"]
    assert t["company"] == "THALES DIS ROMANIA S.R.L."


def test_transform_workmode_normalized():
    jobs = [{"url": "https://x/1", "title": "Dev", "location": ["Bucharest"], "workmode": "Remote"}]
    transformed = index.transform_jobs_for_solr({"company": "THALES DIS ROMANIA S.R.L.", "jobs": jobs})
    assert transformed["jobs"][0]["workmode"] == "remote"


def test_transform_missing_workmode_dropped():
    jobs = [{"url": "https://x/1", "title": "Dev", "location": ["Bucharest"]}]
    transformed = index.transform_jobs_for_solr({"company": "THALES DIS ROMANIA S.R.L.", "jobs": jobs})
    assert "workmode" not in transformed["jobs"][0]


def test_generate_jobs_markdown(tmp_path, company_config):
    jobs = [{"url": "https://x/job", "title": "Team Manager",
             "company": "THALES DIS ROMANIA S.R.L.", "cif": "37180822",
             "location": ["Bucharest"], "workmode": "on-site"}]
    md = index.generate_jobs_markdown(company_config, jobs)
    assert f"# {company_config['company']}" in md
    assert "## Jobs (1)" in md
    assert "Team Manager" in md
    assert "](https://x/job)" in md


def test_generate_jobs_markdown_empty():
    md = index.generate_jobs_markdown({}, [])
    assert "## Jobs (0)" in md
    assert "_No jobs found._" in md


def test_main_dry_run_writes_summary(tmp_path, monkeypatch):
    fake_jobs = [{"url": f"https://x/{i}", "title": f"Job {i}", "location": ["Bucharest"]}
                 for i in range(3)]
    monkeypatch.setattr(index, "scrape_all_listings", lambda: fake_jobs)
    monkeypatch.setattr(index, "query_solr", lambda cif: {"numFound": 1, "docs": []})
    monkeypatch.setattr(index, "upsert_jobs", lambda jobs: None)
    monkeypatch.setattr(index, "delete_job_by_url", lambda url: None)
    monkeypatch.setattr(index, "upsert_company", lambda cfg: None)
    monkeypatch.setattr(index, "validate_and_get_company", lambda: {
        "company": "THALES DIS ROMANIA S.R.L.", "cif": "37180822", "status": "active",
        "address": "BUCURESTI"})
    monkeypatch.setattr(index, "search_anofm", lambda cif: [])

    index.main(root=tmp_path)
    out = tmp_path / "scraper" / "jobs.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert len(data["jobs"]) >= 3
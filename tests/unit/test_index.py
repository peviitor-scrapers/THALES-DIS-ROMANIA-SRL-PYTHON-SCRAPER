"""Unit tests for the Phenom and Workday board parsers."""

import datetime
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

DETAILS_PREFIX = "https://thales.wd3.myworkdayjobs.com/en-US/Careers/details/"


def test_build_listing_url(scraper_config):
    url = index.build_listing_url()
    assert url.startswith("https://")
    assert "careers.thalesgroup.com" in url
    assert "romania-search-jobs" in url
    assert index.build_listing_url(10).endswith("?from=10&s=1")


def test_build_job_url():
    url = index.build_job_url("Java Software Engineer - Naval Business", "R0161685")
    assert url == "https://thales.wd3.myworkdayjobs.com/en-US/Careers/details/Java-Software-Engineer_R0161685"


def test_build_job_url_en_dash_split():
    url = index.build_job_url("Senior Front-End Developer (UI Components) – Quantum", "R0336024")
    assert url == DETAILS_PREFIX + "Senior-Front-End-Developer-UI-Components_R0336024"


def test_build_job_url_no_separator():
    url = index.build_job_url("HR Business Partner", "R0333338")
    assert url == DETAILS_PREFIX + "HR-Business-Partner_R0333338"


def test_build_job_url_prefers_apply_url_slug():
    url = index.build_job_url(
        "IVQ Infrastructure Engineer (NATO Project)",
        "R0337371",
        "https://thales.wd3.myworkdayjobs.com/Careers/job/Bucharest/"
        "IVQ-Operations-Engineer--NATO-Project-_R0337371/apply",
    )
    assert url == DETAILS_PREFIX + "IVQ-Operations-Engineer--NATO-Project-_R0337371"


def test_build_job_url_keeps_workday_revision_suffix():
    url = index.build_job_url(
        "C++ Software Engineer - Defence Naval Business",
        "R0190603",
        "https://thales.wd3.myworkdayjobs.com/Careers/job/Bucharest/"
        "C-C---Software-Engineer---Defence-Naval-Business_R0190603-1/apply",
    )
    assert url == DETAILS_PREFIX + "C-C---Software-Engineer---Defence-Naval-Business_R0190603-1"


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
    assert jobs[0]["url"] == DETAILS_PREFIX + "Team-Manager_R0330940"
    assert jobs[1]["url"] == DETAILS_PREFIX + "Cpp-Engineer_R0330941"
    assert jobs[0]["location"] == ["Bucharest"]
    assert jobs[0]["date"] == SAMPLE_JOB_1["postedDate"]


def test_parse_api_jobs_keeps_duplicate_rows():
    html = _phenom_page_html([SAMPLE_JOB_1, SAMPLE_JOB_1])
    jobs = index.parse_api_jobs(html)
    assert len(jobs) == 2


def test_scrape_all_listings_deduplicates(monkeypatch):
    page_a = _phenom_page_html([SAMPLE_JOB_1, SAMPLE_JOB_2], total_hits=2)
    page_b = _phenom_page_html([SAMPLE_JOB_1], total_hits=2)
    monkeypatch.setattr(index, "scrape_workday_listings", lambda: [])
    monkeypatch.setattr(index, "fetch_listing", lambda url: page_a if "from=0" in url else page_b)
    jobs = index.scrape_all_listings()
    ids = [j["url"] for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate job URLs found"


def test_scrape_all_listings_prefers_workday(monkeypatch):
    workday_jobs = [{"url": DETAILS_PREFIX + "Only-Workday_R1", "title": "Only Workday",
                     "location": ["Bucharest"], "date": "2026-11-14T00:00:00.000+0000"}]
    monkeypatch.setattr(index, "scrape_workday_listings", lambda: workday_jobs)
    monkeypatch.setattr(index, "scrape_phenom_listings",
                        lambda: (_ for _ in ()).throw(AssertionError("Phenom fallback used")))
    assert index.scrape_all_listings() == workday_jobs


def test_scrape_workday_listings_paginates_and_uses_external_path(monkeypatch):
    pages = {
        0: {"total": 3, "jobPostings": [
            {"title": "A", "externalPath": "/job/Bucharest/A_R1",
             "locationsText": "Bucharest", "postedOn": "Posted Today"},
            {"title": "B", "externalPath": "/job/Bucharest/B_R2",
             "locationsText": "Bucharest", "postedOn": "Posted 3 Days Ago"},
        ]},
        20: {"total": 3, "jobPostings": [
            {"title": "C", "externalPath": "/job/Cluj-Napoca/C_R3",
             "locationsText": "Cluj-Napoca", "postedOn": "Posted Yesterday"},
        ]},
    }
    monkeypatch.setattr(index, "fetch_workday_page", lambda offset: pages[offset])
    monkeypatch.setattr(index.time, "sleep", lambda _: None)

    jobs = index.scrape_workday_listings()

    assert len(jobs) == 3
    assert [j["url"] for j in jobs] == [
        DETAILS_PREFIX + "A_R1",
        DETAILS_PREFIX + "B_R2",
        DETAILS_PREFIX + "C_R3",
    ]
    assert jobs[2]["location"] == ["Cluj-Napoca"]


def test_workday_posted_date_relative():
    now = datetime.datetime(2026, 11, 14, tzinfo=datetime.timezone.utc)
    assert index._workday_posted_date("Posted Today", now) == "2026-11-14T00:00:00.000+0000"
    assert index._workday_posted_date("Posted Yesterday", now) == "2026-11-13T00:00:00.000+0000"
    assert index._workday_posted_date("Posted 3 Days Ago", now) == "2026-11-11T00:00:00.000+0000"
    assert index._workday_posted_date("Posted 30+ Days Ago", now) == "2026-10-15T00:00:00.000+0000"


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
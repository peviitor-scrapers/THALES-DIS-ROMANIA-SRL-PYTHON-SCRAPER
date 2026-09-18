"""
THALES DIS ROMANIA S.R.L. Phenom Scraper

Scrapes THALES DIS ROMANIA S.R.L. job listings from the Thales careers
Phenom-powered board (careers.thalesgroup.com) and publishes them to
peviitor.ro through the v1 API (api.peviitor.ro/v1) — no direct Solr
access.
"""

import datetime
import json
import pathlib
import re
import sys
import time

import requests

from .anaf import search_anofm
from .api import delete_job_by_url, delete_jobs_by_cif, query_solr, upsert_company, upsert_jobs
from .company import validate_and_get_company
from .config import company_config, scraper_config
from .markdown_generator import generate_jobs_markdown

TIMEOUT = 15
HEADERS = {"User-Agent": "job_seeker_ro_spider"}

COMPANY_CIF = company_config["id"]
API_BASE = scraper_config["apiBase"]
API_PATH = scraper_config["apiPath"]
JOB_DETAILS_PREFIX = scraper_config["jobDetailsPrefix"]

COMPANY_NAME = None

_PHENOM_JOBS_RE = re.compile(
    r"phApp\.ddo\s*=\s*(\{.*?\});\s*phApp\.experimentData", re.S
)


def build_listing_url(offset=0):
    """Builds the Phenom search landing-page URL."""
    url = f"{API_BASE}{API_PATH}"
    if offset > 0:
        url = f"{url}?from={offset}&s=1"
    return url


def _slugify(title):
    """Builds the Workday URL alias: the title before its first ' - ' / ' – '
    / ' — ' / ' | ' separator, with runs of non-alphanumeric chars collapsed
    to single hyphens (e.g. 'Java Software Engineer - Naval Business' →
    'Java-Software-Engineer')."""
    t = (title or "").strip()
    m = re.search(r"\s+(?:—|–|-|\|)\s+", t)
    if m:
        t = t[: m.start()]
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")


def build_job_url(job_title, job_id):
    """Builds the canonical Workday details URL from a Thales reqId
    (e.g. R0161685), NOT the apply URL:
    https://thales.wd3.myworkdayjobs.com/en-US/Careers/details/{slug}_{reqId}"""
    return f"{JOB_DETAILS_PREFIX}{_slugify(job_title)}_{job_id}"


def _parse_jobs_from_page(html):
    """Extracts jobs from the embedded ``phApp.ddo`` JSON in a Phenom page."""
    m = _PHENOM_JOBS_RE.search(html)
    if not m:
        return [], None
    ddo = json.loads(m.group(1))
    refine = ddo.get("eagerLoadRefineSearch") or {}
    data = refine.get("data") or {}
    total = refine.get("totalHits")
    return data.get("jobs", []), total


def _map_raw_job(phenom_job):
    """Maps a raw Phenom job object to the internal raw-job dict."""
    city = phenom_job.get("city") or phenom_job.get("workLocation") or "Romania"
    return {
        "url": build_job_url(phenom_job.get("title"), phenom_job["reqId"]),
        "title": (phenom_job.get("title") or "").strip(),
        "location": _extract_location(city),
        "date": phenom_job.get("postedDate"),
    }


def _extract_location(location_text):
    """Extracts the city from a location string like 'Bucharest' or
    'Bucharest, 060071'."""
    if not location_text:
        return []
    first = location_text.split(",")[0].strip()
    if not first:
        return []
    if first.lower() in ("romania", "românia", "romania -"):
        return ["România"]
    return [first]


def parse_api_jobs(html):
    """Parses a single Phenom page HTML into raw job dicts."""
    jobs_phenom, _ = _parse_jobs_from_page(html)
    return [_map_raw_job(j) for j in jobs_phenom if j.get("reqId")]


def fetch_listing(url):
    """Fetches a single board page and returns its HTML."""
    res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if res.status_code != 200:
        raise RuntimeError(f"Listing error: {res.status_code} for {url}")
    return res.text


def scrape_all_listings():
    """Fetches all Romania job pages from the Phenom board and returns
    de-duplicated raw job dicts."""
    seen_ids = set()
    raw_jobs = []
    total_hits = None
    for offset in range(0, 200, 10):
        url = build_listing_url(offset)
        html = fetch_listing(url)
        jobs_phenom, total = _parse_jobs_from_page(html)
        if total is not None:
            total_hits = total
        page_new = 0
        for j in jobs_phenom:
            rid = j.get("reqId")
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            raw_jobs.append(_map_raw_job(j))
            page_new += 1
        if page_new == 0 or (total_hits and len(raw_jobs) >= total_hits):
            break
        time.sleep(1)
    return raw_jobs


def map_to_job_model(raw_job, cif, company_name=None):
    """Maps a raw job dict to the standardized job model."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date = raw_job.get("date") or now
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{4})?$", date)
    if m:
        date = m.group(1) + "Z"
    job = {
        "url": raw_job["url"],
        "title": raw_job["title"],
        "company": company_name or COMPANY_NAME,
        "cif": cif,
        "date": date,
        "status": "scraped",
    }
    if raw_job.get("location"):
        job["location"] = raw_job["location"]
    return job


_ROMANIAN_CITIES = [
    "Bucharest", "București", "Bucuresti", "Cluj-Napoca", "Cluj Napoca",
    "Timișoara", "Timisoara", "Iași", "Iasi", "Brașov", "Brasov",
    "Constanța", "Constanta", "Craiova", "Bacău", "Sibiu",
    "Târgu Mureș", "Targu Mures", "Oradea", "Baia Mare", "Satu Mare",
    "Ploiești", "Ploiesti", "Pitești", "Pitesti", "Arad", "Galați", "Galati",
    "Brăila", "Braila", "Drobeta-Turnu Severin", "Râmnicu Vâlcea", "Ramnicu Valcea",
    "Buzău", "Buzau", "Botoșani", "Botosani", "Zalău", "Zalau", "Hunedoara", "Deva",
    "Suceava", "Bistrița", "Bistrita", "Tulcea", "Călărași", "Calarasi",
    "Giurgiu", "Alba Iulia", "Slatina", "Piatra Neamț", "Piatra Neamt",
    "Piatra-Neamt", "Roman", "Turda", "Câmpia Turzii", "Campia Turzii",
    "Medgidia", "Gura Ialomiței", "Gura Ialomitei",
    "Dumbrăvița", "Dumbravita", "Voluntari", "Popești-Leordeni", "Popesti-Leordeni",
    "Chitila", "Mogoșoaia", "Mogosoaia", "Otopeni",
]

_DIACRITIC_MAP = str.maketrans("ăâîșțĂÂÎȘȚ", "aaistAAIST")


def _normalize_city(city):
    """Normalizes a city name: lowercase, no diacritics, no hyphen/double spaces."""
    if not city:
        return ""
    normalized = city.lower().translate(_DIACRITIC_MAP)
    return " ".join(normalized.replace("-", " ").split())


_CITY_SET = {_normalize_city(c) for c in _ROMANIAN_CITIES}


def _normalize_workmode(workmode):
    if not workmode:
        return None
    lower = workmode.lower()
    if "remote" in lower:
        return "remote"
    if "office" in lower or "on-site" in lower or "site" in lower:
        return "on-site"
    return "hybrid"


def transform_jobs_for_solr(payload):
    """Filters jobs to Romanian cities and normalizes workmode."""
    company = (payload.get("company") or "").upper()

    transformed_jobs = []
    for job in payload.get("jobs", []):
        locations = []
        for loc in job.get("location") or []:
            normalized = _normalize_city(loc)
            if normalized in ("romania", "românia"):
                locations.append("România")
            elif normalized in _CITY_SET:
                locations.append(loc)
        new_job = {
            **job,
            "location": locations if locations else ["România"],
            "workmode": _normalize_workmode(job.get("workmode")),
        }
        if new_job["workmode"] is None:
            del new_job["workmode"]
        transformed_jobs.append(new_job)

    return {**payload, "company": company, "jobs": transformed_jobs}


def main(root=None):
    test_only_one_page = "--test" in sys.argv
    root = root or pathlib.Path(__file__).resolve().parents[1]

    print("=== Step 1: Get existing jobs from SOLR ===")
    existing_result = query_solr(COMPANY_CIF)
    existing_count = existing_result["numFound"]
    existing_urls = {doc.get("url") for doc in existing_result["docs"]
                     if doc.get("url") and doc["url"].startswith(JOB_DETAILS_PREFIX)}
    print(f"Found {existing_count} existing jobs in SOLR ({len(existing_urls)} from this board)")

    print("=== Step 2: Validate company via ANAF ===")
    validated = validate_and_get_company()
    global COMPANY_NAME
    COMPANY_NAME = validated["company"]
    if validated["status"] == "inactive":
        print("⚠️ Company is INACTIVE — deleting jobs and skipping scrape.")
        try:
            delete_jobs_by_cif(validated["cif"])
            print(f"✅ Deleted all jobs for CIF {validated['cif']}")
        except Exception as del_err:
            print(f"⚠️ Failed to delete jobs for CIF {validated['cif']}: {del_err}")
        return

    try:
        upsert_company({
            "id": validated["cif"],
            "company": validated["company"],
            "brand": company_config.get("brand"),
            "status": "activ",
            "location": [validated["address"]] if validated["address"] else company_config["location"],
            "website": company_config.get("website"),
            "career": company_config.get("career"),
            "scraperFile": company_config.get("scraperFile"),
            "lastScraped": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        })
    except Exception as err:
        print(f"Note: Could not upsert company: {err}")

    print("=== Step 3: Scrape THALES DIS ROMANIA S.R.L. jobs from Phenom board ===")
    raw_jobs = scrape_all_listings()
    scraped_count = len(raw_jobs)
    print(f"Jobs scraped from the Thales Phenom board: {scraped_count}")

    if not test_only_one_page:
        anofm_jobs = search_anofm(validated["cif"])
        anofm_count = len(anofm_jobs)
        known_urls = {j["url"] for j in raw_jobs}
        for job in anofm_jobs:
            if job["url"] not in known_urls:
                raw_jobs.append(job)
                known_urls.add(job["url"])
        print(f"Jobs added from ANOFM: {anofm_count}")

    jobs = [map_to_job_model(job, validated["cif"]) for job in raw_jobs]

    payload = {
        "source": "careers.thalesgroup.com",
        "scrapedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "company": COMPANY_NAME,
        "cif": validated["cif"],
        "jobs": jobs,
    }

    print("Transforming jobs for SOLR...")
    transformed_payload = transform_jobs_for_solr(payload)
    valid_count = len([j for j in transformed_payload["jobs"] if j.get("location")])
    print(f"Jobs with valid Romanian locations: {valid_count}")

    root = root or pathlib.Path(__file__).resolve().parents[1]

    jobs_path = root / "scraper" / "jobs.json"
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(
        json.dumps(transformed_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved scraper/jobs.json")

    company_data = {
        "id": validated["cif"],
        "company": transformed_payload["company"],
        "brand": company_config.get("brand"),
        "status": "activ",
        "location": [validated["address"]] if validated["address"] else company_config["location"],
        "website": company_config.get("website"),
        "career": company_config.get("career"),
        "lastScraped": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
    }
    markdown = generate_jobs_markdown(company_data, transformed_payload["jobs"])
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "jobs.md").write_text(markdown, encoding="utf-8")
    print("Saved docs/jobs.md")

    src_company = pathlib.Path(__file__).resolve().parent / "config" / "company.json"
    (root / "docs" / "company.json").write_text(src_company.read_text(encoding="utf-8"), encoding="utf-8")
    print("Copied scraper/config/company.json → docs/company.json")

    print("\n=== Step 4: Upsert jobs to SOLR ===")
    upsert_jobs(transformed_payload["jobs"])

    scraped_urls = {job["url"] for job in transformed_payload["jobs"]}
    stale_urls = [url for url in existing_urls if url not in scraped_urls]

    if stale_urls:
        print(f"\n=== Step 4.5: Delete {len(stale_urls)} stale job(s) ===")
        deleted_count = 0
        for url in stale_urls:
            try:
                print(f"  Deleting: {url}")
                delete_job_by_url(url)
                deleted_count += 1
            except Exception as del_err:
                print(f"  ⚠️ Failed to delete: {url} — {del_err}")
        print(f"✅ Deleted {deleted_count}/{len(stale_urls)} stale job(s)")
    else:
        print("\n✅ No stale jobs to delete")

    print("\n=== Step 5: Summary ===")
    time.sleep(2)
    final_result = query_solr(COMPANY_CIF)
    print(f"\n=== SUMMARY ===")
    print(f"Jobs existing in SOLR before scrape: {existing_count}")
    print(f"Jobs scraped from the Thales Phenom board: {scraped_count}")
    print(f"Stale jobs attempted: {len(stale_urls)}")
    print(f"Jobs in SOLR after scrape: {final_result['numFound']}")
    print(f"====================")

    print("\n=== DONE ===")
    print("Scraper completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print("Scraper failed:", err)
        sys.exit(1)

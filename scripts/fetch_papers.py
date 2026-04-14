#!/usr/bin/env python3
"""
Fetch latest Moyamoya disease research papers from PubMed E-utilities API.
Uses search templates from moyamoya_disease_journals_keywords_pubmed_templates.md.
"""

import json
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote_plus

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

SEARCH_QUERIES = [
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract] OR "moyamoya angiopathy"[Title/Abstract]) AND (stroke OR ischemia OR hemorrhage OR perfusion OR revascularization)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (revascularization OR bypass OR "STA-MCA" OR EDAS OR encephaloduroarteriosynangiosis) AND (outcome OR complications OR prognosis OR follow-up)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (child* OR pediatric OR paediatric OR adolescent) AND (cognition OR developmental outcome OR school OR intelligence OR "quality of life")',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya angiopathy"[Title/Abstract]) AND (adult OR adulthood) AND ("neuropsychological outcome" OR cognition OR "executive function" OR memory OR attention OR "processing speed")',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (neuropsychiatric OR psychiatric OR depression OR anxiety OR behavior OR emotional OR psychosocial)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya angiopathy"[Title/Abstract]) AND ("cerebrovascular reserve" OR "cerebrovascular reactivity" OR perfusion OR hemodynamics OR "arterial spin labeling" OR SPECT OR PET OR "CT perfusion" OR DTI OR fMRI)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (rehabilitation OR neurorehabilitation OR "functional recovery" OR disability OR participation)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND ("physical therapy" OR physiotherapy OR gait OR balance OR mobility OR "motor recovery" OR exercise)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND ("occupational therapy" OR ADL OR IADL OR participation OR "executive function" OR "school function")',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND ("speech therapy" OR "speech-language pathology" OR aphasia OR dysarthria OR "cognitive-communication" OR dysphagia OR swallowing)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND ("quality of life" OR participation OR "return to school" OR "return to work" OR caregiver OR family)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya angiopathy"[Title/Abstract]) AND (revascularization OR bypass) AND ("cognitive recovery" OR cognition OR "executive function" OR "neuropsychological outcome")',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (longitudinal OR prospective OR retrospective OR cohort OR registry) AND (outcome OR cognition OR stroke OR revascularization)',
    '("moyamoya disease"[Title/Abstract] OR "moyamoya syndrome"[Title/Abstract]) AND (review[Publication Type] OR systematic[sb] OR meta-analysis[Publication Type])',
]

HEADERS = {"User-Agent": "MoyamoyaBrainBot/1.0 (research aggregator)"}


def add_date_filter(query: str, days: int = 7) -> str:
    lookback = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y/%m/%d")
    return (
        f'({query}) AND "{lookback}"[Date - Publication] : "3000"[Date - Publication]'
    )


def search_papers(query: str, retmax: int = 20) -> list[str]:
    params = (
        f"?db=pubmed&term={quote_plus(query)}&retmax={retmax}&sort=date&retmode=json"
    )
    url = PUBMED_SEARCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[ERROR] PubMed search failed: {e}", file=sys.stderr)
        return []


def fetch_details(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = f"?db=pubmed&id={ids}&retmode=xml"
    url = PUBMED_FETCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as resp:
            xml_data = resp.read().decode()
    except Exception as e:
        print(f"[ERROR] PubMed fetch failed: {e}", file=sys.stderr)
        return []

    papers = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            art = medline.find(".//Article") if medline else None
            if art is None:
                continue
            title_el = art.find(".//ArticleTitle")
            title = (
                (title_el.text or "").strip()
                if title_el is not None and title_el.text
                else ""
            )
            abstract_parts = []
            for abs_el in art.findall(".//Abstract/AbstractText"):
                label = abs_el.get("Label", "")
                text = "".join(abs_el.itertext()).strip()
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:2000]
            journal_el = art.find(".//Journal/Title")
            journal = (
                (journal_el.text or "").strip()
                if journal_el is not None and journal_el.text
                else ""
            )
            pub_date = art.find(".//PubDate")
            date_str = ""
            if pub_date is not None:
                year = pub_date.findtext("Year", "")
                month = pub_date.findtext("Month", "")
                day = pub_date.findtext("Day", "")
                parts = [p for p in [year, month, day] if p]
                date_str = " ".join(parts)
            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            keywords = []
            for kw in medline.findall(".//KeywordList/Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())
            authors = []
            for author in art.findall(".//AuthorList/Author"):
                last = author.findtext("LastName", "")
                fore = author.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {fore}".strip())
            papers.append(
                {
                    "pmid": pmid,
                    "title": title,
                    "journal": journal,
                    "date": date_str,
                    "abstract": abstract,
                    "url": link,
                    "keywords": keywords,
                    "authors": authors[:5],
                }
            )
    except ET.ParseError as e:
        print(f"[ERROR] XML parse failed: {e}", file=sys.stderr)
    return papers


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Moyamoya disease papers from PubMed"
    )
    parser.add_argument("--days", type=int, default=7, help="Lookback days")
    parser.add_argument(
        "--max-papers", type=int, default=40, help="Max papers to fetch"
    )
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    all_pmids = set()
    for i, query in enumerate(SEARCH_QUERIES):
        dated_query = add_date_filter(query, days=args.days)
        print(
            f"[INFO] Running search template {i + 1}/{len(SEARCH_QUERIES)}...",
            file=sys.stderr,
        )
        pmids = search_papers(dated_query, retmax=15)
        all_pmids.update(pmids)
        print(
            f"  -> Found {len(pmids)} new PMIDs (total unique: {len(all_pmids)})",
            file=sys.stderr,
        )

    pmid_list = list(all_pmids)[: args.max_papers]
    print(
        f"[INFO] Fetching details for {len(pmid_list)} unique papers...",
        file=sys.stderr,
    )

    if not pmid_list:
        print("NO_CONTENT", file=sys.stderr)
        if args.json:
            print(
                json.dumps(
                    {
                        "date": datetime.now(timezone(timedelta(hours=8))).strftime(
                            "%Y-%m-%d"
                        ),
                        "count": 0,
                        "papers": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return

    papers = fetch_details(pmid_list)
    print(f"[INFO] Fetched details for {len(papers)} papers", file=sys.stderr)

    output_data = {
        "date": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d"),
        "count": len(papers),
        "papers": papers,
    }
    out_str = json.dumps(output_data, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(out_str)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"[INFO] Saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

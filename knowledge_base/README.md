# Knowledge base

Curated reference documents used for retrieval-augmented generation (RAG).

## Source policy

- Only legally reusable material from authoritative public sources, checked against each source's reuse
  terms before it is added.
- A source must be listed in `sources/manifest.json` before it can be ingested. Ingestion fails if a
  document is not approved, its URL does not match the manifest, or an approved source is missing.
- Text is copied from the source, not paraphrased or written from memory. Every chunk keeps its title,
  section, URL, publisher and licence.
- General references explain what a test measures. They are never evidence that a specific patient has
  a condition.

## Current sources

All 20 documents are **MedlinePlus "Medical test information" pages from the U.S. National Library of
Medicine**. MedlinePlus states that this content is produced by the federal government and is in the
public domain ([Linking to and Using Content from MedlinePlus](https://medlineplus.gov/about/using/usingcontent/),
checked 2026-10-27). Attribution: *Source: MedlinePlus, National Library of Medicine.* Pages with
third-party copyrighted content (such as the A.D.A.M. Medical Encyclopedia) are rejected by the fetch script.

| Title | URL |
| --- | --- |
| How to Understand Your Lab Results | https://medlineplus.gov/lab-tests/how-to-understand-your-lab-results/ |
| Complete Blood Count (CBC) | https://medlineplus.gov/lab-tests/complete-blood-count-cbc/ |
| Hemoglobin Test | https://medlineplus.gov/lab-tests/hemoglobin-test/ |
| Hematocrit Test | https://medlineplus.gov/lab-tests/hematocrit-test/ |
| White Blood Count (WBC) | https://medlineplus.gov/lab-tests/white-blood-count-wbc/ |
| Platelet Tests | https://medlineplus.gov/lab-tests/platelet-tests/ |
| Blood Glucose Test | https://medlineplus.gov/lab-tests/blood-glucose-test/ |
| Hemoglobin A1C (HbA1c) Test | https://medlineplus.gov/lab-tests/hemoglobin-a1c-hba1c-test/ |
| Cholesterol Levels | https://medlineplus.gov/lab-tests/cholesterol-levels/ |
| Triglycerides Test | https://medlineplus.gov/lab-tests/triglycerides-test/ |
| Potassium Blood Test | https://medlineplus.gov/lab-tests/potassium-blood-test/ |
| Sodium Blood Test | https://medlineplus.gov/lab-tests/sodium-blood-test/ |
| Electrolyte Panel | https://medlineplus.gov/lab-tests/electrolyte-panel/ |
| Creatinine Test | https://medlineplus.gov/lab-tests/creatinine-test/ |
| Basic Metabolic Panel (BMP) | https://medlineplus.gov/lab-tests/basic-metabolic-panel-bmp/ |
| Comprehensive Metabolic Panel (CMP) | https://medlineplus.gov/lab-tests/comprehensive-metabolic-panel-cmp/ |
| TSH (Thyroid-stimulating hormone) Test | https://medlineplus.gov/lab-tests/tsh-thyroid-stimulating-hormone-test/ |
| Vitamin B Test | https://medlineplus.gov/lab-tests/vitamin-b-test/ |
| C-Reactive Protein (CRP) Test | https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/ |
| Vitamin D Test | https://medlineplus.gov/lab-tests/vitamin-d-test/ |

Each document records the page's "Last updated" date and the date it was retrieved.

## Layout

- `sources/manifest.json`: approved sources.
- `sources/documents/*.md`: cleaned source text with metadata (committed).
- `index/`: generated ChromaDB index (git-ignored). Rebuild from `backend/` with
  `.venv/bin/python -m scripts.ingest_knowledge_base`.

## Adding a source

1. Confirm the reuse terms and add an entry to `manifest.json` (id, url, publisher, license, attribution).
2. Run `.venv/bin/python -m scripts.fetch_sources --only <id>` for MedlinePlus pages, or write
   `documents/<id>.md` by hand in the same format for another approved source.
3. Rebuild the index and run `pytest -m integration` to re-check retrieval quality.

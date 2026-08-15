# Gatsby — health record

A veterinary medical record for Gatsby, a Siberian cat in Zürich, published as a static
website. Built for two audiences: a vet who needs the clinical picture quickly, and his
owners tracking his health over time.

**Live site:** `https://<your-username>.github.io/gatsby-health/`

---

## How it works

```
data/gatsby_data.yaml   ← the single source of truth. Everything comes from here.
sources/                ← redacted PDFs of the original veterinary documents
images/                 ← radiographs, dental films, clinical photographs
site/build.py           ← reads data/, writes docs/
site/static/style.css   ← the stylesheet
docs/                   ← generated. GitHub Pages serves this. Never edit by hand.
```

Push a change to `data/`, `images/` or `sources/` and GitHub Actions rebuilds `docs/` and
redeploys, usually in under a minute.

**Git is the database.** Every change is a commit, so you get version history, timestamps
and rollback for free. There is no backend, no API key, and nothing that can be offline
when a vet opens the page in a waiting room.

---

## Setting it up, once

1. **Create the repository** and push this folder to the `main` branch.
2. **Settings → Pages → Source: GitHub Actions.** Not "Deploy from a branch" — the
   workflow handles it.
3. **Settings → Actions → General → Workflow permissions:** select *Read and write
   permissions*. The observation workflow needs this to commit.
4. Push once. The site appears at the URL above.

The "Open a GitHub issue" button on the Observations page fills itself in automatically
from the repository name — no configuration needed.

---

## Recording an observation

Three ways, in order of how fast they are.

### From your phone — about twenty seconds

Open the GitHub mobile app → **Issues** → **New issue** → **Record an observation**.
Fill in the form and submit.

A workflow parses it, adds it to `data/gatsby_data.yaml`, commits, closes the issue with a
confirmation, and the site rebuilds. Photos dragged into the form are captured too.

If you leave the date blank it uses the moment you submitted.

### From the site

The **Observations** page has the same form. It generates a YAML block and a **Copy**
button. Paste the block under `observations:` in `data/gatsby_data.yaml` — newest at the
top — and commit. Useful if you are already on the site, and a fallback if a workflow ever
fails.

### Directly in the file

For corrections, backdating, or anything the form does not cover, edit
`data/gatsby_data.yaml` on github.com. It works fine from a phone browser.

---

## Adding a veterinary document

1. Redact it.
2. Save it into `sources/` using the **exact filename** shown under that document on the
   Documents page — for example `sources/2025-08-21_wendler_referral.pdf`.
3. Commit and push.

The link appears on its own. Until the file exists, the site shows *Not yet uploaded*
alongside the expected filename, so it is always clear what is outstanding.

If a document is new rather than one already listed, add an entry to `sources:` in the
data file first, following the naming convention `YYYY-MM-DD_provider_description.pdf`.

Filenames are permanent. Once a file is published, renaming it breaks any link that has
been sent to a vet.

---

## Adding a vet visit

Add an entry to `timeline:` in `data/gatsby_data.yaml`:

```yaml
  - date: 2026-08-17
    title: Biopsy — footpads and tongue
    detail: >
      What was found, what was done, what was prescribed.
    provider: Katzen-Praxis Zürich
    problem: [P1, P2]        # one problem, or several
    tag: V                   # V, O, I or Q — see below
    source: S11              # the document ID, if you have the report
    images: [I23, I24]       # image IDs, if any
    milestone: true          # optional — larger dot on the timeline
```

Then update the relevant problem's `status` and `body`, add any new drug to
`medications_past`, any new results to `labs`, and any new files to `sources:` and
`images:`.

### Evidence tags

Every statement carries one. This is the most important convention in the record — it is
what lets a vet tell fact from reasoning at a glance.

| Tag | Meaning |
|---|---|
| `V` | Stated in a veterinary document |
| `O` | Owner observation |
| `I` | Inference or hypothesis — **not a diagnosis** |
| `Q` | Unverified, contradicted, or missing |

In prose fields, write them as `` `[V]` `` and they render as coloured chips. Source
references written as `` `[S2]` `` become links to the document.

---

## Running it locally

```bash
pip install pyyaml markdown
python3 site/build.py
python3 -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`.

---

## Privacy

**Everything published here is publicly readable by URL**, including from a private
repository. GitHub Pages sites are public unless you are on Enterprise.

The data file therefore contains **no home address, phone number, email address or client
number**. Owner names are included deliberately. If you add anything to
`data/gatsby_data.yaml`, keep to that line.

PDFs in `sources/` must be redacted before they go in. The build does not check this and
cannot.

---

## Conventions

**File naming:** `YYYY-MM-DD_provider_description.ext` — sorts chronologically and
self-describes, so the folders stay navigable without the site.

**IDs:** `S1, S2…` for source documents, `I1, I2…` for images, `P1, P2…` for problems.
Once assigned, an ID is never reused for something else.

**Dates:** ISO format `YYYY-MM-DD` in the data file. The site formats them for display.

---

## What the site contains

| Page | Purpose |
|---|---|
| At a glance | Emergency one-pager — signalment, active problems, critical background, next appointment |
| Timeline | Every dated event from every source |
| Observations | Your log between visits, plus the recording form |
| Problems P1–P7 | One dossier per problem, with findings, imaging and current status |
| Medications | Every drug on record, with observed responses |
| Lab results | Values shown against their reference intervals |
| Preventive care | Vaccinations, parasite control, weight chart, recall schedule |
| Anaesthesia | Consolidated record across four general anaesthetics |
| Documents | Every primary source, with direct links |
| Images | Radiographs and clinical photographs |
| Care team | Seven practices in four countries |
| Notes & glossary | Analysis, superseded claims, unknowns, German–English glossary |
| Print full record | Everything on one page, print-optimised |

---

## A note on the record itself

This record was assembled from documents held by seven practices, none of which had seen
the whole picture. Several corrections are baked in — a fracture diagnosis that was later
rejected, a drug dose recorded twenty times too high, a shelter origin that was never
true. Those are kept visible under **Notes & glossary → Superseded**, rather than quietly
deleted, so that if an old claim resurfaces in someone's notes it can be recognised and
dismissed.

Statements tagged `I` are inferences drawn from assembling the record. They are material
for a veterinarian to consider, not conclusions to act on.

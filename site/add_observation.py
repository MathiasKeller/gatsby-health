#!/usr/bin/env python3
"""
Turn a GitHub "Record an observation" issue into an entry in gatsby_data.yaml.

Called by .github/workflows/observation.yml. Reads the issue body from the
ISSUE_BODY environment variable and inserts a new observation at the top of the
list, newest first.

The issue body arrives as GitHub's issue-form markdown:

    ### When did you notice it

    2026-08-20 07:30

    ### Category

    Lameness
    ...
"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gatsby_data.yaml"

FIELDS = {
    "when did you notice it": "when",
    "category": "category",
    "how marked was it": "severity",
    "body part": "body_part",
    "one-line summary": "title",
    "what you saw": "detail",
    "vet contacted": "vet_contacted",
}

IMG_RE = re.compile(r"!\[[^\]]*\]\((https://[^\)]+)\)")


def parse(body):
    out, key, buf = {}, None, []
    for line in body.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^###\s+(.*)$", line.strip())
        if m:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = FIELDS.get(m.group(1).strip().lower()), []
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return {k: v for k, v in out.items()
            if v and v.strip().lower() not in ("_no response_", "none", "n/a")}


def yq(s):
    """Quote a scalar for YAML."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    body = os.environ.get("ISSUE_BODY", "")
    if not body.strip():
        sys.exit("ISSUE_BODY is empty — nothing to add.")

    f = parse(body)
    if not f.get("title"):
        sys.exit("No summary in the issue — nothing to add.")

    # Zurich is UTC+2 in summer, UTC+1 in winter. Close enough for a log entry;
    # the person can correct the value in the file if it matters.
    now = datetime.now(timezone(timedelta(hours=2)))
    when = (f.get("when") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2})?$", when):
        when = now.strftime("%Y-%m-%d %H:%M")
    when = when.replace("T", " ")
    if len(when) == 10:
        when += " 00:00"

    detail = f.get("detail", "").strip()
    photos = IMG_RE.findall(detail)
    detail = IMG_RE.sub("", detail).strip() or "—"

    issue_no = os.environ.get("ISSUE_NUMBER", "")

    lines = [f'  - datetime: {yq(when)}',
             f'    category: {yq(f.get("category", "Other"))}',
             f'    severity: {yq(f.get("severity", "Mild"))}']
    if f.get("body_part"):
        lines.append(f'    body_part: {yq(f["body_part"])}')
    lines.append(f'    title: {yq(f["title"])}')
    lines.append("    detail: >")
    for para in detail.split("\n"):
        lines.append("      " + para.strip() if para.strip() else "")
    lines.append(f'    vet_contacted: {yq(f.get("vet_contacted", "No"))}')
    if photos:
        lines.append("    photos:")
        for p in photos:
            lines.append(f"      - {yq(p)}")
    if issue_no:
        lines.append(f"    issue: {issue_no}")
    lines.append("    tag: O")
    entry = "\n".join(l for l in lines if l is not None)

    text = DATA.read_text(encoding="utf-8")

    if re.search(r"^observations:\s*\[\]\s*$", text, flags=re.M):
        text = re.sub(r"^observations:\s*\[\]\s*$", "observations:\n" + entry,
                      text, count=1, flags=re.M)
    elif re.search(r"^observations:\s*$", text, flags=re.M):
        text = re.sub(r"^observations:\s*$", "observations:\n" + entry,
                      text, count=1, flags=re.M)
    else:
        sys.exit("Could not find the 'observations:' key in gatsby_data.yaml.")

    DATA.write_text(text, encoding="utf-8")
    print(f"Added observation: {f['title']}")

    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as fh:
        fh.write(f"title={f['title']}\n")


if __name__ == "__main__":
    main()

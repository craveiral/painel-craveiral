#!/usr/bin/env python3
"""
Daily driver for the Craveiral dashboard's Pick-up section.

Usage:
    python3 update_pickup.py --history pickup_history.csv --text-file today.txt \
        --html index.html [--html artifact_source.html ...] [--min-rows 300]

What it does, step by step:
1. Reads the raw report text (already extracted -- e.g. by concatenating
   get_page_text results while paging through the PDF in a Drive preview,
   or via `pdftotext -layout` on a real PDF file) from --text-file.
2. Parses it with parse_lib.parse_text() to get the observation date and
   the per-stay-date rows.
3. Validates the parse looks complete (a real "Histórico e Previsão" pull
   has ~300-370 rows; anything much smaller usually means the scrape was
   incomplete -- e.g. a page got skipped while scrolling). Aborts without
   touching any file if the sanity check fails, and prints why.
4. Upserts this observation into the history CSV (idempotent: re-running
   for the same obs_date replaces its rows rather than duplicating them).
5. Regenerates the full "<section id=\"pickup\">...</section>" HTML for the
   current year and substitutes it, in place, into every file passed via
   --html (matching on the literal '  <section id="pickup">' /
   '  </section>' lines, which is how this file has always been
   structured -- see the guardrail below).
6. Prints a one-line JSON summary to stdout so the calling agent can report
   what happened without having to re-derive it.

Guardrail: before writing any --html file, this script counts <section>/
</section> tags before and after the substitution and refuses to write
(aborting only that file, others still proceed) if the count changed --
that would mean the boundary-matching found the wrong lines.
"""
import argparse
import json
import sys

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import parse_lib
import pickup_gen


def substitute_pickup_section(html_text, new_section):
    lines = html_text.split('\n')
    start = None
    end = None
    for i, line in enumerate(lines):
        if line.strip() == '<section id="pickup">':
            start = i
            break
    if start is None:
        return None, "could not find '<section id=\"pickup\">' line"
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == '</section>':
            end = i
            break
    if end is None:
        return None, "found the opening <section id=\"pickup\"> but no matching closing </section>"

    before_open = html_text.count('<section')
    before_close = html_text.count('</section>')

    new_lines = lines[:start] + [new_section] + lines[end + 1:]
    new_html = '\n'.join(new_lines)

    after_open = new_html.count('<section')
    after_close = new_html.count('</section>')
    if after_open != before_open or after_close != before_close:
        return None, (f"tag-balance guardrail tripped (open {before_open}->{after_open}, "
                       f"close {before_close}->{after_close}); refusing to write")
    return new_html, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--history', required=True, help='path to pickup_history.csv (read+write)')
    ap.add_argument('--text-file', required=True, help='path to the raw scraped/extracted report text')
    ap.add_argument('--html', action='append', default=[], help='HTML file(s) to update in place (repeatable)')
    ap.add_argument('--min-rows', type=int, default=300, help='sanity floor for parsed row count')
    ap.add_argument('--dry-run', action='store_true', help="parse and report, but don't write anything")
    args = ap.parse_args()

    with open(args.text_file, encoding='utf-8') as f:
        text = f.read()

    parsed = parse_lib.parse_text(text)
    result = {
        'obs_date': parsed['obs_date'],
        'obs_datetime_raw': parsed['obs_datetime_raw'],
        'n_rows': parsed['n_rows'],
    }

    if parsed['obs_date'] is None:
        result['status'] = 'error'
        result['message'] = 'could not find "Data Impressão" header in the text -- nothing written'
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    if parsed['n_rows'] < args.min_rows:
        result['status'] = 'error'
        result['message'] = (f"only {parsed['n_rows']} rows parsed (expected >= {args.min_rows}) -- "
                              f"looks like an incomplete scrape (a page was probably skipped while "
                              f"scrolling); nothing written")
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    if args.dry_run:
        result['status'] = 'dry_run_ok'
        print(json.dumps(result, ensure_ascii=False))
        return

    hist = pickup_gen.load_history(args.history)
    was_already_present = any(k[0] == parsed['obs_date'] for k in hist)
    pickup_gen.upsert_observation(hist, parsed['obs_date'], parsed['rows'])
    pickup_gen.save_history(hist, args.history)

    section_html = pickup_gen.render_pickup_section(hist)

    html_results = []
    for html_path in args.html:
        with open(html_path, encoding='utf-8') as f:
            html_text = f.read()
        new_html, err = substitute_pickup_section(html_text, section_html)
        if err:
            html_results.append({'file': html_path, 'status': 'error', 'message': err})
            continue
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        html_results.append({'file': html_path, 'status': 'ok'})

    result['status'] = 'updated'
    result['was_already_present'] = was_already_present
    result['total_observations'] = len(pickup_gen.all_obs_dates(hist))
    result['html_files'] = html_results
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

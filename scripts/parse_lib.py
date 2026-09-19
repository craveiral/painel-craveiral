import re, subprocess, sys
from datetime import datetime

MONTHS_PT = {
    'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,
    'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12
}

DATE_RE = re.compile(r'^(\d{2})-(\w{3})-(\d{4})$')

ROW_RE = re.compile(
    r'^(?P<date>\d{2}-[a-zç]{3}-\d{4})\s+(?P<dow>[a-zãáéíóúâêôõà]{3})\s+'
    r'(?P<ocup>-?\d+)\s+'
    r'(?P<cheg>-?\d+)\s+'
    r'(?P<oferta>-?\d+)\s+'
    r'(?P<uso_interno>-?\d+)\s+'
    r'(?P<deduz_ind>-?\d+)\s+'
    r'(?P<deduz_grp>-?\d+)\s+'
    r'(?P<pct_ocup>-?\d+,\d+|-)\s+'
    r'(?P<receita>-?\d{1,3}(?: \d{3})*,\d{2}|-)\s+'
    r'(?P<preco>-?\d{1,3}(?: \d{3})*,\d{2}|-?∞|NaN|-)\s+'
    r'(?P<saidas>-?\d+)\s+'
    r'(?P<quartos_fds>-?\d+)\s+'
    r'(?P<adul_cri>-?\d+)\s*$'
)

IMPRESSAO_RE = re.compile(r'Data Impress[aã]o:\s*\n?\s*(\d{2}-[a-zç]{3}-\d{4}) (\d{2}:\d{2})', re.IGNORECASE)
IMPRESSAO_RE2 = re.compile(r'(\d{2}-[a-zç]{3}-\d{4}) (\d{2}:\d{2})\s*$', re.MULTILINE)


def pt_date_to_iso(d):
    m = DATE_RE.match(d)
    if not m:
        return None
    dd, mon, yyyy = m.groups()
    mon_num = MONTHS_PT.get(mon.lower())
    if not mon_num:
        return None
    return f"{yyyy}-{mon_num:02d}-{int(dd):02d}"


def parse_number(s):
    if s is None or s == '-':
        return None
    if s in ('NaN', '∞', '-∞'):
        return None  # undefined avg price (e.g. zero paid room-nights)
    s = s.replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def extract_text(pdf_path):
    r = subprocess.run(['pdftotext', '-layout', pdf_path, '-'], capture_output=True, text=True)
    return r.stdout


def find_data_impressao(text):
    # Look at the first part of the text for "Data Impressão:" then date+time
    # nearby. Widened window because browser-scraped multi-page text can have
    # extra boilerplate (viewer chrome, filename, etc.) before the real header.
    lines = text.split('\n')
    for i, line in enumerate(lines[:60]):
        if 'Impress' in line:
            for j in range(i, min(i + 3, len(lines))):
                m = re.search(r'(\d{2}-[a-zçãéíóú]{3}-\d{4})\s+(\d{2}:\d{2})', lines[j], re.IGNORECASE)
                if m:
                    return m.group(1), m.group(2)
    # Fallback: some scraped layouts put date+time right after "Impress"
    # on the SAME line with no newline in between.
    m = IMPRESSAO_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return None, None


def parse_text(text):
    """Parse already-extracted report text (from pdftotext, or scraped from
    a browser PDF preview) into the same structure parse_pdf() returns."""
    dt_str, tm_str = find_data_impressao(text)
    obs_date_iso = pt_date_to_iso(dt_str) if dt_str else None

    rows = []
    for line in text.split('\n'):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        m = ROW_RE.match(line_stripped)
        if m:
            gd = m.groupdict()
            stay_date_iso = pt_date_to_iso(gd['date'])
            if stay_date_iso is None:
                continue
            rows.append({
                'stay_date': stay_date_iso,
                'ocup': parse_number(gd['ocup']),
                'cheg': parse_number(gd['cheg']),
                'oferta': parse_number(gd['oferta']),
                'uso_interno': parse_number(gd['uso_interno']),
                'deduz_individ': parse_number(gd['deduz_ind']),
                'deduz_grupos': parse_number(gd['deduz_grp']),
                'pct_ocup': parse_number(gd['pct_ocup']),
                'receita_quartos': parse_number(gd['receita']),
                'preco_medio': parse_number(gd['preco']),
                'saidas': parse_number(gd['saidas']),
                'quartos_fds': parse_number(gd['quartos_fds']),
                'adul_cri': parse_number(gd['adul_cri']),
            })
    return {
        'obs_date': obs_date_iso,
        'obs_datetime_raw': f"{dt_str} {tm_str}" if dt_str else None,
        'n_rows': len(rows),
        'rows': rows,
    }


def parse_pdf(pdf_path):
    text = extract_text(pdf_path)
    return parse_text(text)


if __name__ == '__main__':
    result = parse_pdf(sys.argv[1])
    print('obs_date:', result['obs_date'], result['obs_datetime_raw'])
    print('n_rows:', result['n_rows'])
    for r in result['rows'][:5]:
        print(r)

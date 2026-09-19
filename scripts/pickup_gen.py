"""
Shared logic to turn the pickup_history.csv dataset into the HTML for the
dashboard's "Pick-up" section. Used both interactively and by the daily
update script (update_pickup.py).

The dataset is a long-format CSV: obs_date,stay_date,ocup,pct_ocup,receita_quartos
- obs_date: the date the PMS report was printed / observed (ISO yyyy-mm-dd)
- stay_date: the calendar date the row's numbers describe (ISO yyyy-mm-dd)
- ocup: room nights on the books for stay_date, as of obs_date
- pct_ocup: occupancy % for stay_date, as of obs_date
- receita_quartos: room revenue (EUR) for stay_date, as of obs_date

The Pick-up section always focuses on "the current year" (derived from the
most recent obs_date in the dataset), comparing:
- Ontem vs Hoje: the two most recent available obs_dates (not necessarily
  calendar-adjacent -- some days have no PMS snapshot).
- vs. prior year (closed): for each day in the target year, the "actual"
  value from the prior year, taken from the first obs_date on/after that
  prior-year date (so it reflects the settled, no-longer-changing actual).
"""
import csv
import gzip
from datetime import date, timedelta


def _open_text(path, mode):
    """Transparent gzip support: pickup_history.csv.gz is read/written
    compressed (keeps the file well under the 10MB browser-upload cap used
    to push it to GitHub); a plain .csv path is read/written as-is."""
    if path.endswith('.gz'):
        return gzip.open(path, mode + 't', encoding='utf-8', newline='' if 'w' in mode else None)
    return open(path, mode, newline='' if 'w' in mode else None, encoding='utf-8')

MONTH_NAMES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho',
               'Agosto','Setembro','Outubro','Novembro','Dezembro']
DOW_PT = ['seg','ter','qua','qui','sex','sáb','dom']


def load_history(path):
    """Returns dict[(obs_date, stay_date)] -> {ocup, pct_ocup, receita_quartos}"""
    hist = {}
    with _open_text(path, 'r') as f:
        r = csv.DictReader(f)
        for row in r:
            hist[(row['obs_date'], row['stay_date'])] = {
                'ocup': float(row['ocup']) if row['ocup'] not in ('', 'None') else None,
                'pct_ocup': float(row['pct_ocup']) if row['pct_ocup'] not in ('', 'None') else None,
                'receita_quartos': float(row['receita_quartos']) if row['receita_quartos'] not in ('', 'None') else None,
            }
    return hist


def save_history(hist, path):
    with _open_text(path, 'w') as f:
        w = csv.writer(f)
        w.writerow(['obs_date', 'stay_date', 'ocup', 'pct_ocup', 'receita_quartos'])
        for (obs_date, stay_date) in sorted(hist.keys()):
            v = hist[(obs_date, stay_date)]
            w.writerow([obs_date, stay_date, v['ocup'], v['pct_ocup'], v['receita_quartos']])


def upsert_observation(hist, obs_date, rows):
    """rows: list of dicts with stay_date, ocup, pct_ocup, receita_quartos.
    Replaces any existing rows for this obs_date (idempotent re-runs)."""
    for k in [k for k in hist if k[0] == obs_date]:
        del hist[k]
    for r in rows:
        hist[(obs_date, r['stay_date'])] = {
            'ocup': r['ocup'], 'pct_ocup': r['pct_ocup'], 'receita_quartos': r['receita_quartos'],
        }


def all_obs_dates(hist):
    return sorted({k[0] for k in hist.keys()})


def two_most_recent_obs_dates(hist):
    dates = all_obs_dates(hist)
    if len(dates) < 2:
        raise ValueError(f"Need at least 2 observation dates, have {len(dates)}")
    return dates[-1], dates[-2]  # (hoje, ontem)


def get_row(hist, obs_date, stay_date):
    return hist.get((obs_date, stay_date))


def get_prior_year_actual(hist, stay_date_prior_year):
    """First obs_date on/after stay_date_prior_year that has a row for it
    (the earliest snapshot taken after the date happened == settled actual)."""
    candidates = sorted(k[0] for k in hist.keys() if k[1] == stay_date_prior_year and k[0] >= stay_date_prior_year)
    if not candidates:
        return None
    return hist[(candidates[0], stay_date_prior_year)]


# ---------- number formatting (pt-PT locale) ----------

def fmt_int(n):
    n = round(n or 0)
    return f"{n:,.0f}".replace(",", ".")

def fmt_signed_int(n):
    n = round(n or 0)
    s = fmt_int(abs(n))
    return f"+{s}" if n > 0 else (f"-{s}" if n < 0 else "0")

def fmt_eur(n):
    return f"{fmt_int(n)}€"

def fmt_signed_eur(n):
    n = round(n or 0)
    s = fmt_int(abs(n))
    return f"+{s}€" if n > 0 else (f"-{s}€" if n < 0 else "0€")

def fmt_adr(n):
    n = n or 0
    s = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}€"

def fmt_pct1(n):
    return f"{(n or 0):.1f}".replace(".", ",") + "%"

def fmt_pct0(n):
    return f"{round(n or 0)}%"


def compute_year_data(hist, year, obs_hoje, obs_ontem):
    """Builds the full per-day / per-month structure for `year`, comparing
    obs_hoje vs obs_ontem, with (year-1) actuals as the reference column."""
    d0 = date(year, 1, 1)
    d1 = date(year, 12, 31)
    all_days = []
    d = d0
    while d <= d1:
        all_days.append(d.isoformat())
        d += timedelta(days=1)

    months = {m: {'days': [], 'rn_ontem': 0.0, 'rn_hoje': 0.0, 'receita_hoje': 0.0,
                  'rn_prior': 0.0, 'receita_prior': 0.0} for m in range(1, 13)}

    totals = {'rn_hoje': 0.0, 'rn_ontem': 0.0, 'receita_hoje': 0.0, 'receita_ontem': 0.0,
              'rn_prior': 0.0, 'receita_prior': 0.0}

    for d_str in all_days:
        y, m, dd = [int(x) for x in d_str.split('-')]
        hr = get_row(hist, obs_hoje, d_str)
        orow = get_row(hist, obs_ontem, d_str)
        try:
            prior_date = date(year - 1, m, dd).isoformat()
        except ValueError:
            prior_date = date(year - 1, 2, 28).isoformat()  # Feb 29 fallback
        pr = get_prior_year_actual(hist, prior_date)

        rn_hoje = (hr or {}).get('ocup') or 0.0
        pct_hoje = (hr or {}).get('pct_ocup') or 0.0
        rec_hoje = (hr or {}).get('receita_quartos') or 0.0
        rn_ontem = (orow or {}).get('ocup') or 0.0
        pct_ontem = (orow or {}).get('pct_ocup') or 0.0
        rec_ontem = (orow or {}).get('receita_quartos') or 0.0
        rn_prior = (pr or {}).get('ocup') or 0.0
        rec_prior = (pr or {}).get('receita_quartos') or 0.0

        dow = DOW_PT[date(y, m, dd).weekday()]
        months[m]['days'].append({
            'date': d_str, 'dow': dow,
            'rn_ontem': rn_ontem, 'pct_ontem': pct_ontem, 'rec_ontem': rec_ontem,
            'rn_hoje': rn_hoje, 'pct_hoje': pct_hoje, 'rec_hoje': rec_hoje,
            'pickup_rn': rn_hoje - rn_ontem, 'pickup_rec': rec_hoje - rec_ontem,
        })
        months[m]['rn_ontem'] += rn_ontem
        months[m]['rn_hoje'] += rn_hoje
        months[m]['receita_hoje'] += rec_hoje
        months[m]['rn_prior'] += rn_prior
        months[m]['receita_prior'] += rec_prior

        totals['rn_hoje'] += rn_hoje
        totals['rn_ontem'] += rn_ontem
        totals['receita_hoje'] += rec_hoje
        totals['receita_ontem'] += rec_ontem
        totals['rn_prior'] += rn_prior
        totals['receita_prior'] += rec_prior

    return months, totals, all_days


def render_pickup_section(hist, year=None, obs_hoje=None, obs_ontem=None):
    """Returns the full '<section id="pickup">...</section>' HTML string."""
    if obs_hoje is None or obs_ontem is None:
        obs_hoje, obs_ontem = two_most_recent_obs_dates(hist)
    if year is None:
        year = int(obs_hoje[:4])
    prior_year = year - 1

    months, totals, _all_days = compute_year_data(hist, year, obs_hoje, obs_ontem)

    adr_ano = totals['receita_hoje'] / totals['rn_hoje'] if totals['rn_hoje'] else 0
    adr_prior = totals['receita_prior'] / totals['rn_prior'] if totals['rn_prior'] else 0
    pickup_rn_total = totals['rn_hoje'] - totals['rn_ontem']
    pickup_rec_total = totals['receita_hoje'] - totals['receita_ontem']
    delta_rn_prior = totals['rn_hoje'] - totals['rn_prior']
    delta_rec_prior = totals['receita_hoje'] - totals['receita_prior']

    def dmy(iso):
        y, m, d = iso.split('-')
        return f"{d}/{m}/{y}"

    kpi_html = f"""    <div class="kpi-grid">
      <div class="kpi-tile">
        <span class="kpi-label">Room Nights no ano ({year})</span>
        <span class="kpi-value mono">{fmt_int(totals['rn_hoje'])}</span>
        <span class="kpi-note">{prior_year} (fechado): {fmt_int(totals['rn_prior'])} · Δ {fmt_signed_int(delta_rn_prior)}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Receita no ano ({year})</span>
        <span class="kpi-value mono">{fmt_eur(totals['receita_hoje'])}</span>
        <span class="kpi-note">{prior_year} (fechado): {fmt_eur(totals['receita_prior'])} · Δ {fmt_signed_eur(delta_rec_prior)}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">ADR médio no ano</span>
        <span class="kpi-value mono">{fmt_adr(adr_ano)}</span>
        <span class="kpi-note">{prior_year} (fechado): {fmt_adr(adr_prior)}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Pick-up desde ontem</span>
        <span class="kpi-value mono">{fmt_signed_int(pickup_rn_total)} <span style="font-size:0.95rem;font-weight:500;">RN</span></span>
        <span class="kpi-note">{fmt_signed_eur(pickup_rec_total)} de receita {'adicionada' if pickup_rec_total >= 0 else 'retirada'}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Vs. mesmo período do ano passado ({prior_year}, fechado)</span>
        <span class="kpi-value mono">{fmt_signed_int(delta_rn_prior)} <span style="font-size:0.95rem;font-weight:500;">RN</span></span>
        <span class="kpi-note">{fmt_signed_eur(delta_rec_prior)} de receita</span>
      </div>
    </div>"""

    rows_html = []
    for m in range(1, 13):
        md = months[m]
        rn_ontem = md['rn_ontem']; rn_hoje = md['rn_hoje']; receita_hoje = md['receita_hoje']
        rn_prior = md['rn_prior']; receita_prior = md['receita_prior']
        pickup_rn = rn_hoje - rn_ontem
        adr_hoje = receita_hoje / rn_hoje if rn_hoje else 0
        days = md['days']
        avg_pct_hoje = sum(dday['pct_hoje'] for dday in days) / len(days) if days else 0
        delta_rn = rn_hoje - rn_prior
        delta_rec = receita_hoje - receita_prior
        rows_html.append(
            f'<tr><td>{MONTH_NAMES[m - 1]}</td>\n'
            f'<td class="mono">{fmt_int(rn_ontem)}</td>\n'
            f'<td class="mono">{fmt_int(rn_hoje)}</td>\n'
            f'<td class="mono">{fmt_signed_int(pickup_rn)}</td>\n'
            f'<td class="mono">{fmt_pct1(avg_pct_hoje)}</td>\n'
            f'<td class="mono">{fmt_eur(receita_hoje)}</td>\n'
            f'<td class="mono">{fmt_adr(adr_hoje)}</td>\n'
            f'<td class="mono">{fmt_int(rn_prior)}</td>\n'
            f'<td class="mono">{fmt_eur(receita_prior)}</td>\n'
            f'<td class="mono">{fmt_signed_int(delta_rn)}</td>\n'
            f'<td class="mono">{fmt_signed_eur(delta_rec)}</td></tr>'
        )
    monthly_table_html = f"""    <h3 style="font-size:1rem;">Pick-up mensal — {year} vs. {prior_year} (fechado)</h3>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Mês</th><th>RN Ontem</th><th>RN Hoje</th><th>Pick-up (RN)</th><th>Ocup. Hoje</th><th>Receita Hoje</th><th>ADR Hoje</th><th>RN {prior_year}</th><th>Receita {prior_year}</th><th>Δ RN vs {prior_year}</th><th>Δ Receita vs {prior_year}</th></tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>"""

    blocks = []
    for m in range(1, 13):
        days = months[m]['days']
        n_days = len(days)
        row_htmls = []
        for dday in days:
            dd_mm = dday['date'][8:10] + "/" + dday['date'][5:7]
            row_htmls.append(
                f'<tr><td class="mono">{dd_mm}</td><td>{dday["dow"]}</td>\n'
                f'<td class="mono">{fmt_int(dday["rn_ontem"])}</td><td class="mono">{fmt_pct0(dday["pct_ontem"])}</td><td class="mono">{fmt_eur(dday["rec_ontem"])}</td>\n'
                f'<td class="mono">{fmt_int(dday["rn_hoje"])}</td><td class="mono">{fmt_pct0(dday["pct_hoje"])}</td><td class="mono">{fmt_eur(dday["rec_hoje"])}</td>\n'
                f'<td class="mono">{fmt_signed_int(dday["pickup_rn"])}</td><td class="mono">{fmt_signed_eur(dday["pickup_rec"])}</td></tr>'
            )
        blocks.append(f"""        <details class="table-toggle pickup-month">
          <summary>{MONTH_NAMES[m - 1]} — ver detalhe diário ({n_days} dias)</summary>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr><th>Data</th><th>Dia</th><th>RN Ontem</th><th>Ocup. Ontem</th><th>Receita Ontem</th><th>RN Hoje</th><th>Ocup. Hoje</th><th>Receita Hoje</th><th>Pick-up RN</th><th>Pick-up Receita</th></tr>
              </thead>
              <tbody>
                {''.join(row_htmls)}
              </tbody>
            </table>
          </div>
        </details>""")
    day_detail_html = "\n".join(blocks)

    full = f"""  <section id="pickup">
    <div class="section-head">
      <div>
        <h2>Pick-up — Craveiral {year}</h2>
        <p class="sub">Ritmo de reservas do ano corrente: comparação real entre a leitura de ontem e a de hoje, por mês, com o fecho de {prior_year} como referência. Dados extraídos diariamente do relatório do PMS "150. Histórico e Previsão", com histórico completo dia a dia desde Outubro de 2024.</p>
      </div>
    </div>

{kpi_html}

{monthly_table_html}

    <h3 style="font-size:1rem;">Detalhe diário por mês</h3>
    <p class="sub" style="margin:0 0 4px;">Cada mês tem a leitura dia a dia (ontem, hoje e pick-up). Clique para abrir.</p>

{day_detail_html}

    <p class="footnote">Fonte: relatório "150. Histórico e Previsão" do PMS do Craveiral, recolhido diariamente do Google Drive da propriedade (pasta "RELATÓRIOS DIÁRIOS"). Histórico completo dia a dia desde Outubro de 2024 ({len(all_obs_dates(hist))} leituras). Ontem = leitura de {dmy(obs_ontem)}, Hoje = leitura de {dmy(obs_hoje)}. Esta secção é atualizada automaticamente todos os dias.</p>
  </section>"""

    return full

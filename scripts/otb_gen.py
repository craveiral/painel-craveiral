"""
Turns a monthly OTB (On The Books) revenue-mix snapshot into the HTML for
the dashboard's "Receita Total & Mix" section. Used both interactively and
by the daily update automation.

Source: the "OTB" Google Drive folder (OTB e RELATÓRIOS DIÁRIOS/OTB/OTB's
<ano>), one .xlsx per snapshot (filename OTB_Craveiral_<ano>-DD.MM.YYYY.xlsx,
added roughly twice a week, Mon/Thu). Each file's most recent sheet tab has
a "ON THE BOOKS <data> vs SAME DATE LAST YEAR" block with, per month:
Taxa de Ocupação, Noites Vendidas, Receita Total, Receita Quartos, Receita
F&B, Receita Outros, Receita SPA (2026 and 2025 columns each). Room
nights/occupancy duplicate the Pick-up section (same PMS source) -- the
genuinely new data this section adds is the revenue breakdown by stream.

Input to render_otb_section(): a dict {month_num (1-12): {'quartos':
float, 'fb': float, 'outros': float, 'spa': float}} for the current year,
plus the snapshot date string (as printed in the sheet, e.g. "24.09.2026")
and the year (int). Only months with actual data need be present (e.g. a
snapshot taken mid-year won't yet have full trailing months -- pass what
the sheet shows; months beyond the snapshot are still OTB/pace figures the
sheet itself provides, so normally all 12 are present).
"""
import json

MONTH_NAMES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho',
               'Agosto','Setembro','Outubro','Novembro','Dezembro']


def fmt_eur(n):
    n = round(n or 0)
    return f"{n:,.0f}".replace(",", ".") + "€"


def fmt_pct1(n):
    return f"{(n or 0):.1f}".replace(".", ",") + "%"


def render_otb_section(monthly, snapshot_date, year):
    """monthly: {month_num: {'quartos','fb','outros','spa'}}. Returns the
    full '<section id="otb">...</section>' HTML string."""
    rows_html = []
    cats, qs, fbs, others, totals = [], [], [], [], []
    tot_quartos = tot_fb = tot_outros = tot_spa = 0.0
    for m in range(1, 13):
        d = monthly.get(m, {'quartos': 0.0, 'fb': 0.0, 'outros': 0.0, 'spa': 0.0})
        quartos = d.get('quartos') or 0.0
        fb = d.get('fb') or 0.0
        outros = (d.get('outros') or 0.0) + (d.get('spa') or 0.0)  # SPA folded into Outros (currently always 0)
        total = quartos + fb + outros
        extra_pct = ((fb + outros) / total * 100) if total else 0.0
        tot_quartos += quartos; tot_fb += fb; tot_outros += outros

        cats.append(MONTH_NAMES[m - 1][:3])
        qs.append(round(quartos)); fbs.append(round(fb)); others.append(round(outros))
        totals.append(round(total))

        rows_html.append(
            f'<tr><td>{MONTH_NAMES[m - 1]}</td>'
            f'<td class="mono">{fmt_eur(quartos)}</td>'
            f'<td class="mono">{fmt_eur(fb)}</td>'
            f'<td class="mono">{fmt_eur(outros)}</td>'
            f'<td class="mono">{fmt_eur(total)}</td>'
            f'<td class="mono">{fmt_pct1(extra_pct)}</td></tr>'
        )

    tot_total = tot_quartos + tot_fb + tot_outros
    extra_total = tot_fb + tot_outros
    extra_pct_total = (extra_total / tot_total * 100) if tot_total else 0.0

    kpi_html = f"""    <div class="kpi-grid">
      <div class="kpi-tile">
        <span class="kpi-label">Receita total do ano ({year})</span>
        <span class="kpi-value mono">{fmt_eur(tot_total)}</span>
        <span class="kpi-note">Quartos + F&amp;B + Outros, a partir do OTB de {snapshot_date}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Receita extra (não-quartos)</span>
        <span class="kpi-value mono">{fmt_eur(extra_total)}</span>
        <span class="kpi-note">{fmt_pct1(extra_pct_total)} da receita total do ano</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Receita F&amp;B no ano</span>
        <span class="kpi-value mono">{fmt_eur(tot_fb)}</span>
        <span class="kpi-note">Restaurante e bar, acumulado {year}</span>
      </div>
      <div class="kpi-tile">
        <span class="kpi-label">Receita Outros/SPA no ano</span>
        <span class="kpi-value mono">{fmt_eur(tot_outros)}</span>
        <span class="kpi-note">SPA ainda sem receita registada nesta fonte</span>
      </div>
    </div>"""

    chart_payload = {
        'categories': cats,
        'series': [
            {'slot': 1, 'label': 'Quartos', 'values': qs},
            {'slot': 2, 'label': 'F&B', 'values': fbs},
            {'slot': 3, 'label': 'Outros + SPA', 'values': others},
        ],
    }
    chart_html = f"""    <div class="chart-card">
      <h3>Receita por origem — {year}</h3>
      <p class="chart-sub">Quartos, F&amp;B e Outros/SPA, mês a mês (fonte: OTB de {snapshot_date}).</p>
      <div class="legend-row">
        <span class="legend-item"><span class="legend-swatch swatch-1"></span>Quartos</span>
        <span class="legend-item"><span class="legend-swatch swatch-2"></span>F&amp;B</span>
        <span class="legend-item"><span class="legend-swatch swatch-3"></span>Outros + SPA</span>
      </div>
      <div id="otb-chart"></div>
    </div>
    <script>
    (function(){{
      var data = {json.dumps(chart_payload, ensure_ascii=False)};
      function fmt(v){{ return Math.round(v).toLocaleString('pt-PT') + '€'; }}
      window.CraveiralCharts.lineChart(document.getElementById('otb-chart'), {{
        categories: data.categories,
        series: data.series,
        formatValue: fmt,
        ariaLabel: 'Receita por origem (Quartos, F&B, Outros e SPA) do Craveiral em {year}, por mês'
      }});
    }})();
    </script>"""

    table_html = f"""    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Mês</th><th>Receita Quartos</th><th>Receita F&amp;B</th><th>Receita Outros + SPA</th><th>Receita Total</th><th>% Receita Extra</th></tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>"""

    full = f"""  <section id="otb">
    <div class="section-head">
      <div>
        <h2>Receita Total &amp; Mix — OTB</h2>
        <p class="sub">Receita do hotel por origem (quartos, F&amp;B, outros e SPA), a partir do relatório "On The Books" interno, atualizado cerca de duas vezes por semana (segunda e quinta). Complementa o Pick-up (que só cobre quartos) com a receita não-quartos.</p>
      </div>
    </div>

{kpi_html}

{chart_html}

{table_html}

    <p class="footnote">Fonte: workbook "OTB_Craveiral" na pasta do Google Drive "OTB e RELATÓRIOS DIÁRIOS / OTB", ficheiro mais recente ({snapshot_date}), tabela "ON THE BOOKS vs SAME DATE LAST YEAR". Room nights e ocupação já constam da secção Pick-up (mesma fonte PMS) — esta secção foca-se na receita por departamento. Atualizado sempre que surge um ficheiro novo na pasta (tipicamente 2x por semana), não diariamente.</p>
  </section>"""

    return full


if __name__ == '__main__':
    # quick manual smoke test with the 24.09.2026 snapshot's real figures
    monthly = {
        1: {'quartos': 34737, 'fb': 14062.89, 'outros': 195.53, 'spa': 0},
        2: {'quartos': 36531, 'fb': 18736.03, 'outros': 123.90, 'spa': 0},
        3: {'quartos': 58853, 'fb': 25949.10, 'outros': 882.02, 'spa': 0},
        4: {'quartos': 138549, 'fb': 51579.83, 'outros': 148.34, 'spa': 0},
        5: {'quartos': 113288, 'fb': 63624.39, 'outros': 365.82, 'spa': 0},
        6: {'quartos': 166893, 'fb': 57127.41, 'outros': 1781.89, 'spa': 0},
        7: {'quartos': 294733, 'fb': 81677.72, 'outros': 812.08, 'spa': 0},
        8: {'quartos': 430294, 'fb': 114946.37, 'outros': 655.71, 'spa': 0},
        9: {'quartos': 195374, 'fb': 42078.72, 'outros': 98.96, 'spa': 0},
        10: {'quartos': 115460, 'fb': 4528.27, 'outros': 0, 'spa': 0},
        11: {'quartos': 17173, 'fb': 1037.73, 'outros': 0, 'spa': 0},
        12: {'quartos': 11974, 'fb': 419.81, 'outros': 0, 'spa': 0},
    }
    html = render_otb_section(monthly, '24.09.2026', 2026)
    print(len(html))
    open('/tmp/otb_section_test.html', 'w', encoding='utf-8').write(html)

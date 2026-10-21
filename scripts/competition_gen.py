"""
Turns the `competitionset` collection's documents into the HTML for the
dashboard's "Competition set" section (both the private artifact's static
public mirror and, in principle, any other place that needs this exact
rendering).

Source (since 21/10/2026): each hotel's own official website PLUS a
Booking.com search, 1 night / 2 pax, same reference date for every
property in a run (previously: Climber RMS + Lighthouse rate shopping —
discontinued per instruction 21/10/2026). Collected manually (there is no
API), one value per source per property, then written to `ArtifactData`.

Input to render_competition_section(): a list of dicts, each
{'nome': str, 'adr_site': float|None, 'adr_booking': float|None,
'notas': str}, in the order they should appear in the table (the live
dashboard's own form adds rows in entry order; for the public mirror just
keep the same order as the `competitionset` collection, e.g. alphabetical
by doc_id). `adr_site`/`adr_booking` are None when no rate was found for
that source (sold out, no flexible/refundable rate on Booking, minimum-
stay restriction with no matching 1-night window, no public rate on the
official site, etc.) -- `notas` should explain which, in Portuguese, using
one of the keyword phrases below so the hover tooltip and the live
dashboard's own `competitionGapReason()` stay consistent:

  - "Esgotado" anywhere in `notas`              -> sold out / no availability
  - "Sem tarifa flexível" / "sem tarifa flexivel" -> no non-refundable rate
  - anything else (e.g. "não publica tarifário",
    "não encontrado", a minimum-stay note)        -> generic "not published"

The distinction above only changes the *tooltip wording* shown over an
empty Booking.com cell (see BOOKING_ESGOTADO_TITLE / BOOKING_SEMFLEX_TITLE
below) -- an empty "Site oficial" cell always gets the same generic
tooltip (SITE_EMPTY_TITLE), since official-site failures aren't usefully
split into sub-reasons the way Booking.com ones are.
"""
import json

SITE_EMPTY_TITLE = "Tarifa não publicada (ou não encontrada) no site oficial."
BOOKING_ESGOTADO_TITLE = "Sem tarifa: alojamento esgotado no dia consultado (ver Notas)."
BOOKING_SEMFLEX_TITLE = "Sem tarifa flexível disponível no dia consultado (ver Notas)."


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cell(value, empty_title):
    if value is None:
        return f'<td class="mono"><span class="empty-note" title="{empty_title}">—<sup>*</sup></span></td>'
    return f'<td class="mono">{round(value)}€</td>'


def render_competition_section(rows):
    """rows: list of {'nome', 'adr_site', 'adr_booking', 'notas'}.
    Returns the full '<section id="competition">...</section>' HTML string."""
    row_html = []
    chart_items = []
    for r in rows:
        nome = r["nome"]
        site = r.get("adr_site")
        booking = r.get("adr_booking")
        notas = r.get("notas") or ""

        site_td = _cell(site, SITE_EMPTY_TITLE)
        if booking is None:
            booking_title = (
                BOOKING_ESGOTADO_TITLE if "esgotado" in notas.lower() else BOOKING_SEMFLEX_TITLE
            )
            booking_td = _cell(None, booking_title)
        else:
            booking_td = _cell(booking, "")

        row_html.append(
            f'<tr><td>{_esc(nome)}</td>{site_td}{booking_td}<td>{_esc(notas)}</td></tr>'
        )

        prices = [v for v in (site, booking) if v is not None]
        if prices:
            chart_items.append({"label": nome, "value": min(prices)})

    chart_items.sort(key=lambda x: -x["value"])
    table_html = "\n".join(row_html)
    chart_js = json.dumps(chart_items, ensure_ascii=False)

    section = f"""  <section id="competition">
    <div class="section-head">
      <div>
        <h2>Competition set</h2>
        <p class="sub">Alojamentos comparáveis na região. Tarifas mais recentes (ver data em cada nota), 1 noite / 2 pax, recolhidas diretamente no site oficial e no Booking.com de cada alojamento.</p>
      </div>
    </div>

    <div class="chart-card">
      <h3>ADR por alojamento</h3>
      <p class="chart-sub">Menor tarifa publicada por alojamento (site oficial ou Booking.com, a que for mais barata); alojamentos sem nenhuma tarifa disponível não aparecem no gráfico.</p>
      <div id="competition-chart"></div>
    </div>
    <script>
    (function(){{
      window.CraveiralCharts.barChart(document.getElementById('competition-chart'), {{
        items: {chart_js},
        formatValue: function(v){{ return Math.round(v).toLocaleString('pt-PT') + '€'; }},
        ariaLabel: 'ADR por alojamento do competition set (menor tarifa entre site oficial e Booking.com)',
        labelWidth: 210
      }});
    }})();
    </script>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr><th>Alojamento</th><th>Site oficial (€)</th><th>Booking.com (€)</th><th>Notas</th></tr>
        </thead>
        <tbody>
{table_html}
        </tbody>
      </table>
      <p class="footnote table-legend">* Passe o cursor sobre o valor para ver o motivo. Tarifas de 1 noite, 2 adultos, recolhidas diretamente no site oficial e no Booking.com de cada alojamento para a mesma data de referência (ver Notas em cada linha); quando o site oficial publica apenas um tarifário indicativo ("desde X€"), isso fica assinalado na nota.</p>
    </div>
  </section>"""

    return section


if __name__ == '__main__':
    # quick manual smoke test with the 21/10/2026 run's real figures
    rows = [
        {"nome": "Areias do Seixo Villas", "adr_site": None, "adr_booking": None,
         "notas": "195 km · Esgotado no Booking.com (não aceita reservas no momento, verificado 07-08/11/2026, 1 noite/2 pax); tarifa de site oficial não disponível"},
        {"nome": "Herdade do Amarelo Nature & Spa", "adr_site": 150, "adr_booking": None,
         "notas": "25 km · Esgotado no Booking.com (07-08/11/2026, 1 noite/2 pax); site oficial: desde 150€/noite"},
        {"nome": "Herdade Do Touril", "adr_site": 140, "adr_booking": 132,
         "notas": "13 km · Estadia mínima de 2 noites para 07-08/11/2026; tarifa de 1 noite mais próxima (06-07 ou 08-09/11/2026, 2 pax): 132€."},
    ]
    html = render_competition_section(rows)
    print(len(html))
    open('/tmp/competition_section_test.html', 'w', encoding='utf-8').write(html)

# Pipeline do Pick-up — Craveiral

Estes scripts mantêm a secção "Pick-up" do painel (privado e público) ligada
a dados reais do PMS, recolhidos diariamente do relatório "150. Histórico e
Previsão" na pasta do Google Drive "RELATÓRIOS DIÁRIOS"
(`https://drive.google.com/drive/u/0/folders/1wzeoJxU4C6H1hK6qWMb5P0hvgz3X-GNJ`).

## Ficheiros

- `parse_lib.py` — extrai as linhas da tabela (uma por dia do ano) e a data
  de observação ("Data Impressão") a partir do texto do relatório. Funciona
  tanto sobre um PDF real (`parse_pdf`, via `pdftotext -layout`) como sobre
  texto já extraído de outra fonte, por exemplo copiado de um preview de
  PDF no browser (`parse_text`).
- `pickup_gen.py` — mantém o histórico consolidado (`../data/pickup_history.csv.gz`,
  formato longo: `obs_date,stay_date,ocup,pct_ocup,receita_quartos`) e sabe
  gerar o HTML completo da secção `<section id="pickup">...</section>` a
  partir dele, para o ano corrente (derivado da data de observação mais
  recente), comparando a leitura de ontem com a de hoje e com o fecho do
  ano anterior.
- `update_pickup.py` — o script que a tarefa diária corre. Ver `--help`.

## Gráficos interativos (CraveiralCharts)

Desde 19/09/2026 as três secções dinâmicas (Pick-up, Evolução comercial,
Competition set) têm gráficos interativos (linha com tooltip/crosshair para
séries temporais, barras com tooltip para o competition set), em vez de só
tabelas. **Não são um serviço externo** — é uma pequena biblioteca JS/CSS
própria, sem dependências, já embebida no `<head>` de ambos os ficheiros
(`index.html` e o HTML do painel privado): a `<style>` principal ganhou um
bloco de classes (`.line-series-N`, `.dot-series-N`, `.chart-tooltip*`,
`.metric-toggle`, etc.) e logo a seguir ao `</style>` há um `<script>` que
define `window.CraveiralCharts` com duas funções, `lineChart(container,
opts)` e `barChart(container, opts)`. **Este bloco no `<head>` é estável —
não precisa de ser regenerado nem tocado nas execuções diárias.** Se algum
dia precisar de ser atualizado, a versão de referência vive em
`/home/claude/chart_lib/craveiral-charts.{css,js}` na sessão em que foi
criada (19/09/2026); caso essa sessão já não exista, o próprio `<head>` do
`index.html` já publicado é a fonte de verdade.

- **Pick-up**: totalmente automático — `pickup_gen.render_pickup_section()`
  já gera, dentro da própria secção, um `<div class="chart-card">` com um
  `metric-toggle` (Room Nights / Receita / Ocupação) e o `<script>` que
  chama `CraveiralCharts.lineChart(...)` com os dados do ano corrente vs.
  o ano anterior fechado. Correr `update_pickup.py` como sempre já trata
  disto; não há nenhum passo extra.
- **Evolução comercial** e **Competition set** no painel **privado**
  (artifact): também automático — o `<script>` no fim do HTML do painel já
  lê a base de dados (`window.claude.use('db')`) e chama
  `CraveiralCharts.lineChart`/`barChart` sozinho quando os dados mudam
  (ver `renderComercialChart` e o bloco de gráfico dentro de
  `renderCompetition` nesse ficheiro). Não requer nenhuma ação da tarefa
  diária além do PASSO 1 já descrito (ler/substituir a secção pickup e
  publicar de novo com a ferramenta Artifact).
- **Evolução comercial** e **Competition set** na **página pública**
  (`index.html`, site estático, sem base de dados ao vivo): aqui os
  gráficos têm de ser recriados como uma "fotografia" a cada execução, tal
  como as tabelas já eram. Ao regenerar estas duas secções no PASSO 2
  (a partir das coleções `comercial` e `competitionset` lidas via
  ArtifactData), insira, imediatamente antes do `<div class="table-wrap">`
  de cada secção, um bloco assim (adapte os valores; o resto do padrão é
  fixo):

  ```html
  <div class="chart-card">
    <h3>Evolução mensal</h3>
    <p class="chart-sub">A partir do Climber RMS. Use os botões para trocar a métrica.</p>
    <div class="metric-toggle" role="group" aria-label="Escolher métrica do gráfico de evolução comercial" data-toggle-for="comercial-chart">
      <button type="button" data-metric="receita" aria-pressed="true">Receita</button>
      <button type="button" data-metric="reservas" aria-pressed="false">Room Nights</button>
      <button type="button" data-metric="ocupacaoPct" aria-pressed="false">Ocupação</button>
      <button type="button" data-metric="adr" aria-pressed="false">ADR</button>
      <button type="button" data-metric="revpar" aria-pressed="false">RevPAR</button>
    </div>
    <div id="comercial-chart"></div>
  </div>
  <script>
  (function(){
    var categories = [/* "Jun/26", ... um por mês, ordem cronológica */];
    var metrics = { receita:{label:'Receita',suffix:'€',values:[...]}, reservas:{label:'Room Nights',suffix:'',values:[...]}, ocupacaoPct:{label:'Ocupação',suffix:'%',values:[...]}, adr:{label:'ADR',suffix:'€',values:[...]}, revpar:{label:'RevPAR',suffix:'€',values:[/* adr*ocupacaoPct/100 */]} };
    function fmt(suffix){ return function(v){ if (suffix==='€') return Math.round(v).toLocaleString('pt-PT')+'€'; if (suffix==='%') return v.toLocaleString('pt-PT',{minimumFractionDigits:1,maximumFractionDigits:1})+'%'; return Math.round(v).toLocaleString('pt-PT'); }; }
    function render(key){ var m=metrics[key]; window.CraveiralCharts.lineChart(document.getElementById('comercial-chart'), {categories:categories, series:[{slot:1,label:m.label,values:m.values}], formatValue:fmt(m.suffix), ariaLabel:'Evolução mensal de '+m.label+' do Craveiral'}); }
    var toggle=document.querySelector('.metric-toggle[data-toggle-for="comercial-chart"]');
    toggle.addEventListener('click', function(ev){ var btn=ev.target.closest('button'); if(!btn) return; toggle.querySelectorAll('button').forEach(function(b){ b.setAttribute('aria-pressed', String(b===btn)); }); render(btn.dataset.metric); });
    render('receita');
  })();
  </script>
  ```

  E para o competition set (barras de ADR, só alojamentos com tarifa
  conhecida, ordenados do maior para o menor):

  ```html
  <div class="chart-card">
    <h3>ADR por alojamento</h3>
    <p class="chart-sub">Tarifas mais recentes recolhidas no Lighthouse / Climber (rate shopping); alojamentos sem tarifa disponível não aparecem no gráfico.</p>
    <div id="competition-chart"></div>
  </div>
  <script>
  (function(){
    window.CraveiralCharts.barChart(document.getElementById('competition-chart'), {
      items: [/* {label:'Nome do alojamento', value: adr}, ... ordenado por value desc, só quem tem adr */],
      formatValue: function(v){ return Math.round(v).toLocaleString('pt-PT')+'€'; },
      ariaLabel: 'ADR por alojamento do competition set',
      labelWidth: 210
    });
  })();
  </script>
  ```

  O script de exemplo completo que gerou a versão de 19/09/2026 está em
  `/home/claude/apply_charts_public.py` nessa mesma sessão, caso seja
  preciso reconstruir tudo do zero; para o uso diário normal, basta seguir
  os dois blocos acima com os dados frescos das coleções.

## Ciclo diário

1. Recolher o texto do relatório do dia (o mais recente disponível na pasta
   do mês corrente em "RELATÓRIOS DIÁRIOS"). A forma comprovada de o fazer
   sem precisar de um computador ligado: abrir o ficheiro "Histórico e
   Previsão ..." no preview do próprio Google Drive (não fazer download) e
   ir avançando página a página (o relatório tem sempre 12 páginas, uma por
   mês do ano) com `get_page_text` a cada página — **avançar devagar, uma
   página de cada vez**; um scroll grande pode saltar uma página inteira
   sem ela chegar a ser desenhada, e essa página fica em falta no texto.
   Concatenar o texto das 12 páginas, por ordem, num único ficheiro de
   texto.
2. Correr:
   ```
   python3 scripts/update_pickup.py \
     --history data/pickup_history.csv.gz \
     --text-file <ficheiro de texto do passo 1> \
     --html index.html
   ```
   Isto:
   - confirma que o texto tem uma data de observação e pelo menos ~300
     linhas (um relatório completo tem sempre entre ~300 e ~370 linhas,
     uma por dia do ano restante); se tiver muito menos, o script recusa-se
     a escrever nada (é sinal de que uma página ficou por capturar) —
     nesse caso, tentar de novo com mais cuidado no scroll, ou saltar o dia
     sem bloquear o resto da tarefa (o histórico já tem falhas pontuais e o
     Pick-up continua a funcionar comparando as duas leituras mais
     recentes disponíveis, mesmo que não sejam dias de calendário
     consecutivos);
   - actualiza `data/pickup_history.csv.gz` (idempotente: correr duas vezes
     para o mesmo dia substitui as linhas desse dia, não duplica);
   - substitui a secção `<section id="pickup">...</section>` dentro de
     `index.html`, com uma salvaguarda: se o número de tags `<section>` ou
     `</section>` no ficheiro mudar depois da substituição, o script recusa
     escrever esse ficheiro (mostra o erro em vez de arriscar corromper o
     HTML).
3. Publicar `index.html` e `data/pickup_history.csv.gz` atualizados neste
   repositório (`craveiral/painel-craveiral`, branch `main`) — o `git push`
   direto costuma ser recusado pelo proxy desta sessão ("repository not in
   this session's authorized set"); nesse caso usar o mesmo caminho já
   comprovado nesta tarefa: `https://github.com/craveiral/painel-craveiral/upload/main`
   no Chrome já autenticado do utilizador, arrastando os ficheiros
   alterados (`file_upload` do Claude in Chrome) e clicando em "Commit
   changes" (a committer diretamente para `main`).
4. Aplicar a MESMA secção HTML gerada (o `update_pickup.py` também a grava,
   idêntica, dentro do `index.html` atualizado — pode ser lida de lá) ao
   painel privado: ler o artifact publicado
   (`https://claude.ai/artifact/AZZXSg1y3y4Yt31w2TeYkW`) com a ferramenta
   Artifact, substituir a mesma secção pickup no seu HTML, e publicar de
   novo (`url` = o link acima).

## Coisas já resolvidas, não repetir a investigação

- O `pdftotext -layout` mistura acentos corretamente só se os ficheiros
  forem extraídos com `zipfile` do Python, nunca com `unzip` da CLI (que
  corrompe nomes acentuados neste ambiente).
- A coluna do preço médio pode conter `NaN`, `∞` ou `-∞` (quando há zero
  quartos pagos nesse dia) em vez de um número — `parse_lib.py` já trata
  estes casos como "sem valor" (`None`), não como erro de parsing.
- Testado ao vivo (19/09/2026): o preview de PDF do Google Drive devolve
  texto limpo, uma linha por linha da tabela, por ordem correta, com
  espaços simples entre valores (não preserva o alinhamento de colunas do
  PDF original, mas isso não importa — o parser já lida com espaços
  simples). O único risco real é uma página ser saltada durante o scroll.

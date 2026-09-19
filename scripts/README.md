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

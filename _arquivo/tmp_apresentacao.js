// Apresentação Sprint Comercial 19/05 → 26/05 - Data Lake Nevoni
// 7 slides executivos pro Victor

const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "Gustavo Neves - Vanguardia";
pres.title = "Sprint Comercial 19-26/05 — Data Lake Nevoni";

// Paleta Midnight Executive
const NAVY    = "1E2761";
const ICE     = "CADCFC";
const WHITE   = "FFFFFF";
const ACCENT  = "10B981";  // verde - sucesso
const WARN    = "FB923C";  // laranja - atenção
const MUTED   = "64748B";  // cinza escuro
const BG_DARK = "0F1A3A";  // navy mais escuro
const BG_SOFT = "F5F7FB";  // off-white levíssimo

const FONT_HEAD = "Calibri";
const FONT_BODY = "Calibri";

const W = 13.3, H = 7.5;

// Helpers
function addHeader(slide, kicker, title) {
  slide.background = { color: WHITE };
  slide.addText(kicker, {
    x: 0.6, y: 0.4, w: 12, h: 0.4,
    fontSize: 12, fontFace: FONT_HEAD, bold: true,
    color: ACCENT, charSpacing: 4, margin: 0,
  });
  slide.addText(title, {
    x: 0.6, y: 0.8, w: 12, h: 0.9,
    fontSize: 32, fontFace: FONT_HEAD, bold: true,
    color: NAVY, margin: 0,
  });
}

function addFooter(slide, pageNum) {
  slide.addText("Vanguardia · Data Lake Nevoni · Sprint Comercial 19→26 Maio 2026", {
    x: 0.6, y: H - 0.4, w: 10, h: 0.3,
    fontSize: 9, fontFace: FONT_BODY, color: MUTED, margin: 0,
  });
  slide.addText(`${pageNum} / 7`, {
    x: W - 1.4, y: H - 0.4, w: 0.8, h: 0.3,
    fontSize: 9, fontFace: FONT_BODY, color: MUTED, align: "right", margin: 0,
  });
}

// ============================================================
// SLIDE 1 — CAPA
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: BG_DARK };

  // bloco de cor lateral
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.25, h: H, fill: { color: ACCENT }, line: { type: "none" },
  });

  s.addText("DATA LAKE NEVONI", {
    x: 0.8, y: 1.4, w: 11, h: 0.5,
    fontSize: 14, fontFace: FONT_HEAD, bold: true,
    color: ICE, charSpacing: 8, margin: 0,
  });

  s.addText("Sprint Comercial", {
    x: 0.8, y: 2.0, w: 11, h: 1.3,
    fontSize: 64, fontFace: FONT_HEAD, bold: true,
    color: WHITE, margin: 0,
  });

  s.addText("19 → 26 de Maio 2026", {
    x: 0.8, y: 3.2, w: 11, h: 0.7,
    fontSize: 28, fontFace: FONT_HEAD,
    color: ICE, margin: 0,
  });

  // Linha divisória sutil
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 4.3, w: 3, h: 0.04, fill: { color: ACCENT }, line: { type: "none" },
  });

  s.addText("Da auditoria à carteira oficial", {
    x: 0.8, y: 4.6, w: 11, h: 0.6,
    fontSize: 22, fontFace: FONT_HEAD, italic: true,
    color: WHITE, margin: 0,
  });

  s.addText("Base operacional 100% validada, RFV reprocessado e dashboard executivo no ar.", {
    x: 0.8, y: 5.2, w: 11, h: 0.5,
    fontSize: 14, fontFace: FONT_BODY,
    color: ICE, margin: 0,
  });

  // Rodapé com autor
  s.addText("Vanguardia  ·  Apresentação semanal", {
    x: 0.8, y: H - 0.7, w: 8, h: 0.3,
    fontSize: 11, fontFace: FONT_BODY,
    color: ICE, margin: 0,
  });
  s.addText("26/05/2026", {
    x: W - 2.5, y: H - 0.7, w: 1.7, h: 0.3,
    fontSize: 11, fontFace: FONT_BODY,
    color: ICE, align: "right", margin: 0,
  });
}

// ============================================================
// SLIDE 2 — STATUS DO QUE FOI PEDIDO
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "RECAP DA REUNIÃO ANTERIOR", "O que foi pedido em 19/05 — Status hoje");

  const itens = [
    { titulo: "Quadrantes RFV iguais ao Excel", status: "ENTREGUE",
      detalhe: "Matriz visual com cores por segmento + glossário lateral implementado." },
    { titulo: "Quantidade de clientes correta", status: "ENTREGUE",
      detalhe: "De 556 mapeados → carteira oficial com 1.934 clientes únicos (planilha Inside Sales + Farmers)." },
    { titulo: "Visão por família, vendedor e empresa", status: "ENTREGUE",
      detalhe: "Filtros independentes; vendedor escopado por família + período." },
    { titulo: "Decisão de BI (Streamlit × Luzmo × Looker)", status: "DEFINIDO",
      detalhe: "Streamlit confirmado pelo Victor: rápido, flexível, IA integrada." },
    { titulo: "Acessos por persona (gestor × operacional)", status: "PRONTO p/ aplicar",
      detalhe: "Arquitetura de autenticação validada (Sara) — aplicar quando definirmos usuários." },
    { titulo: "Apresentar resultados ao Alves antes do call", status: "ENTREGUE",
      detalhe: "Reunião 25/05 — 8 decisões oficiais consolidadas." },
  ];

  const colW = 6.0, rowH = 1.65, gapX = 0.3, gapY = 0.2;
  const startX = 0.6, startY = 2.0;

  itens.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (colW + gapX);
    const y = startY + row * (rowH + gapY);

    // card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: colW, h: rowH,
      fill: { color: BG_SOFT }, line: { color: ICE, width: 1 },
    });
    // accent bar
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.08, h: rowH, fill: { color: ACCENT }, line: { type: "none" },
    });

    // título
    s.addText(it.titulo, {
      x: x + 0.25, y: y + 0.15, w: colW - 1.8, h: 0.45,
      fontSize: 15, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
    });

    // badge status
    s.addShape(pres.shapes.RECTANGLE, {
      x: x + colW - 1.55, y: y + 0.2, w: 1.4, h: 0.35,
      fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(it.status, {
      x: x + colW - 1.55, y: y + 0.2, w: 1.4, h: 0.35,
      fontSize: 10, fontFace: FONT_HEAD, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0, charSpacing: 2,
    });

    // detalhe
    s.addText(it.detalhe, {
      x: x + 0.25, y: y + 0.7, w: colW - 0.4, h: rowH - 0.8,
      fontSize: 11, fontFace: FONT_BODY, color: MUTED, margin: 0,
    });
  });

  addFooter(s, 2);
}

// ============================================================
// SLIDE 3 — DESCOBERTAS CRÍTICAS DA SEMANA
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "AUDITORIA TÉCNICA", "Descobertas críticas que mudaram a base");

  const descobertas = [
    { titulo: "Fórmula MAX(data) do Excel",
      problema: "100% dos clientes em Farmácias e SAC tinham recência errada",
      acao: "Reescrevemos a planilha Hospitalar e validamos metodologia" },
    { titulo: "Carteira manual fantasma",
      problema: "98,7% dos 1.342 clientes ativos já estavam excluídos no ERP",
      acao: "Limpeza aplicada — base passou de 1.342 → 1.104 reais" },
    { titulo: "Filtro de naturezas <>'N'",
      problema: "Hipótese baseada em fala do Frederico, sem dados",
      acao: "842/842 naturezas validadas — 99,97% do excluído é legítimo" },
    { titulo: "Bug latente no loader BigQuery",
      problema: "Qualquer fact com DATE nulo falhava silenciosamente",
      acao: "Corrigido — afetava potencialmente todas as facts do pipeline" },
  ];

  const cardW = 2.95, cardH = 4.4, gapX = 0.2;
  const startX = 0.6, startY = 2.0;

  descobertas.forEach((d, i) => {
    const x = startX + i * (cardW + gapX);
    const y = startY;

    // card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cardW, h: cardH,
      fill: { color: WHITE }, line: { color: ICE, width: 1 },
      shadow: { type: "outer", color: NAVY, blur: 8, offset: 2, angle: 90, opacity: 0.08 },
    });
    // top accent
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cardW, h: 0.12, fill: { color: WARN }, line: { type: "none" },
    });

    // número
    s.addText(`0${i + 1}`, {
      x: x + 0.25, y: y + 0.35, w: 1, h: 0.5,
      fontSize: 28, fontFace: FONT_HEAD, bold: true,
      color: WARN, margin: 0,
    });

    // título
    s.addText(d.titulo, {
      x: x + 0.25, y: y + 1.0, w: cardW - 0.5, h: 0.8,
      fontSize: 15, fontFace: FONT_HEAD, bold: true,
      color: NAVY, margin: 0,
    });

    // label problema
    s.addText("PROBLEMA", {
      x: x + 0.25, y: y + 1.95, w: cardW - 0.5, h: 0.25,
      fontSize: 9, fontFace: FONT_HEAD, bold: true,
      color: WARN, charSpacing: 2, margin: 0,
    });
    s.addText(d.problema, {
      x: x + 0.25, y: y + 2.2, w: cardW - 0.5, h: 0.9,
      fontSize: 11, fontFace: FONT_BODY, color: MUTED, margin: 0,
    });

    // label ação
    s.addText("AÇÃO", {
      x: x + 0.25, y: y + 3.15, w: cardW - 0.5, h: 0.25,
      fontSize: 9, fontFace: FONT_HEAD, bold: true,
      color: ACCENT, charSpacing: 2, margin: 0,
    });
    s.addText(d.acao, {
      x: x + 0.25, y: y + 3.4, w: cardW - 0.5, h: 0.9,
      fontSize: 11, fontFace: FONT_BODY, color: NAVY, bold: true, margin: 0,
    });
  });

  addFooter(s, 3);
}

// ============================================================
// SLIDE 4 — NOVA CARTEIRA OFICIAL
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "ENTREGA PRINCIPAL", "Nova carteira oficial em produção");

  // 4 big numbers no topo
  const stats = [
    { num: "1.935", label: "clientes ativos", sub: "vs 1.044 anteriores", color: ACCENT },
    { num: "+982",  label: "novos adicionados", sub: "estavam fora do sistema", color: NAVY },
    { num: "+261",  label: "trocaram de vendedor", sub: "alinhado com Alves", color: NAVY },
    { num: "+96",   label: "inativados", sub: "saíram da planilha", color: WARN },
  ];

  const statW = 2.95, statH = 1.7, gapX = 0.2;
  const startX = 0.6, startY = 1.95;

  stats.forEach((st, i) => {
    const x = startX + i * (statW + gapX);
    const y = startY;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: statW, h: statH,
      fill: { color: BG_SOFT }, line: { color: ICE, width: 1 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: statW, h: 0.08, fill: { color: st.color }, line: { type: "none" },
    });
    s.addText(st.num, {
      x, y: y + 0.2, w: statW, h: 0.85,
      fontSize: 44, fontFace: FONT_HEAD, bold: true,
      color: st.color, align: "center", margin: 0,
    });
    s.addText(st.label, {
      x, y: y + 1.05, w: statW, h: 0.3,
      fontSize: 13, fontFace: FONT_HEAD, bold: true,
      color: NAVY, align: "center", margin: 0,
    });
    s.addText(st.sub, {
      x, y: y + 1.35, w: statW, h: 0.3,
      fontSize: 10, fontFace: FONT_BODY,
      color: MUTED, align: "center", margin: 0,
    });
  });

  // ANTES x DEPOIS
  s.addText("Vendedores reais identificados", {
    x: 0.6, y: 3.95, w: 12, h: 0.4,
    fontSize: 16, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
  });

  // 2 colunas: ANTES / DEPOIS
  const colY = 4.45, colH = 2.3;

  // ANTES
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: colY, w: 6.0, h: colH,
    fill: { color: BG_SOFT }, line: { color: ICE, width: 1 },
  });
  s.addText("ANTES (carteira manual)", {
    x: 0.8, y: colY + 0.15, w: 5.6, h: 0.35,
    fontSize: 11, fontFace: FONT_HEAD, bold: true,
    color: MUTED, charSpacing: 2, margin: 0,
  });
  s.addText("3 vendedores nominais", {
    x: 0.8, y: colY + 0.55, w: 5.6, h: 0.45,
    fontSize: 20, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
  });
  s.addText([
    { text: "Guilherme · Kaua · Richard", options: { breakLine: true, color: NAVY, fontSize: 13 } },
    { text: "+ 222 \"Sem Vendedor\" + patches manuais (Ribeiro/Ramos/Giovanna)",
      options: { color: MUTED, fontSize: 11, italic: true } },
  ], {
    x: 0.8, y: colY + 1.05, w: 5.6, h: 1.1,
    fontFace: FONT_BODY, margin: 0,
  });

  // DEPOIS
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: colY, w: 6.0, h: colH,
    fill: { color: NAVY }, line: { type: "none" },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 6.8, y: colY, w: 0.08, h: colH, fill: { color: ACCENT }, line: { type: "none" },
  });
  s.addText("DEPOIS (planilha oficial Inside Sales + Farmers)", {
    x: 7.0, y: colY + 0.15, w: 5.7, h: 0.35,
    fontSize: 11, fontFace: FONT_HEAD, bold: true,
    color: ICE, charSpacing: 2, margin: 0,
  });
  s.addText("7 vendedores reais", {
    x: 7.0, y: colY + 0.55, w: 5.7, h: 0.45,
    fontSize: 20, fontFace: FONT_HEAD, bold: true, color: WHITE, margin: 0,
  });
  s.addText([
    { text: "Guilherme Aquino (315) · Kauã Rodrigues (295) · Richard Lucas (435)",
      options: { breakLine: true, color: WHITE, fontSize: 12 } },
    { text: "Kauan Ramos (389) · Eduardo Marques (81) · Cauã Ribeiro (262)",
      options: { breakLine: true, color: WHITE, fontSize: 12 } },
    { text: "Geovanna Gomes (158) — só em SAC (decisão Alves 25/05)",
      options: { color: ACCENT, fontSize: 12, bold: true } },
  ], {
    x: 7.0, y: colY + 1.05, w: 5.7, h: 1.15,
    fontFace: FONT_BODY, margin: 0,
  });

  addFooter(s, 4);
}

// ============================================================
// SLIDE 5 — DASHBOARD SEMANAL DE LIDERANÇA
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "NOVA ENTREGA", "Dashboard Semanal de Liderança · Aba Vendas");

  s.addText("Substitui o trabalho manual semanal do Alves — leitura automática direto do Data Lake.", {
    x: 0.6, y: 1.7, w: 12, h: 0.4,
    fontSize: 13, fontFace: FONT_BODY, italic: true, color: MUTED, margin: 0,
  });

  // Coluna esquerda: KPIs do dashboard
  const leftX = 0.6, topY = 2.3;
  s.addShape(pres.shapes.RECTANGLE, {
    x: leftX, y: topY, w: 6.0, h: 4.2,
    fill: { color: BG_SOFT }, line: { color: ICE, width: 1 },
  });
  s.addText("KPIs em destaque", {
    x: leftX + 0.25, y: topY + 0.15, w: 5.5, h: 0.4,
    fontSize: 15, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
  });

  const kpis = [
    "Faturamento do mês selecionado",
    "vs Mês Anterior — variação automática (Δ MoM)",
    "vs Mesmo Mês Ano Anterior — comparativo YoY",
    "Ticket Médio do período",
    "Transações (deals fechados)",
  ];
  s.addText(
    kpis.map((k, i) => ({
      text: k,
      options: { bullet: true, breakLine: i < kpis.length - 1, fontSize: 12, color: NAVY },
    })),
    { x: leftX + 0.35, y: topY + 0.65, w: 5.5, h: 2.0, fontFace: FONT_BODY, margin: 0,
      paraSpaceAfter: 6 },
  );

  s.addText("Por que sem meta hardcoded?", {
    x: leftX + 0.25, y: topY + 2.85, w: 5.5, h: 0.35,
    fontSize: 12, fontFace: FONT_HEAD, bold: true, color: WARN, margin: 0,
  });
  s.addText("Decisão Alves (25/05): meta é manual com carry-over entre semanas, definida pelo Vinícius. Substituímos predição automática por comparativos MoM + YoY, fiel à operação.", {
    x: leftX + 0.25, y: topY + 3.2, w: 5.5, h: 0.95,
    fontSize: 11, fontFace: FONT_BODY, color: MUTED, italic: true, margin: 0,
  });

  // Coluna direita: Canais cobertos
  const rightX = 6.9;
  s.addShape(pres.shapes.RECTANGLE, {
    x: rightX, y: topY, w: 5.8, h: 4.2,
    fill: { color: NAVY }, line: { type: "none" },
  });
  s.addText("Canais cobertos", {
    x: rightX + 0.25, y: topY + 0.15, w: 5.3, h: 0.4,
    fontSize: 15, fontFace: FONT_HEAD, bold: true, color: WHITE, margin: 0,
  });

  const canais = [
    { nome: "Hospitalar",   fonte: "carteira (rfv_familia)",  cor: ICE },
    { nome: "Marketplace",  fonte: "YCODVEN do ERP (ML/Amazon/Shopee/etc)", cor: ICE },
    { nome: "Farmácias",    fonte: "carteira Farmers",         cor: ICE },
    { nome: "SAC",          fonte: "carteira (Geovanna)",      cor: ICE },
    { nome: "Outros",       fonte: "fallback — cliente novo",  cor: ICE },
  ];
  canais.forEach((c, i) => {
    const ry = topY + 0.75 + i * 0.6;
    s.addShape(pres.shapes.OVAL, {
      x: rightX + 0.3, y: ry + 0.1, w: 0.18, h: 0.18, fill: { color: ACCENT }, line: { type: "none" },
    });
    s.addText(c.nome, {
      x: rightX + 0.6, y: ry, w: 2.2, h: 0.4,
      fontSize: 14, fontFace: FONT_HEAD, bold: true, color: WHITE, margin: 0,
    });
    s.addText(c.fonte, {
      x: rightX + 2.8, y: ry + 0.04, w: 2.85, h: 0.4,
      fontSize: 11, fontFace: FONT_BODY, color: c.cor, italic: true, margin: 0,
    });
  });

  addFooter(s, 5);
}

// ============================================================
// SLIDE 6 — REUNIÃO 25/05 — 8 DECISÕES OFICIAIS
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "ALINHAMENTO COMERCIAL", "Reunião 25/05 com Alves · 8 decisões oficiais");

  const decisoes = [
    ["Carteira é fonte da verdade",        "Quem fez o pedido NÃO muda o dono"],
    ["Conflito → maior valor pesa",        "Empate cai pra prioridade da carteira"],
    ["Giovanna só em SAC",                  "158 clientes Hosp reclassificados pra SAC"],
    ["Vendedor D = Kauan Ramos",            "Confirmado via WhatsApp"],
    ["\"Sem Vendedor\" = Cliente Novo",     "Não é débito — chegou pós-corte 2024-25"],
    ["Filtro <>'N' validado",                "Devolução compensada por outro pedido"],
    ["Meta semanal é manual (Vinícius)",   "Sem predição automática — usar carry-over"],
    ["Doc Data Lake → Albert",              "Albert vai aprender Streamlit com camada Gold"],
  ];

  const colW = 6.05, rowH = 0.85, gapX = 0.25, gapY = 0.15;
  const startX = 0.6, startY = 1.95;

  decisoes.forEach((d, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (colW + gapX);
    const y = startY + row * (rowH + gapY);

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: colW, h: rowH,
      fill: { color: BG_SOFT }, line: { type: "none" },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 0.08, h: rowH, fill: { color: ACCENT }, line: { type: "none" },
    });

    // número
    s.addText(`${i + 1}`, {
      x: x + 0.25, y: y + 0.15, w: 0.5, h: 0.55,
      fontSize: 22, fontFace: FONT_HEAD, bold: true, color: ACCENT, margin: 0,
    });
    // título decisão
    s.addText(d[0], {
      x: x + 0.85, y: y + 0.08, w: colW - 1.0, h: 0.4,
      fontSize: 13, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
    });
    // detalhe
    s.addText(d[1], {
      x: x + 0.85, y: y + 0.45, w: colW - 1.0, h: 0.35,
      fontSize: 10, fontFace: FONT_BODY, color: MUTED, margin: 0,
    });
  });

  // CTA no rodapé
  s.addText("Resultado: pipeline aplicado em produção (1.935 ativos + 96 inativados) e RFV reprocessado de Jan→Mai/2026.", {
    x: 0.6, y: 6.45, w: 12, h: 0.35,
    fontSize: 11, fontFace: FONT_BODY, italic: true, bold: true,
    color: ACCENT, margin: 0,
  });

  addFooter(s, 6);
}

// ============================================================
// SLIDE 7 — PRÓXIMOS PASSOS / ROADMAP
// ============================================================
{
  const s = pres.addSlide();
  addHeader(s, "ROADMAP", "Próximos passos · após esta sprint");

  // 3 colunas: imediato / curto prazo / médio prazo
  const trilhas = [
    {
      label: "EM ANDAMENTO",
      labelColor: ACCENT,
      titulo: "Comercial — fechamento",
      itens: [
        "Validação final do dashboard com Alves",
        "Albert recebendo doc do Data Lake p/ aprender Streamlit",
        "Funil CRM corrigido (3 pipelines integrados)",
      ],
    },
    {
      label: "PRÓXIMA SPRINT",
      labelColor: NAVY,
      titulo: "Financeiro — Gold com Diego",
      itens: [
        "gold_fin_dre_mensal (caixa × competência)",
        "gold_fin_kpis_mensais consolidado",
        "param_fin_metas_mensais (metas Diego)",
        "Validação DRE 2026 vs planilha original",
      ],
    },
    {
      label: "BACKLOG",
      labelColor: MUTED,
      titulo: "Setores aguardando fontes",
      itens: [
        "Operacional + Produção (fontes mapeadas)",
        "SAC + Assistência Técnica (Bronze pronto)",
        "TI / RH / Eng. Produto (ClickUp + Miro)",
        "Servidor físico (chamar diretor TI)",
      ],
    },
  ];

  const cardW = 4.0, cardH = 4.6, gapX = 0.25;
  const startX = 0.6, startY = 1.95;

  trilhas.forEach((t, i) => {
    const x = startX + i * (cardW + gapX);
    const y = startY;

    // card
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cardW, h: cardH,
      fill: { color: WHITE }, line: { color: ICE, width: 1 },
      shadow: { type: "outer", color: NAVY, blur: 8, offset: 2, angle: 90, opacity: 0.08 },
    });
    // top accent
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: cardW, h: 0.12, fill: { color: t.labelColor }, line: { type: "none" },
    });

    // label
    s.addText(t.label, {
      x: x + 0.3, y: y + 0.35, w: cardW - 0.6, h: 0.3,
      fontSize: 10, fontFace: FONT_HEAD, bold: true,
      color: t.labelColor, charSpacing: 3, margin: 0,
    });
    // título
    s.addText(t.titulo, {
      x: x + 0.3, y: y + 0.7, w: cardW - 0.6, h: 0.7,
      fontSize: 18, fontFace: FONT_HEAD, bold: true, color: NAVY, margin: 0,
    });
    // divisor
    s.addShape(pres.shapes.RECTANGLE, {
      x: x + 0.3, y: y + 1.55, w: 0.6, h: 0.04,
      fill: { color: t.labelColor }, line: { type: "none" },
    });
    // itens
    s.addText(
      t.itens.map((it, idx) => ({
        text: it,
        options: { bullet: true, breakLine: idx < t.itens.length - 1, fontSize: 12, color: NAVY },
      })),
      { x: x + 0.4, y: y + 1.85, w: cardW - 0.7, h: cardH - 2.0,
        fontFace: FONT_BODY, margin: 0, paraSpaceAfter: 8 },
    );
  });

  // Linha final destaque
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 6.75, w: 12.1, h: 0.05, fill: { color: ACCENT }, line: { type: "none" },
  });

  addFooter(s, 7);
}

pres.writeFile({ fileName: "C:\\Users\\gusta\\Downloads\\Sprint_Comercial_19-26_Maio.pptx" })
  .then(name => console.log(`✓ Gerado: ${name}`));

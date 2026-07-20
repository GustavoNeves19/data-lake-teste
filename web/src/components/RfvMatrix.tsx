import { fmtNum } from "../lib/format";
import {
  SEGMENT_DISPLAY, SEG_RENDER_ORDER, PERDIDOS_SATELITE_AREA, FIEIS_SATELITE_AREA,
  REC_HEADERS, FREQ_BG, FREQ_DESC,
} from "../theme";
import type { RfvSegment } from "../lib/api";

const FREQ_ROWS = ["F1", "F2", "F3", "F4", "F5"];

export function RfvMatrix({ segments, familia }: { segments: RfvSegment[]; familia: string }) {
  const lookup = new Map<number, RfvSegment>();
  segments.forEach((s) => lookup.set(s.seg_num, s));
  const freqDesc = FREQ_DESC[familia] ?? FREQ_DESC.TODOS;

  const cell = "bg-white box-border";

  return (
    <div className="overflow-x-auto pb-1 mb-2">
      <div
        className="grid gap-px border border-[#1F1F1F] bg-[#1F1F1F]"
        style={{
          minWidth: 1180,
          gridTemplateColumns: "76px 134px 1.25fr 1fr 1.18fr 1.18fr 1.18fr",
          // Row 6 subiu de 72->98px: Hibernando é célula única e o R$ transbordava sobre Perdidos.
          gridTemplateRows: "56px 72px 94px 30px 98px 98px 102px",
        }}
      >
        {/* Rótulos superiores (vermelho) */}
        <div
          className="flex items-center justify-center text-center text-white font-bold text-base px-3"
          style={{ gridArea: "1 / 1 / 2 / 3", background: "#C00000" }}
        >
          Data última compra
        </div>
        <div
          className="flex items-center justify-center text-center text-white font-bold text-base px-3"
          style={{ gridArea: "2 / 1 / 3 / 3", background: "#C00000" }}
        >
          Frequência em 12 meses
        </div>

        {/* Cabeçalhos de recência (R1-R5) */}
        {REC_HEADERS.map((r, i) => (
          <div
            key={`rc-${r.code}`}
            className="flex items-center justify-center text-center text-black font-bold text-lg"
            style={{ gridArea: `1 / ${i + 3} / 2 / ${i + 4}`, background: r.bg }}
          >
            {r.code}
          </div>
        ))}
        {REC_HEADERS.map((r, i) => (
          <div
            key={`rd-${r.code}`}
            className="flex items-center justify-center text-center text-black text-sm px-2"
            style={{ gridArea: `2 / ${i + 3} / 3 / ${i + 4}`, background: r.bg }}
          >
            {r.desc}
          </div>
        ))}

        {/* Frequência (F1-F5): código + descrição */}
        {FREQ_ROWS.map((f, i) => {
          const row = i + 3;
          return (
            <div key={`f-${f}`} className="contents">
              <div
                className="flex items-center justify-center text-center text-black font-bold text-lg"
                style={{ gridArea: `${row} / 1 / ${row + 1} / 2`, background: FREQ_BG[f] }}
              >
                {f}
              </div>
              <div
                className="flex items-center justify-center text-center text-black text-sm px-2"
                style={{ gridArea: `${row} / 2 / ${row + 1} / 3`, background: FREQ_BG[f] }}
              >
                {freqDesc[f]}
              </div>
            </div>
          );
        })}

        {/* Satélite Perdidos (preenche célula sem repetir número) */}
        <div className={cell} style={{ gridArea: PERDIDOS_SATELITE_AREA, background: SEGMENT_DISPLAY[11].bg }} />
        {/* Satélite Fiéis: F2R1 é Fiéis, mas fica fora do bloco principal (Campeões
            agora é só F1R1). Preenche a célula com a cor de Fiéis, sem número. */}
        <div className={cell} style={{ gridArea: FIEIS_SATELITE_AREA, background: SEGMENT_DISPLAY[2].bg }} />

        {/* Blocos de segmento */}
        {SEG_RENDER_ORDER.map((seg) => {
          const cfg = SEGMENT_DISPLAY[seg];
          const d = lookup.get(seg);
          const clientes = d?.clientes ?? 0;
          const fat = d?.faturamento ?? 0;
          return (
            <div
              key={`seg-${seg}`}
              className="relative flex flex-col items-center justify-start text-center px-3.5 pt-2.5 pb-3.5 overflow-hidden"
              style={{ gridArea: cfg.area, background: cfg.bg, color: cfg.fg }}
            >
              <div className="text-lg font-bold leading-tight mt-0.5">{cfg.nome}</div>
              <div className="text-2xl font-extrabold leading-none mt-2.5">{clientes}</div>
              <div className="w-full mt-auto flex items-baseline justify-between gap-2.5 text-base font-bold leading-none">
                <span className="min-w-[30px] text-left">R$</span>
                <span className="flex-1 text-right">{fmtNum(fat, 2)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

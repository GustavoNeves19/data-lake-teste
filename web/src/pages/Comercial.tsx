import { useState } from "react";
import { PageHeader, Tabs } from "../components/layout";
import { isResourceHidden } from "../lib/access";
import { getPageResourceTabs } from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";
import VendasTab from "../tabs/VendasTab";
import GestaoVistaTab from "../tabs/GestaoVistaTab";
import RfvTab from "../tabs/RfvTab";
import PerformanceTab from "../tabs/PerformanceTab";

export default function Comercial() {
  const { user } = useAuth();
  // Matriz Performance é só nível gestão (Vinícius/Alves) — decisão reunião 09/07.
  // Vendedor não vê a aba nem os dados individuais de esforço x resultado.
  const podeVerPerformance = !!(user?.pode_editar_metas || user?.is_admin);
  const tabs = getPageResourceTabs("/comercial")
    .filter((t) => t.id !== "performance" || podeVerPerformance)
    .filter((t) => !isResourceHidden(user, t.resource))
    .map(({ id, label }) => ({ id, label }));
  const [tab, setTab] = useState("vendas");
  const tabAtiva = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id;

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="Vendas"
        subtitle="A operação comercial da semana. Do pedido novo ao cliente que precisa de retomada."
        sources={[
          { name: "ERP + Pipedrive", active: true },
        ]}
      />
      {tabs.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white px-5 py-4 text-sm text-gray-600">
          Nenhuma aba comercial está habilitada para o seu usuário.
        </div>
      ) : (
        <Tabs tabs={tabs} active={tabAtiva ?? tabs[0].id} onChange={setTab} />
      )}
      {tabAtiva === "vendas" && <VendasTab />}
      {tabAtiva === "gestao" && <GestaoVistaTab />}
      {tabAtiva === "rfv" && <RfvTab />}
      {tabAtiva === "performance" && podeVerPerformance && <PerformanceTab />}
    </div>
  );
}

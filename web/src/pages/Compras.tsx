import { PageHeader } from "../components/layout";
import ComprasTab from "../tabs/ComprasTab";

export default function Compras() {
  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="Compras"
        subtitle="Suprimentos e importação. O que entra pra sustentar o que a Comercial vende."
        sources={[{ name: "ERP", active: true }]}
      />
      <ComprasTab />
    </div>
  );
}

import { PageHeader } from "./layout";

// Placeholder de setor ainda em migração para a Nevoni 360.
export default function ComingSoon({ title, note }: { title: string; note?: string }) {
  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader title={title} subtitle={note ?? "Setor em migração do Streamlit para a Nevoni 360."} />
      <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
        <div className="text-5xl mb-4">🚧</div>
        <p className="text-lg font-semibold text-gray-700">Em construção</p>
        <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
          Esta área está sendo migrada do Streamlit. Assim como na Comercial, os números virão
          da camada gold já validada no BigQuery, batendo o ERP ao centavo.
        </p>
      </div>
    </div>
  );
}

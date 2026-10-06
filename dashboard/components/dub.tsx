/** Primitives Dub (DESIGN.md) : compactes, plates et structurées par la bordure. */

export function Carte({ children, className = "", ...reste }: React.ComponentProps<"div">) {
  return <div {...reste} className={`rounded-(--radius-cards) border border-ash bg-canvas-white p-4 ${className}`}>{children}</div>;
}

export function Tag({ children, accent = "blue" }: { children: React.ReactNode; accent?: "blue" | "orange" | "green" | "violet" }) {
  const couleur = { blue: "bg-electric-blue", orange: "bg-tangerine", green: "bg-vivid-green", violet: "bg-lavender" }[accent];
  return (
    <span className="inline-flex min-h-7 self-start items-center gap-2 rounded-(--radius-pill) bg-paper-mist px-3 text-[12px] font-medium text-charcoal">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${couleur}`} />
      {children}
    </span>
  );
}

export function Etat({ genre, titre, detail, action }: { genre: "vide" | "erreur" | "alerte"; titre: string; detail?: React.ReactNode; action?: React.ReactNode }) {
  const style = genre === "erreur" ? "border-tangerine/40 bg-soft-tangerine" : genre === "alerte" ? "border-smoke bg-paper-mist" : "border-ash bg-canvas-white";
  return (
    <div role="status" className={`rounded-(--radius-cards) border ${style} px-5 py-8 text-center`}>
      <p className="text-body-lg font-medium text-balance">{titre}</p>
      {detail ? <p className="mx-auto mt-2 max-w-[52ch] text-[14px] text-steel">{detail}</p> : null}
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

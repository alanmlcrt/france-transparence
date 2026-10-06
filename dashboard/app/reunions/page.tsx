import { siBaseAbsente } from "@/components/base-absente";
import Link from "next/link";
import { TableauReunions } from "@/components/reunions-table";
import { LIBELLES_ETAT, type EtatLecture } from "@/lib/etat-lecture";
import { communesMoissonnees, optionsTags, reunionsFiltrees, type FiltresReunions } from "@/lib/reunions";

export const metadata = { title: "Réunions" };
export const dynamic = "force-dynamic";

type Parametres = { q?: string; insee?: string; etat?: string; type?: string; theme?: string; signal?: string; du?: string; au?: string; page?: string };

/** Cent lignes par page : tout rendre d'un coup produisait 530 Ko de HTML, et
 *  couper à 500 sans le dire cachait le reste des résultats. */
const PAR_PAGE = 100;

export default async function Reunions({ searchParams }: { searchParams: Promise<Parametres> }) {
  try {
    const params = await searchParams;
    const filtres: FiltresReunions = {
      q: params.q,
      insee: params.insee,
      etat: etatValide(params.etat),
      type: params.type,
      theme: params.theme,
      signal: params.signal,
      du: params.du,
      au: params.au,
    };
    const toutes = reunionsFiltrees(filtres);
    const pages = Math.max(1, Math.ceil(toutes.length / PAR_PAGE));
    const page = Math.min(pages, Math.max(1, Number.parseInt(params.page ?? "1", 10) || 1));
    const liste = toutes.slice((page - 1) * PAR_PAGE, page * PAR_PAGE);
    const lienPage = (n: number) => {
      const q = new URLSearchParams(Object.entries(params).filter(([k, v]) => v && k !== "page") as [string, string][]);
      if (n > 1) q.set("page", String(n));
      const s = q.toString();
      return s ? `/reunions?${s}` : "/reunions";
    };
    const communes = communesMoissonnees();
    const tags = optionsTags();
    const filtreActif = Object.entries(params).some(([k, v]) => v && k !== "page");

    return (
      <div className="py-10 sm:py-14">
        <header className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-[690px]">
            <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-fog">Base documentaire</p>
            <h1 className="mt-2 font-display text-[clamp(36px,6vw,48px)] font-medium leading-none tracking-[-0.04em]">Toutes les réunions</h1>
            <p className="mt-5 text-body-lg text-steel">Recherchez par ville, période, état de lecture, sujet ou signal utile.</p>
          </div>
          <p className="rounded-(--radius-pill) bg-paper-mist px-3 py-2 text-[12px] font-medium text-steel">{toutes.length} résultat{toutes.length > 1 ? "s" : ""}{pages > 1 ? ` · page ${page} sur ${pages}` : ""}</p>
        </header>

        <form method="get" action="/reunions" role="search" className="mt-8 rounded-(--radius-cards) border border-ash bg-paper-mist/50 p-4">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <Champ label="Rechercher" large>
              <input name="q" type="search" defaultValue={params.q ?? ""} placeholder="Objet, numéro, service, ou mot du résumé…" className="controle-filtre" />
            </Champ>
            <Champ label="Ville">
              <select name="insee" defaultValue={params.insee ?? ""} className="controle-filtre"><option value="">Toutes</option>{communes.map((c) => <option key={c.insee} value={c.insee}>{c.commune ?? c.insee}</option>)}</select>
            </Champ>
            <Champ label="Lecture">
              <select name="etat" defaultValue={params.etat ?? ""} className="controle-filtre">
                <option value="">Tous les états</option>
                {(Object.keys(LIBELLES_ETAT) as EtatLecture[]).map((etat) => <option key={etat} value={etat}>{LIBELLES_ETAT[etat]}</option>)}
              </select>
            </Champ>
            {tags.types.length ? (
            <Champ label="Type">
              <select name="type" defaultValue={params.type ?? ""} className="controle-filtre"><option value="">Tous les types</option>{tags.types.map((type) => <option key={type}>{type}</option>)}</select>
            </Champ>) : null}
            {tags.themes.length ? (
            <Champ label="Thème">
              <select name="theme" defaultValue={params.theme ?? ""} className="controle-filtre"><option value="">Tous les thèmes</option>{tags.themes.map((theme) => <option key={theme}>{theme}</option>)}</select>
            </Champ>) : null}
            {tags.signals.length ? (
            <Champ label="Signal utile">
              <select name="signal" defaultValue={params.signal ?? ""} className="controle-filtre"><option value="">Tous les signaux</option>{tags.signals.map((signal) => <option key={signal}>{signal}</option>)}</select>
            </Champ>) : null}
            <Champ label="Du"><input name="du" type="date" defaultValue={params.du ?? ""} className="controle-filtre" /></Champ>
            <Champ label="Au"><input name="au" type="date" defaultValue={params.au ?? ""} className="controle-filtre" /></Champ>
            <div className="flex items-end gap-2">
              <button type="submit" className="min-h-11 flex-1 rounded-(--radius-buttons) bg-midnight-ink px-4 text-[14px] font-medium text-white hover:bg-graphite">Filtrer</button>
              {filtreActif ? <Link href="/reunions" className="inline-flex min-h-11 items-center rounded-(--radius-buttons) border border-ash bg-white px-3 text-[13px] font-medium hover:bg-paper-mist">Effacer</Link> : null}
            </div>
          </div>
        </form>

        <div className="mt-6"><TableauReunions liste={liste} /></div>
        {pages > 1 ? (
          <nav aria-label="Pages de résultats" className="mt-6 flex items-center justify-between gap-3 text-[13px] font-medium">
            {page > 1 ? <Link href={lienPage(page - 1)} className="inline-flex min-h-11 items-center rounded-(--radius-buttons) border border-ash px-4 hover:bg-paper-mist">← Précédents</Link> : <span />}
            <span className="text-fog">Page {page} sur {pages}</span>
            {page < pages ? <Link href={lienPage(page + 1)} className="inline-flex min-h-11 items-center rounded-(--radius-buttons) border border-ash px-4 hover:bg-paper-mist">Suivants →</Link> : <span />}
          </nav>
        ) : null}
      </div>
    );
  } catch (erreur) {
    return siBaseAbsente(erreur);
  }
}

function Champ({ label, children, large = false }: { label: string; children: React.ReactNode; large?: boolean }) {
  return <label className={`block ${large ? "lg:col-span-2" : ""}`}><span className="mb-1.5 block text-[11px] font-medium text-steel">{label}</span>{children}</label>;
}

function etatValide(etat?: string): EtatLecture | undefined {
  return etat && etat in LIBELLES_ETAT ? etat as EtatLecture : undefined;
}

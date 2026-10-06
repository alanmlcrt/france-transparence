"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchIcon } from "lucide-react";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import { Kbd } from "@/components/ui/kbd";

type Commune = { insee: string; commune: string | null; type: "commune" | "epci" };
type ReunionLegere = { id: number; titre: string; commune: string | null; insee: string };
type Donnees = { communes: Commune[]; reunions: ReunionLegere[] };

// cmdk filtre par défaut en fuzzy (sous-séquence de lettres) : sur des titres
// longs, ça remonte des correspondances sans rapport. Une simple recherche de
// sous-chaîne, insensible aux accents, est ce que le reste du site fait déjà
// (lib/reunions.ts) — pas réutilisable ici tel quel, ce module tourne côté
// client et ne peut pas importer un fichier qui ouvre la base SQLite.
function sansAccents(texte: string): string {
  return texte.normalize("NFD").replace(/[̀-ͯ]/g, "");
}
function filtrer(valeur: string, recherche: string): number {
  return sansAccents(valeur).toLocaleLowerCase("fr").includes(sansAccents(recherche).toLocaleLowerCase("fr")) ? 1 : 0;
}

/** Cmd/Ctrl+K : ouvre une recherche instantanée sur les collectivités et les
 *  réunions déjà chargées côté client — 458 documents, ça tient largement en
 *  mémoire, pas besoin d'interroger le serveur à chaque frappe. Les données ne
 *  sont récupérées qu'à la première ouverture, jamais au chargement de page. */
export function CommandPalette() {
  const [ouvert, setOuvert] = useState(false);
  const [donnees, setDonnees] = useState<Donnees | null>(null);
  const chargement = useRef<Promise<void> | null>(null);
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOuvert((v) => !v);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!ouvert || donnees || chargement.current) return;
    chargement.current = fetch("/api/recherche")
      .then((r) => r.json())
      .then((d: Donnees) => setDonnees(d))
      .catch(() => setDonnees({ communes: [], reunions: [] }));
  }, [ouvert, donnees]);

  function aller(url: string) {
    setOuvert(false);
    router.push(url);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOuvert(true)}
        aria-label="Rechercher"
        className="inline-flex min-h-9 items-center justify-center gap-2 rounded-(--radius-buttons) border border-ash px-2.5 text-[13px] text-fog hover:bg-paper-mist hover:text-charcoal sm:px-3"
      >
        <SearchIcon aria-hidden="true" className="size-4 shrink-0" />
        <span className="hidden sm:inline">Rechercher</span>
        <Kbd className="hidden sm:inline-flex">⌘K</Kbd>
      </button>
      <CommandDialog
        open={ouvert}
        onOpenChange={setOuvert}
        title="Rechercher"
        description="Trouver une collectivité ou une réunion par son nom."
        filter={filtrer}
      >
        <CommandInput placeholder="Une commune, une intercommunalité, une réunion…" />
        <CommandList>
          <CommandEmpty>{donnees ? "Aucun résultat." : "Chargement…"}</CommandEmpty>
          {donnees?.communes.length ? (
            <CommandGroup heading="Collectivités">
              {donnees.communes.map((c) => (
                <CommandItem key={c.insee} value={`${c.commune ?? c.insee} ${c.insee}`} onSelect={() => aller(`/collectivites/${c.insee}`)}>
                  {c.commune ?? c.insee}
                  <span className="ml-auto text-[11px] text-fog">{c.type === "epci" ? "Intercommunalité" : "Commune"}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          {donnees?.reunions.length ? (
            <CommandGroup heading="Réunions">
              {donnees.reunions.map((r) => (
                <CommandItem key={r.id} value={`${r.titre} ${r.commune ?? r.insee}`} onSelect={() => aller(`/reunions/${r.id}`)}>
                  <span className="truncate">{r.titre}</span>
                  <span className="ml-auto shrink-0 text-[11px] text-fog">{r.commune ?? r.insee}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
        </CommandList>
      </CommandDialog>
    </>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Liens de la navigation principale, avec indication de la section courante.
 *  Client uniquement pour lire le chemin : le reste de l'en-tete reste serveur. */
const LIENS = [
  { href: "/", libelle: "Accueil", masqueEnPetit: true },
  { href: "/collectivites", libelle: "Collectivités", masqueEnPetit: false },
  { href: "/reunions", libelle: "Réunions", masqueEnPetit: false },
];

export function NavLiens() {
  const chemin = usePathname();

  return (
    <div className="flex items-center gap-1 text-[13px] font-medium text-steel">
      {LIENS.map(({ href, libelle, masqueEnPetit }) => {
        const actif = href === "/" ? chemin === "/" : chemin === href || chemin.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={actif ? "page" : undefined}
            className={`min-h-10 items-center rounded-(--radius-buttons) px-3 ${
              masqueEnPetit ? "hidden sm:inline-flex" : "inline-flex"
            } ${actif ? "bg-paper-mist text-charcoal" : "hover:bg-paper-mist hover:text-charcoal"}`}
          >
            {libelle}
          </Link>
        );
      })}
    </div>
  );
}

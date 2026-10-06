import Link from "next/link";
import { Etat } from "@/components/dub";

export const metadata = { title: "Page introuvable" };

export default function NonTrouve() {
  return (
    <div className="py-10 sm:py-14">
      <Etat
        genre="vide"
        titre="Cette page n’existe pas"
        detail="L’adresse ne correspond à aucune réunion, collectivité ou section du site."
        action={<Link href="/" className="text-[13px] font-medium text-electric-blue hover:underline">Retour à l’accueil</Link>}
      />
    </div>
  );
}

import fs from "node:fs";
import { Readable } from "node:stream";
import { pdfDe } from "@/lib/reunions";

/**
 * Sert le PDF d'une délibération depuis son chemin ENREGISTRÉ par le
 * collecteur. Aucun chemin fourni par le client n'est accepté.
 */

export const dynamic = "force-dynamic";

export async function GET(
  requete: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  return servir(requete, await params, true);
}

export async function HEAD(
  requete: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  return servir(requete, await params, false);
}

function servir(requete: Request, { id }: { id: string }, corps: boolean) {
  const n = Number(id);
  if (!Number.isInteger(n)) return new Response(null, { status: 404 });

  let pdf;
  try {
    pdf = pdfDe(n);
  } catch {
    return new Response(null, { status: 404 });
  }
  if (!pdf || !fs.existsSync(pdf.cheminLocal)) return new Response(null, { status: 404 });

  const taille = fs.statSync(pdf.cheminLocal).size;
  let debut = 0;
  let fin = taille - 1;
  let partiel = false;

  const plage = requete.headers.get("range");
  if (plage) {
    const m = /bytes=(\d*)-(\d*)/.exec(plage);
    if (m) {
      if (m[1]) debut = Number(m[1]);
      if (m[2]) fin = Math.min(Number(m[2]), taille - 1);
      if (debut > fin || debut >= taille) {
        return new Response(null, {
          status: 416,
          headers: { "content-range": `bytes */${taille}` },
        });
      }
      partiel = true;
    }
  }

  const entetes = new Headers({
    "content-type": "application/pdf",
    "content-length": String(fin - debut + 1),
    "accept-ranges": "bytes",
    "content-disposition": `inline; filename="${pdf.titre.replaceAll('"', "").slice(0, 80)}.pdf"`,
    "cache-control": "private, no-store",
  });
  if (partiel) entetes.set("content-range", `bytes ${debut}-${fin}/${taille}`);

  if (!corps) return new Response(null, { status: partiel ? 206 : 200, headers: entetes });

  const flux = Readable.toWeb(
    fs.createReadStream(pdf.cheminLocal, { start: debut, end: fin }),
  ) as ReadableStream;
  return new Response(flux, { status: partiel ? 206 : 200, headers: entetes });
}

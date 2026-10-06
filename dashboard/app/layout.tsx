import type { Metadata } from "next";
import Link from "next/link";
import { ViewTransition } from "react";
import { NavLiens } from "@/components/nav-liens";
import { CommandPalette } from "@/components/command-palette";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "France Transparence",
    template: "%s — France Transparence",
  },
  description:
    "Les délibérations et comptes rendus des conseils municipaux, collectés " +
    "commune par commune, avec l'acte signé à l'appui de chaque montant.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" data-scroll-behavior="smooth">
      <head><meta name="theme-color" content="#ffffff" /></head>
      <body>
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-(--radius-buttons) focus:bg-midnight-ink focus:px-4 focus:py-3 focus:text-canvas-white"
        >
          Aller au contenu
        </a>
        <Navigation />
        <main id="contenu" className="mx-auto w-full max-w-(--container-page) px-4 sm:px-6">
          <ViewTransition default="page">{children}</ViewTransition>
        </main>
        <Pied />
      </body>
    </html>
  );
}

function Navigation() {
  return (
    <nav
      aria-label="Navigation principale"
      className="sans-impression mx-auto flex w-full max-w-(--container-page) items-center justify-between gap-4 border-b border-ash px-4 py-4 sm:px-6"
    >
      <Link
        href="/"
        className="inline-flex min-h-11 min-w-0 items-center gap-2 rounded-(--radius-buttons) pr-1 text-[13px] font-semibold tracking-[-0.01em] hover:text-electric-blue sm:text-[15px]"
      >
        {/* Même fichier que le favicon (app/icon.svg) : une seule source pour
            la marque, jamais deux dessins à faire diverger. */}
        <img src="/icon.svg" alt="" width={24} height={24} className="size-6 shrink-0 max-[359px]:hidden" />
        <span className="whitespace-nowrap">France&nbsp;Transparence</span>
      </Link>
      <div className="flex items-center gap-3">
        <CommandPalette />
        <NavLiens />
      </div>
    </nav>
  );
}

function Pied() {
  return (
    <footer className="mx-auto mt-16 w-full max-w-(--container-page) border-t border-ash px-4 py-8 text-[12px] leading-5 text-fog sm:px-6">
      <p>Lecture seule · Chaque montant renvoie à l&rsquo;acte signé qui le prouve.</p>
    </footer>
  );
}

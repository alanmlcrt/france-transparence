"use client";

import Link from "next/link";
import { ArrowFillButton } from "@/components/block/arrow-fill-button";

/** `ArrowFillButton` accepte un composant `as`, mais un composant serveur ne
 *  peut pas lui passer `Link` directement (une fonction ne traverse pas la
 *  frontière RSC). Ce wrapper client résout `Link` localement à la place. */
export function ArrowFillLink({ href, children, ...props }: { href: string; children: React.ReactNode } & Record<string, unknown>) {
  return (
    <ArrowFillButton as={Link} href={href} {...props}>
      {children}
    </ArrowFillButton>
  );
}

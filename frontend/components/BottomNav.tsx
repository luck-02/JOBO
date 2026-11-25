"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Accueil", icon: "⌂" },
  { href: "/suivi", label: "Suivi", icon: "☰" },
  { href: "/tips", label: "Tips", icon: "★" },
  { href: "/profil", label: "Profil", icon: "●" },
];

export default function BottomNav() {
  const path = usePathname();
  return (
    <nav className="bottomnav" aria-label="Navigation principale">
      {TABS.map((t) => {
        const active = t.href === "/" ? path === "/" || path.startsWith("/offres") : path.startsWith(t.href);
        return (
          <Link key={t.href} href={t.href} className={active ? "active" : ""}>
            <span aria-hidden>{t.icon}</span>
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}

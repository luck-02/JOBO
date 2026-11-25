import type { Metadata, Viewport } from "next";
import BottomNav from "../components/BottomNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Candidature – trouve et postule en un clic",
  description: "Offres de stage et d'alternance, CV et lettre sur mesure.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#1d4ed8" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <header className="topbar">Candidature<span className="badge">POC</span></header>
        <main className="container">{children}</main>
        <BottomNav />
      </body>
    </html>
  );
}

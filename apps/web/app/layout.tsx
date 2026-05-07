import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import "./console.css";

export const metadata: Metadata = {
  title: "Agentic QA Orchestrator",
  description: "Agentic software QA platform — control plane.",
};

export default function RootLayout({ children }: { children: ReactNode }): JSX.Element {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "QAForge AI",
  description: "Agentic software QA platform — control plane.",
};

export default function RootLayout({ children }: { children: ReactNode }): JSX.Element {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

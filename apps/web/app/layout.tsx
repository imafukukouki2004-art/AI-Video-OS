import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI Video OS",
  description: "AI Video OS operator interface",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="shell site-header__inner">
            <Link className="brand" href="/" aria-label="AI Video OS home">
              AI Video OS
            </Link>
            <span className="phase-label">Foundation</span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}

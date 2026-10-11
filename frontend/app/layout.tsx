import type { Metadata } from "next";
import "./globals.css";
import { siteUrl } from "./site";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  applicationName: "Slides Bloom",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

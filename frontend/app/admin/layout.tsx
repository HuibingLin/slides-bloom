import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Private statistics · Slides Bloom",
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}

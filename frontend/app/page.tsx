import type { Metadata } from "next";
import Home from "./home";
import { siteUrl } from "./site";

const title = "PPT Animation to PDF Converter | Slides Bloom";
const description = "Convert PowerPoint (.pptx) click animations into step-by-step PDF pages. Preview and download your PDF for free, with no account required. Files up to 20 MB.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${siteUrl}/` },
  robots: { index: true, follow: true },
  verification: process.env.GOOGLE_SITE_VERIFICATION
    ? { google: process.env.GOOGLE_SITE_VERIFICATION }
    : undefined,
  openGraph: {
    type: "website",
    url: `${siteUrl}/`,
    siteName: "Slides Bloom",
    locale: "en_US",
    title,
    description,
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Slides Bloom turns PowerPoint animation steps into PDF pages" }],
  },
  twitter: { card: "summary_large_image", title, description, images: ["/og-image.png"] },
};

const appSchema = JSON.stringify({
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "Slides Bloom",
  url: `${siteUrl}/`,
  description,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Any",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
}).replace(/</g, "\\u003c");

export default function Page() {
  return <>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: appSchema }} />
    <Home />
  </>;
}

import type { MetadataRoute } from "next";
import { siteUrl } from "./site";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    // /admin must remain crawlable so its noindex tag can be read.
    rules: { userAgent: "*", allow: "/", disallow: "/api/" },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}

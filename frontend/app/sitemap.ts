import type { MetadataRoute } from "next";
import { siteUrl } from "./site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${siteUrl}/`, changeFrequency: "monthly", priority: 1 },
    { url: `${siteUrl}/ppt-animation-to-pdf`, changeFrequency: "monthly", priority: 0.8 },
    { url: `${siteUrl}/zh-cn/ppt-animation-to-pdf`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${siteUrl}/zh-tw/ppt-animation-to-pdf`, changeFrequency: "monthly", priority: 0.6 },
  ];
}

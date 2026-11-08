// Used at build time by the statically exported site. Set SITE_URL for other hosts.
export const siteUrl = new URL(process.env.SITE_URL || "https://slidesbloom.duckdns.org").origin;
export const authorName = "Huibing Lin";
export const authorUrl = "https://github.com/HuibingLin";
export const repositoryUrl = "https://github.com/HuibingLin/slides-bloom";


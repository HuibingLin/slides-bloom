// Used at build time by the statically exported site. Set SITE_URL for other hosts.
export const siteUrl = new URL(process.env.SITE_URL || "https://slidesbloom.duckdns.org").origin;


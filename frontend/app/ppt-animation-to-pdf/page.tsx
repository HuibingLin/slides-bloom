import GuideContent, { guideMetadata } from "./guide-content";

export const metadata = guideMetadata("en");

export default function Page() {
  return <GuideContent locale="en" />;
}

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";

export const metadata: Metadata = { robots: { index: false } };

export default function ProductLayout({ children }: { children: ReactNode }) {
  return <Providers>{children}</Providers>;
}

"use client";

import { MapPin, MapPinOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { intlLocale } from "@/i18n";
import { formatDistance } from "@/lib/geolocation";

/** Where a clock-in or clock-out happened, relative to the branch area. */
export function GeoBadge({ geo, distance, label }: { geo: string | null | undefined; distance?: number | null; label?: string }) {
  const { t } = useTranslation();
  if (!geo) return null;
  const prefix = label ? `${label}: ` : "";
  if (geo === "inside") {
    return (
      <Badge tone="success" title={distance != null ? formatDistance(distance, intlLocale()) : undefined}>
        <MapPin className="size-3" aria-hidden="true" />
        {prefix}
        {t("location.inside")}
      </Badge>
    );
  }
  if (geo === "outside") {
    return (
      <Badge tone="warn">
        <MapPin className="size-3" aria-hidden="true" />
        {prefix}
        {t("location.outsideShort", { distance: formatDistance(distance ?? 0, intlLocale()) })}
      </Badge>
    );
  }
  return (
    <Badge tone="neutral">
      <MapPinOff className="size-3" aria-hidden="true" />
      {prefix}
      {geo === "no_site" ? t("location.noSite") : t("location.noFix")}
    </Badge>
  );
}

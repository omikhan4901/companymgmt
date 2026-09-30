"use client";

import { useQuery } from "@tanstack/react-query";
import { forwardRef, type SelectHTMLAttributes } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { Employee, Page } from "@/api/types";

import { Select } from "./ui/input";

/** Everyone this person may see, as a native select (the phone's own picker on mobile). */
export const PeopleSelect = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { emptyLabel?: string }>(function PeopleSelect(
  { emptyLabel, ...props },
  ref,
) {
  const { t } = useTranslation();
  const people = useQuery({
    queryKey: ["people", { status: "active", limit: 200 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { status: "active", limit: 200 } }),
  });
  return (
    <Select ref={ref} {...props}>
      <option value="">{emptyLabel ?? t("attendance.everyone")}</option>
      {(people.data?.items ?? []).map((p) => (
        <option key={p.id} value={p.id}>
          {p.full_name}
        </option>
      ))}
    </Select>
  );
});

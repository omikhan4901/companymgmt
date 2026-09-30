import { Table, type TableProps } from "antd";
import { useEffect, useRef } from "react";

/**
 * antd Table that stays keyboard-accessible when it scrolls sideways on small screens
 * (WCAG 2.1.1: scrollable regions must be focusable).
 */
export default function DataTable<T extends object>({ "aria-label": label, ...props }: TableProps<T> & { "aria-label"?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelectorAll<HTMLElement>(".ant-table-content, .ant-table-body").forEach((el) => {
      el.tabIndex = 0;
      el.setAttribute("role", "region");
      if (label) el.setAttribute("aria-label", label);
    });
  });
  return (
    <div ref={ref}>
      <Table<T> {...props} />
    </div>
  );
}

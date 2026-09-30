import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Form, Input, Modal } from "antd";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { AttendanceRecord } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { isoToZoned, zonedToIso } from "@/lib/format";

interface Values {
  clock_in_at: string;
  clock_out_at: string;
  reason: string;
}

/**
 * Ask a manager to fix a shift (wrong or missing times). `record` is the shift to fix;
 * without it, the request adds a missing shift.
 */
export default function CorrectionModal({ record, onClose }: { record?: AttendanceRecord; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<Values>();

  const save = useMutation({
    mutationFn: (values: Values) =>
      api("/v1/attendance/corrections", {
        body: {
          kind: record ? "change" : "add",
          record_id: record?.id,
          clock_in_at: zonedToIso(values.clock_in_at, timezone),
          clock_out_at: zonedToIso(values.clock_out_at, timezone),
          reason: values.reason,
        },
      }),
    onSuccess: async () => {
      void message.success(t("attendance.requested"));
      await queryClient.invalidateQueries({ queryKey: ["attendance"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });

  const start = record ? isoToZoned(record.clock_in_at, timezone) : "";
  const end = record?.clock_out_at ? isoToZoned(record.clock_out_at, timezone) : "";

  return (
    <Modal
      open
      title={record ? t("attendance.fixTitle") : t("attendance.addMissing")}
      okText={t("attendance.requestFix")}
      cancelText={t("common.cancel")}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={save.isPending}
      destroyOnHidden
    >
      <p className="mb-4 text-sm text-slate-500">{t("attendance.fixSub")}</p>
      <Form form={form} layout="vertical" requiredMark={false} initialValues={{ clock_in_at: start, clock_out_at: end }} onFinish={(v) => save.mutate(v)}>
        <div className="grid gap-x-3 sm:grid-cols-2">
          <Form.Item name="clock_in_at" label={t("attendance.startTime")} rules={[{ required: true }]}>
            <Input type="datetime-local" />
          </Form.Item>
          <Form.Item name="clock_out_at" label={t("attendance.endTime")} rules={[{ required: true }]}>
            <Input type="datetime-local" />
          </Form.Item>
        </div>
        <Form.Item name="reason" label={t("common.reason")} extra={t("attendance.reasonHelp")} rules={[{ required: true, min: 3, max: 500 }]}>
          <Input.TextArea rows={2} maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

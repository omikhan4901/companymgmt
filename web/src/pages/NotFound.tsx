import { Button } from "antd";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import Logo from "@/components/Logo";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <main className="grid min-h-screen place-items-center px-4 text-center">
      <div className="flex flex-col items-center gap-4">
        <Logo />
        <h1 className="font-display text-2xl font-bold text-ink">{t("errors.notFound")}</h1>
        <Link to="/">
          <Button type="primary">{t("errors.goHome")}</Button>
        </Link>
      </div>
    </main>
  );
}

import { StyleProvider } from "@ant-design/cssinjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider, Spin } from "antd";
import bnBD from "antd/locale/bn_BD";
import enGB from "antd/locale/en_GB";
import { MotionConfig } from "motion/react";
import { lazy, Suspense, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router";

import { ApiError } from "@/api/client";
import { SessionProvider, useSession } from "@/auth/session";
import AppShell from "@/components/AppShell";

import { theme } from "./theme";

const Login = lazy(() => import("@/pages/auth/Login"));
const Signup = lazy(() => import("@/pages/auth/Signup"));
const Forgot = lazy(() => import("@/pages/auth/Forgot"));
const Reset = lazy(() => import("@/pages/auth/Reset"));
const VerifyEmail = lazy(() => import("@/pages/auth/VerifyEmail"));
const Invite = lazy(() => import("@/pages/auth/Invite"));
const ChangePassword = lazy(() => import("@/pages/auth/ChangePassword"));
const Home = lazy(() => import("@/pages/Home"));
const Attendance = lazy(() => import("@/pages/attendance/AttendancePage"));
const People = lazy(() => import("@/pages/people/PeoplePage"));
const Team = lazy(() => import("@/pages/team/TeamPage"));
const Settings = lazy(() => import("@/pages/settings/SettingsPage"));
const Account = lazy(() => import("@/pages/account/AccountPage"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      staleTime: 15_000,
    },
  },
});

function Loading() {
  return (
    <div className="grid min-h-[50vh] place-items-center" role="status" aria-live="polite">
      <Spin />
    </div>
  );
}

function RequireSession({ children }: { children: ReactNode }) {
  const { ready, signedIn, me } = useSession();
  const location = useLocation();
  if (!ready) return <Loading />;
  if (!signedIn || !me) {
    const next = location.pathname === "/" ? "" : `?next=${encodeURIComponent(location.pathname + location.search)}`;
    return <Navigate to={`/login${next}`} replace />;
  }
  if (me.must_change_password && location.pathname !== "/change-password") return <Navigate to="/change-password" replace />;
  if (!me.workspace && location.pathname !== "/account") return <Navigate to="/account" replace />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { ready, signedIn } = useSession();
  if (!ready) return <Loading />;
  if (signedIn) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Lazy() {
  return (
    <Suspense fallback={<Loading />}>
      <Outlet />
    </Suspense>
  );
}

const router = createBrowserRouter([
  {
    element: <Lazy />,
    children: [
      { path: "/login", element: <PublicOnly><Login /></PublicOnly> },
      { path: "/signup", element: <PublicOnly><Signup /></PublicOnly> },
      { path: "/forgot-password", element: <Forgot /> },
      { path: "/reset-password", element: <Reset /> },
      { path: "/verify-email", element: <VerifyEmail /> },
      { path: "/invite", element: <Invite /> },
      { path: "/change-password", element: <RequireSession><ChangePassword /></RequireSession> },
      {
        element: (
          <RequireSession>
            <AppShell />
          </RequireSession>
        ),
        children: [
          {
            element: <Lazy />,
            children: [
              { index: true, element: <Home /> },
              { path: "attendance", element: <Attendance /> },
              { path: "people", element: <People /> },
              { path: "team", element: <Team /> },
              { path: "settings", element: <Settings /> },
              { path: "account", element: <Account /> },
            ],
          },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

function Localized({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation();
  return (
    <ConfigProvider theme={theme} locale={i18n.language === "bn" ? bnBD : enGB}>
      {children}
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      {/* antd styles go in the "antd" cascade layer so Tailwind utilities can override them. */}
      <StyleProvider layer>
      <QueryClientProvider client={queryClient}>
        <Localized>
          <AntApp>
            <SessionProvider>
              <RouterProvider router={router} />
            </SessionProvider>
          </AntApp>
        </Localized>
      </QueryClientProvider>
      </StyleProvider>
    </MotionConfig>
  );
}

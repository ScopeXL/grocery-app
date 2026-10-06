import { QueryCache, QueryClient, useQueryClient } from "@tanstack/react-query";
import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";
import { useEffect } from "react";

import { ApiError } from "./api/client";
import { qk } from "./api/keys";
import { SignInScreen } from "./features/auth/SignInScreen";
import { WhoScreen } from "./features/auth/WhoScreen";
import { ListScreen } from "./features/list/ListScreen";
import { MealsScreen } from "./features/meals/MealsScreen";
import { MoreScreen } from "./features/more/MoreScreen";
import { InstallScreen } from "./features/onboarding/InstallScreen";
import { PlanScreen } from "./features/plan/PlanScreen";
import { AboutScreen } from "./features/settings/AboutScreen";
import { SettingsScreen } from "./features/settings/SettingsScreen";
import { createEventHandler } from "./lib/eventRouter";
import { LiveUpdates } from "./lib/events";
import { shouldShowInstallFirst } from "./lib/platform";
import {
  fetchSession,
  probeSession,
  rememberSignedIn,
  signedInBefore,
  type Session,
} from "./lib/session";
import { OfflinePill, ToastRegion, UpdatePrompt } from "./ui/StatusLayer";
import { TabBar } from "./ui/TabBar";

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) handleSignedOut();
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      retry: (count, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
    mutations: { retry: 0 },
  },
});

export function handleSignedOut(): void {
  rememberSignedIn(false);
  queryClient.setQueryData(qk.session(), null);
  void router.navigate({ to: "/sign-in" });
}

async function currentSession(client: QueryClient): Promise<Session | null | "offline"> {
  try {
    return await client.query({
      queryKey: qk.session(),
      queryFn: fetchSession,
      staleTime: "static",
    });
  } catch {
    return "offline";
  }
}

function RootLayout() {
  return (
    <>
      <OfflinePill />
      <Outlet />
      <ToastRegion />
      <UpdatePrompt />
    </>
  );
}

function SignedLayout() {
  const client = useQueryClient();
  useEffect(() => {
    const live = new LiveUpdates({
      onEvent: createEventHandler(client, handleSignedOut),
      onPoll: () => void client.invalidateQueries(),
      probeSession,
    });
    live.start();
    return () => {
      live.stop();
    };
  }, [client]);
  return <Outlet />;
}

function TabsLayout() {
  return (
    <>
      <div className="lg:pl-60">
        <Outlet />
      </div>
      <TabBar />
    </>
  );
}

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootLayout,
});

const installRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/install",
  validateSearch: (search: Record<string, unknown>): { from?: "more" } =>
    search.from === "more" ? { from: "more" } : {},
  component: InstallScreen,
});

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sign-in",
  beforeLoad: async ({ context }) => {
    const session = await currentSession(context.queryClient);
    if (session && session !== "offline") throw redirect({ to: "/" });
  },
  component: SignInScreen,
});

const signedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "signed",
  beforeLoad: async ({ context }) => {
    const session = await currentSession(context.queryClient);
    if (session === "offline") {
      // A phone that signed in before opens offline; only a real 401 signs it out.
      if (signedInBefore()) return;
      throw redirect({ to: "/sign-in" });
    }
    if (!session) {
      if (shouldShowInstallFirst()) throw redirect({ to: "/install", search: {} });
      throw redirect({ to: "/sign-in" });
    }
  },
  component: SignedLayout,
});

const whoRoute = createRoute({
  getParentRoute: () => signedRoute,
  path: "/who",
  component: WhoScreen,
});
const tabsRoute = createRoute({
  getParentRoute: () => signedRoute,
  id: "tabs",
  component: TabsLayout,
});
const planRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/",
  component: PlanScreen,
});
const mealsRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/meals",
  component: MealsScreen,
});
const listRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/list",
  component: ListScreen,
});
const moreRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/more",
  component: MoreScreen,
});
const settingsRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/settings",
  component: SettingsScreen,
});
const aboutRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/about",
  component: AboutScreen,
});

const routeTree = rootRoute.addChildren([
  installRoute,
  signInRoute,
  signedRoute.addChildren([
    whoRoute,
    tabsRoute.addChildren([planRoute, mealsRoute, listRoute, moreRoute, settingsRoute, aboutRoute]),
  ]),
]);

export const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

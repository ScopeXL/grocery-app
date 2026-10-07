import { QueryCache, QueryClient, useQueryClient } from "@tanstack/react-query";
import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";
import { useEffect } from "react";

import { api, ApiError, unwrap } from "./api/client";
import { qk } from "./api/keys";
import { JoinScreen } from "./features/auth/JoinScreen";
import { SignInScreen } from "./features/auth/SignInScreen";
import { WhoScreen, type WhoFrom } from "./features/auth/WhoScreen";
import { ListScreen } from "./features/list/ListScreen";
import { MealDetailScreen } from "./features/meals/MealDetailScreen";
import { EditMealScreen, NewMealScreen } from "./features/meals/MealEditor";
import { MealsScreen } from "./features/meals/MealsScreen";
import type { Role } from "./features/meals/types";
import { connectResult, type ConnectResult } from "./features/kroger/account";
import { KrogerDoneScreen } from "./features/kroger/KrogerDoneScreen";
import { MoreScreen } from "./features/more/MoreScreen";
import { FirstRunScreen, type FirstRunStep } from "./features/onboarding/FirstRunScreen";
import { InstallScreen } from "./features/onboarding/InstallScreen";
import { PlanScreen } from "./features/plan/PlanScreen";
import { AboutScreen } from "./features/settings/AboutScreen";
import { SettingsScreen } from "./features/settings/SettingsScreen";
import { WalkingOrderScreen } from "./features/settings/WalkingOrderScreen";
import { ShoppingScreen } from "./features/shopping/ShoppingScreen";
import { TripDetailScreen } from "./features/trips/TripDetailScreen";
import { TripsScreen } from "./features/trips/TripsScreen";
import { createEventHandler } from "./lib/eventRouter";
import { LiveUpdates } from "./lib/events";
import { outbox } from "./lib/outbox";
import { shouldShowInstallFirst } from "./lib/platform";
import {
  fetchSession,
  probeSession,
  rememberSignedIn,
  signedInBefore,
  type Session,
} from "./lib/session";
import { warmTripImages } from "./lib/images";
import { hydrateTrips, photoUrls, syncActiveTrips, tripStore } from "./lib/trips";
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

/**
 * Every saved list being shopped, on this phone with its photos, so a phone is ready for the
 * store even when someone else saved the list (PLAN §9.4).
 */
async function refreshTrips(): Promise<void> {
  if (!(await syncActiveTrips())) return;
  for (const trip of tripStore.list()) {
    if (trip.header.status === "active") void warmTripImages(trip.header.id, photoUrls(trip));
  }
}

function SignedLayout() {
  const client = useQueryClient();
  useEffect(() => {
    // Saved lists live on this phone (IndexedDB); unsent taps go out whenever there's signal.
    void hydrateTrips().then(refreshTrips);
    const visible = () => {
      if (document.visibilityState === "visible") void refreshTrips();
    };
    document.addEventListener("visibilitychange", visible);
    const stop = outbox.start();
    return () => {
      document.removeEventListener("visibilitychange", visible);
      stop();
    };
  }, []);
  useEffect(() => {
    const live = new LiveUpdates({
      onEvent: createEventHandler(client, handleSignedOut),
      onPoll: () => {
        void client.invalidateQueries();
        void refreshTrips();
      },
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
      <div className="lg:pl-60 print:pl-0">
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

/** Connect Kroger finished in another browser (an iPhone's home-screen app can do that). */
const krogerDoneRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/kroger-done",
  validateSearch: (search: Record<string, unknown>): { result: ConnectResult } => ({
    result: connectResult(search.result) ?? "failed",
  }),
  component: function KrogerDone() {
    const { result } = krogerDoneRoute.useSearch();
    return <KrogerDoneScreen result={result} />;
  },
});

/** A scanned Add-a-phone QR code: `/join#<code>` (Settings → Add a phone). */
const joinRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/join",
  beforeLoad: async ({ context }) => {
    const session = await currentSession(context.queryClient);
    if (session && session !== "offline") throw redirect({ to: "/" });
  },
  component: JoinScreen,
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
  validateSearch: (search: Record<string, unknown>): { from?: WhoFrom } =>
    search.from === "more" || search.from === "settings" ? { from: search.from } : {},
  component: function Who() {
    const { from } = whoRoute.useSearch();
    return <WhoScreen from={from} />;
  },
});
const welcomeRoute = createRoute({
  getParentRoute: () => signedRoute,
  path: "/welcome",
  validateSearch: (search: Record<string, unknown>): { step?: FirstRunStep } =>
    search.step === "dinner" || search.step === "done" ? { step: search.step } : {},
  component: function Welcome() {
    const { step } = welcomeRoute.useSearch();
    return <FirstRunScreen step={step ?? "store"} />;
  },
});
const newMealRoute = createRoute({
  getParentRoute: () => signedRoute,
  path: "/meals/new",
  validateSearch: (search: Record<string, unknown>): { role?: Role; first?: boolean } => {
    const valid: { role?: Role; first?: boolean } = {};
    if (search.role === "main" || search.role === "side") valid.role = search.role;
    if (search.first === true || search.first === "true") valid.first = true;
    return valid;
  },
  component: function NewMeal() {
    const { role, first } = newMealRoute.useSearch();
    return <NewMealScreen role={role} first={first} />;
  },
});
const editMealRoute = createRoute({
  getParentRoute: () => signedRoute,
  path: "/meals/$dishId/edit",
  component: function EditMeal() {
    const { dishId } = editMealRoute.useParams();
    return <EditMealScreen dishId={dishId} />;
  },
});

/** Shopping mode is full screen: no tabs, nothing between the shopper and the list. */
const shopRoute = createRoute({
  getParentRoute: () => signedRoute,
  path: "/shop/$tripId",
  component: function Shop() {
    const { tripId } = shopRoute.useParams();
    return <ShoppingScreen tripId={tripId} />;
  },
});

/** The tabs need a store first (UX §4.3); offline or unknown, the app doesn't block on it. */
async function hasStore(client: QueryClient): Promise<boolean> {
  try {
    const active = await client.query({
      queryKey: qk.activeStore(),
      queryFn: async () => unwrap(await api.GET("/api/stores/active")),
      staleTime: 60_000,
      retry: false, // offline should open the app at once, not after retries
    });
    return active.store !== null;
  } catch {
    return true;
  }
}

const tabsRoute = createRoute({
  getParentRoute: () => signedRoute,
  id: "tabs",
  beforeLoad: async ({ context }) => {
    if (!(await hasStore(context.queryClient))) {
      throw redirect({ to: "/welcome", search: { step: "store" } });
    }
  },
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
  validateSearch: (search: Record<string, unknown>): { role?: Role } =>
    search.role === "side" ? { role: "side" } : {},
  component: function Meals() {
    const { role } = mealsRoute.useSearch();
    return <MealsScreen role={role ?? "main"} />;
  },
});
const mealRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/meals/$dishId",
  component: function Meal() {
    const { dishId } = mealRoute.useParams();
    return <MealDetailScreen dishId={dishId} />;
  },
});
const listRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/list",
  validateSearch: (search: Record<string, unknown>): { show?: "unpriced" } =>
    search.show === "unpriced" ? { show: "unpriced" } : {},
  component: function List() {
    const { show } = listRoute.useSearch();
    return <ListScreen show={show} />;
  },
});
const moreRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/more",
  component: MoreScreen,
});
const settingsRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/settings",
  validateSearch: (search: Record<string, unknown>): { kroger?: ConnectResult } => {
    const result = connectResult(search.kroger);
    return result ? { kroger: result } : {};
  },
  component: function Settings() {
    const { kroger } = settingsRoute.useSearch();
    return <SettingsScreen kroger={kroger} />;
  },
});
const tripsRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/trips",
  component: TripsScreen,
});
const tripRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/trips/$tripId",
  component: function Trip() {
    const { tripId } = tripRoute.useParams();
    return <TripDetailScreen tripId={tripId} />;
  },
});
const walkingOrderRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/settings/walking-order",
  component: WalkingOrderScreen,
});
const aboutRoute = createRoute({
  getParentRoute: () => tabsRoute,
  path: "/about",
  component: AboutScreen,
});

const routeTree = rootRoute.addChildren([
  installRoute,
  krogerDoneRoute,
  joinRoute,
  signInRoute,
  signedRoute.addChildren([
    whoRoute,
    welcomeRoute,
    newMealRoute,
    editMealRoute,
    shopRoute,
    tabsRoute.addChildren([
      planRoute,
      mealsRoute,
      mealRoute,
      listRoute,
      moreRoute,
      settingsRoute,
      walkingOrderRoute,
      tripsRoute,
      tripRoute,
      aboutRoute,
    ]),
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

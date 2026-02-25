import { createSignal, createContext, useContext, type ParentProps, type Accessor } from "solid-js";

export type HomeRoute = { type: "home" };
export type SessionRoute = { type: "session" };
export type Route = HomeRoute | SessionRoute;

type RouteContextValue = {
  data: Accessor<Route>;
  navigate: (route: Route) => void;
};

const RouteContext = createContext<RouteContextValue | undefined>(undefined);

export function RouteProvider(props: ParentProps) {
  const [data, setData] = createSignal<Route>({ type: "home" });
  const value: RouteContextValue = {
    data,
    navigate(route: Route) {
      setData(route);
    },
  };
  return (
    <RouteContext.Provider value={value}>
      {props.children}
    </RouteContext.Provider>
  );
}

export function useRoute() {
  const ctx = useContext(RouteContext);
  if (!ctx) throw new Error("useRoute must be used within RouteProvider");
  return ctx;
}

export function useRouteData<T extends Route["type"]>(_type: T) {
  const route = useRoute();
  return route.data as Accessor<Extract<Route, { type: T }>>;
}

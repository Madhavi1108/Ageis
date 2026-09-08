import { Outlet } from "react-router-dom";

import { ErrorBoundary } from "../feedback/ErrorBoundary";
import { SideNav } from "./SideNav";
import { TopBar } from "./TopBar";

export function AppLayout() {
  return (
    <div className="flex h-full min-h-screen bg-bg text-fg">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-w-0 flex-1 overflow-y-auto p-4">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

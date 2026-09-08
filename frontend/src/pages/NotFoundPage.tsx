import { Link } from "react-router-dom";

import { EmptyState } from "../components/feedback/EmptyState";

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md pt-16">
      <EmptyState
        title="Page not found"
        hint="The route you followed doesn't exist in the dashboard."
        action={
          <Link to="/" className="text-sm text-accent underline">
            Back to the dashboard
          </Link>
        }
      />
    </div>
  );
}

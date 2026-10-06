import { useNavigate } from "@tanstack/react-router";

import { Button } from "../../ui/Button";
import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";

export function PlanScreen() {
  const navigate = useNavigate();
  return (
    <Screen title="This week">
      <EmptyState
        message="No meals planned yet. Add a dinner and the shopping list builds itself."
        note="Planning the week arrives in the next update. Until then, add the meals you make."
        action={
          <Button onClick={() => void navigate({ to: "/meals", search: { role: "main" } })}>
            Go to Meals
          </Button>
        }
      />
    </Screen>
  );
}

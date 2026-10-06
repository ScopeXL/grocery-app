import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";

export function PlanScreen() {
  return (
    <Screen title="This week">
      <EmptyState
        message="No meals planned yet. Add a dinner and the shopping list builds itself."
        note="Adding meals arrives in the next update."
      />
    </Screen>
  );
}

import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";

export function MealsScreen() {
  return (
    <Screen title="Meals">
      <EmptyState
        message="Your meals live here. Start with a dinner you make often."
        note="Adding meals arrives in the next update."
      />
    </Screen>
  );
}

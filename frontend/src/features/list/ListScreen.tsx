import { EmptyState } from "../../ui/EmptyState";
import { Screen } from "../../ui/Screen";

export function ListScreen() {
  return (
    <Screen title="Shopping list">
      <EmptyState
        message="Your list fills in as you plan meals. You can also add things like milk."
        note="The shopping list arrives in an upcoming update."
      />
    </Screen>
  );
}

import { Screen } from "../../ui/Screen";

export function AboutScreen() {
  return (
    <Screen title="About & privacy">
      <div className="flex flex-col gap-6 rounded-tile border border-rule bg-paper p-5 text-body">
        <p>
          Dinner Bell {__APP_VERSION__} plans the week’s meals and builds one shared shopping list
          for the household.
        </p>
        <p>
          Dinner Bell is an independent project and is not affiliated with, endorsed by, or
          sponsored by The Kroger Co.
        </p>
        <div>
          <h2 className="mb-2 text-row font-bold">Your data</h2>
          <ul className="list-disc space-y-2 pl-6">
            <li>Everything is stored on the server your household runs, nowhere else.</li>
            <li>No analytics, no tracking, no ads, and no third-party scripts.</li>
            <li>Product searches and your chosen store go to Kroger to show prices and aisles.</li>
            <li>Settings lets you export everything at any time.</li>
          </ul>
        </div>
        <p className="text-secondary text-ink-soft">Open source under the MIT license.</p>
      </div>
    </Screen>
  );
}

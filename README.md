# Dinner Bell

A household meal-planning and grocery app, built for phones:

- **Plan the week's dinners.** Mains, sides, and the occasional breakfast or snack. Dinner Bell suggests meals that use what you're already buying.
- **Get one shared shopping list.** Built automatically from the plan, rounded to whole packages, with an estimated total and sale prices from your chosen Kroger store.
- **Shop it aisle by aisle.** The list works offline in the store and syncs live between family members' phones.
- **Or order online.** Send the list to your Kroger cart for pickup or delivery; nothing is ever added twice by accident.
- **Easy for the whole family.** One household password, or a QR code from a phone that's already signed in.

**Status:** in everyday use by its household. [CHANGELOG.md](CHANGELOG.md) lists what each release added.

## Documentation

- [Plan](docs/PLAN.md): architecture, data model, Kroger integration, quantity math, milestones.
- [UX](docs/UX.md): screens, flows and visual design.
- [Decision records](docs/adr/README.md): why things are the way they are.
- [CLAUDE.md](CLAUDE.md): working rules for the AI sessions that build and maintain this app.

## Self-hosting

Dinner Bell ships as one Docker image, `scopexl/dinner-bell`, with all state on a `/data` volume and all configuration in environment variables. See [Deploying](docs/DEPLOY.md), [Kroger setup](docs/KROGER.md) (product data, and Connect Kroger for the cart), [Restoring a backup](docs/RESTORE.md) and [Releasing](docs/RELEASING.md).

Without Kroger keys it runs in sample mode, with made-up products, which is how it's developed and tested.

## Not affiliated with Kroger

Dinner Bell is an independent project and is not affiliated with, endorsed by, or sponsored by The Kroger Co. It uses the public Kroger APIs under Kroger's developer terms. Product names, images and prices are shown as Kroger provides them.

## Privacy

See [PRIVACY.md](PRIVACY.md). In short: your data stays on your own server, and there are no analytics or third-party scripts.

## License

[MIT](LICENSE)

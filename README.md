# Dinner Bell

A household meal-planning and grocery app, built for phones:

- **Plan the week's dinners.** Mains, sides, and the occasional breakfast or snack.
- **Get one shared shopping list.** Built automatically from the plan, with an estimated total from your chosen Kroger store.
- **Shop it aisle by aisle.** The list works offline and syncs live between family members' phones.
- **Or order online.** Send the list to your Kroger cart for pickup or delivery.

**Status:** planning complete. The first release (0.1.0) will come out of milestone M0.

## Documentation

- [Plan](docs/PLAN.md): architecture, data model, Kroger integration, quantity math, milestones.
- [UX](docs/UX.md): screens, flows and visual design.
- [Decision records](docs/adr/README.md): why things are the way they are.
- [CLAUDE.md](CLAUDE.md): working rules for the AI sessions that build and maintain this app.

## Self-hosting

Dinner Bell ships as one Docker image, `scopexl/dinner-bell`, with all state on a `/data` volume and all configuration in environment variables. Deployment and restore guides will be added in M0.

## Not affiliated with Kroger

Dinner Bell is an independent project and is not affiliated with, endorsed by, or sponsored by The Kroger Co. It uses the public Kroger APIs under Kroger's developer terms. Product names, images and prices are shown as Kroger provides them.

## Privacy

See [PRIVACY.md](PRIVACY.md). In short: your data stays on your own server, and there are no analytics or third-party scripts.

## License

[MIT](LICENSE)

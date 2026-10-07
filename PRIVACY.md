# Privacy

**Status:** current as of version 0.6.0, which has every feature this page describes.

Each Dinner Bell installation is run by the household that deploys it. The authors of this project receive no data from any installation.

## What Dinner Bell stores

Everything is kept in a SQLite database on the server's `/data` volume, and in its backups:

- Household members' display names, and which member added or checked off what.
- Meals, plans, shopping lists and saved trips, including the estimated and actual totals you enter.
- Meal photos you upload, resized, with their EXIF data removed.
- Signed-in devices: a short label and timestamps. IP addresses are not stored.
- The store you chose.
- A short-lived cache of Kroger product data (descriptions, prices, aisles), kept no longer than Kroger's cache rules allow.
- If you connect a Kroger account for Send to cart: your Kroger access tokens, encrypted, and which member connected it. Your Kroger password never reaches Dinner Bell: you sign in on Kroger's own page.
- A record of which items were sent to the Kroger cart, kept a week (or a day after the trip is finished) so nothing is added twice by mistake.
- "Add a phone" codes, stored only as a one-way hash and usable once, for 10 minutes.

## What is sent to Kroger

- **Product searches and your chosen store,** so Dinner Bell can show products, prices and aisles. Search terms are not stored.
- **Items you choose to add to your Kroger cart,** only when you tap Send, and only to the account you connected.
- **Your browser loads product images directly from Kroger,** so Kroger receives your device's IP address for those requests. Dinner Bell asks your browser not to send the page address along with them.

## What Dinner Bell does not do

- No analytics, tracking, advertising or telemetry.
- No third-party scripts or CDNs. Fonts are served by the app itself.
- No selling or sharing of data with anyone.

## Your control

- **Export everything** as JSON: Settings → Data → Export all data.
- **Disconnect your Kroger account:** Settings → Kroger account. This deletes the stored tokens.
- **Delete all data:** whoever runs the server removes the `/data` volume.

## Contact

Report security issues privately through the repository's GitHub security advisories (private vulnerability reporting). Other questions can go in a GitHub issue.

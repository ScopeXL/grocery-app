# ADR 0025: Add a phone with a one-time code, scanned or typed

- **Status:** Accepted (refines ADR 0004's "QR join")
- **Date:** 2026-10-07

## Context

ADR 0004 planned a QR code that lets a signed-in phone sign in a new one without the household password: a single-use, 5-minute token in `/join#<token>`.

On an iPhone that falls short:
- The camera opens the link in Safari.
- The home-screen app keeps its own cookies (UX §5.1).
- A token used in Safari signs in Safari, and the installed app still asks for the password.
- A link-only token can't be carried over by hand.

## Decision

**The code**
- A signed-in phone (Settings → Add a phone) shows one code two ways: a QR code for `/join#<code>`, and the same code in letters ("4F7K 9QX2").
- It is 8 characters from an alphabet without look-alikes (no 0, O, 1, I or L): about 40 bits.
- It is single-use and lasts **10 minutes**, which leaves time to install the app first.
- It is stored as an HMAC under its own key (`join-code-v1`), so a database copy doesn't give away live codes.
- A new code retires the phone's older unused one. A code stops working if its phone is signed out.

**Using it**
- The new phone scans it or types it on the sign-in screen under **Use a code from another phone**.
- On an iPhone in Safari, the join page suggests installing first and typing the code in the home-screen app. "Sign in here in Safari instead" stays one tap away.
- Wrong codes count against the login limits: 5 per 15 minutes per address, 50 an hour in all. At that rate, no one can guess a code in its 10 minutes.

## Consequences

- An iPhone can join the installed app with no password at all.
- The fragment carries the code, so it never reaches a proxy's or the server's logs. The join page also removes it from the browser history once read.
- Anyone who can see the screen during those 10 minutes could use the code. For a household app that is the same exposure as saying the password aloud, and the code works only once.

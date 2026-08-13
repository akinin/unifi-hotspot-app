# Changelog

## 0.3.0

- Redesign the administration interface to match Home Assistant cards, colors, spacing, and responsive behavior.
- Add live client and archive search with result counters.
- Add quick SMS recipient selection, copy actions, message length counter, refresh controls, and an in-app confirmation dialog for destructive actions.

## 0.2.3

- Document the mandatory Wiren Board `send_sms.js` rule and include the script in the repository.

## 0.2.2

- Fix the Home Assistant Ingress entry path so the administration interface opens without a double slash.

## 0.2.1

- Replace the application icon and logo with the official Wiren Board artwork.

## 0.2.0

- Initial Home Assistant App packaging.
- Home Assistant Ingress for the administrator interface.
- Persistent database and generated application secret in `/data`.
- Safe UniFi dry-run mode enabled by default.
- Non-conflicting test ports for parallel operation with the existing LXC.

# Changelog

## 0.5.7

- Allow the trusted preview iframe to load its same-origin saved logo through Home Assistant ingress.
- Replace the stretching two-pane Hotspot summary with one compact six-field card.

## 0.5.6

- Merge the Portal and UniFi connection summaries into one compact card.
- Match the designer sidebar height to the preview card and remove client/archive tabs from its header.
- Serve the saved portal logo through an ingress-safe, non-cached preview route instead of a CSP-blocked data URL.

## 0.5.5

- Move the portal preview from the main product navigation into the Hotspot section.
- Turn the Portal card icon into the current logo picker and simplify the settings row.
- Add a portal background color picker and build the existing gradient from that color.
- Embed the current portal logo in the preview so Home Assistant ingress cannot break its URL.
- Add a live logo-size slider in the preview and persist the selected size for the real portal.

## 0.5.4

- Add a safe Hotspot preview tab that renders the real guest login page without allowing SMS requests or access changes.
- Add compact mobile and wide preview modes with an explicit refresh action.

## 0.5.3

- Run ModemManager at normal log level to avoid filling the app log with virtual TTY discovery details.

## 0.5.2

- Replace the combined SMS Gateway tab with separate WB and USB tabs.
- Route WB test messages explicitly through MQTT and USB test messages through ModemManager.
- Keep ModemManager available alongside WB so either transport can be tested without changing the portal OTP default.

## 0.5.1

- Start D-Bus and ModemManager only when the USB backend is selected.
- Run the USB D-Bus socket without unsupported UID/GID changes inside the protected Home Assistant app container.

## 0.5.0

- Reposition the Home Assistant App as UniFi Hotspot with an integrated SMS transport.
- Make Hotspot the default workspace and keep SMS Gateway as a secondary WB/USB workspace.
- Preserve the existing app slug and persistent data for an in-place upgrade.
- Expose MQTT and USB ModemManager backend selection in app settings.
- Use the supplied UniFi artwork for the Home Assistant app icon and the supplied USB artwork for the USB transport.

## 0.4.2

- Replace the UniFi artwork everywhere with the supplied PNG without redrawing it.
- Use the active product identity in the page header and favicon.
- Make portal settings denser and consolidate guest extension, revocation, and blocking into one action menu.
- Reduce the active-client table from eight columns to five while preserving authorization details.

## 0.4.1

- Use the supplied WB and UniFi SVG assets in the interface; place UniFi artwork on its brand-blue `#0559C9` background.
- Compact the dashboard and stack related cards to remove empty layout gaps.
- Add a UniFi connection summary with mode, controller, site, access duration, and credential state.
- Record confirmed WB delivery results from every source, including `wirenboard-discovery`, without duplicate journal rows.
- Add a protected UniFi Hotspot API for portal settings, active clients, archive, extension, revocation, and blocking.

## 0.4.0

- Split the interface into dedicated WB and UniFi workspaces.
- Add the SMS delivery journal, MQTT connection summary, and viewing/downloading of the mandatory `send_sms.js` rule.
- Use the supplied Wiren Board logo asset in the interface without recreating it.

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

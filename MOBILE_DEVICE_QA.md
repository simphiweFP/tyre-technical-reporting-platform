# Mobile Device Sign-off

Use this checklist on the deployed HTTPS environment before production sign-off.

## Required devices

- Android: current Chrome on a physical phone with rear camera.
- iPhone: current Safari on a physical iPhone with rear camera.
- Desktop: current Edge or Chrome at 1280px or wider.

Record device model, OS/browser version, tester and date for every run.

## Report capture

1. Sign in and start a new report.
2. Confirm the three-step progress bar is readable without horizontal clipping.
3. Complete Report details with dropdowns, customer lookup and required validation.
4. On Take photos, use **camera capture** for at least:
   - DOT
   - Serial number
   - Entire tyre
   - Issue
   - Tread depth
   - Vehicle
5. Use **gallery upload** for at least one separate photo.
6. Confirm every preview uses the correct image and can be removed/replaced.
7. Confirm Gemini analysis returns without blocking photo storage if AI fails.
8. Confirm AI-populated tyre/vehicle fields remain editable.
9. Confirm each Gemini image comment stays associated with its photo.
10. Open tyre-position selector and select positions for Car, Horse and Trailer.
11. Complete Tyre & vehicle and reach Preview.
12. Confirm recipient must be selected before Send report is enabled.
13. Confirm SweetAlert confirmation fits the screen and can be cancelled.
14. Send one test report to the approved test mailbox.
15. Open the sent item in Delivery Centre and verify the immutable PDF.
16. Send a user-written follow-up and confirm it appears in the same email thread where supported.

## Responsive / touch checks

- No horizontal page scrolling except intentionally scrollable data tables.
- Buttons have comfortable touch targets and do not overlap.
- Keyboard does not permanently cover the active field/action.
- Select controls remain usable with the native mobile picker.
- Modals fit the viewport and can always be closed.
- Long customer/email/error text wraps instead of breaking the page.
- Orientation change does not lose unsaved form state.
- Back navigation does not silently discard captured work.

## Connectivity checks

1. Start a draft while online.
2. Disable connectivity.
3. Edit text fields and capture a photo.
4. Confirm the app indicates offline state and keeps the draft locally.
5. Re-enable connectivity.
6. Confirm queued report/photo changes sync.
7. If the server version changed while offline, confirm the conflict is surfaced rather than silently overwritten.

## Evidence required for sign-off

For Android and iPhone attach:
- screenshot of each wizard step;
- screenshot of the tyre-position selector;
- screenshot of Preview;
- screenshot of successful SweetAlert/send result;
- screenshot of Delivery Centre sent-email view;
- received email screenshot with PDF attachment;
- any failure/error notes.

## Sign-off

| Device | OS / Browser | Camera | Gemini | Offline sync | PDF/email | Result | Tester / Date |
|---|---|---|---|---|---|---|---|
| Android |  |  |  |  |  | Pending |  |
| iPhone |  |  |  |  |  | Pending |  |
| Desktop |  | N/A |  |  |  | Pending |  |

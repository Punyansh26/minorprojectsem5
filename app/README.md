# Web Application Client

**Chhattisgarhi Voice-to-Voice Agricultural Shopping Assistant**

This directory hosts the web client front-end for the Minor Project MVP.

---

## 🎯 Scope & Product Definition

- **Format:** Web development (Chromium-based desktop browser priority, responsive for mobile browsers)
- **Voice-first UX:** The user speaks naturally in Chhattisgarhi to browse agricultural products, verify prices/quantities, update their shopping cart, and complete a simulated checkout.
- **Safety Boundaries:** Grounded actions only. Fixed KVK-referral response on pesticide/dosage or crop-diagnosis requests.
- **Backend Communication:** Real-time WebSocket connection to the STS (Speech-to-Speech) pipeline for live audio streaming, transcription, and TTS playback.

For the complete specification and UI/UX flows, refer to [`idea/docs/WEB_APP_SPECIFICATION.md`](../idea/docs/WEB_APP_SPECIFICATION.md).

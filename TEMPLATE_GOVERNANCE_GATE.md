# Controlled Template Governance Gate

The current bundled Basic Vehicle Inspection Checklist is **provisional test content**. It is not the approved inspection sheet and must not be activated for real customer visits.

All templates that predate this governance release are permanently locked as provisional records. They remain readable only for continuity; they cannot be reclassified or approved by editing a name, reference, or hash.

Before any template can become active for new Check-in sessions, an authorized administrator must provide and record:

1. A controlled source reference for the approved inspection artifact.
2. The artifact’s exact SHA-256 content hash.
3. A non-provisional declaration and named approving administrator.
4. An explicit approval action in Workbai.

Workbai permits only one active approved non-provisional template for new Check-in sessions. The server, not the browser, selects and locks that record for a new visit, then stores its content snapshot and recorded provenance with the inspection session.

The available email evidence confirms that the inspection sheet exists and that torque-spec verification is required, but the attachment/PDF itself was not retrievable. This build therefore adds governance mechanics only. It does not infer sheet fields, torque values, thresholds, locations, layout, vehicle applicability, or evidence policy.

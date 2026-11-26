// How an assessment's status is shown, wherever one is listed.

import { pill } from "./ui.js";

export const STATUS = { planned: ["Planned", ""], in_progress: ["In progress", "info"], complete: ["Complete", "ok"], cancelled: ["Cancelled", ""] };

export const statusPill = (status) => pill(STATUS[status]?.[0] ?? status, STATUS[status]?.[1] ?? "");

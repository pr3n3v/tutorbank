// Model ids come from models.json — the ONE place they live (CLAUDE.md §5).
import models from "./models.json" with { type: "json" };

export const DEEPSEEK_BASE_URL = models.base_url;
export const MODEL_LIVE = models.fast; // /ask default: fast chat
export const MODEL_SOLVE = models.accurate; // /ask solve mode: value swaps, accuracy

export const DIAGRAMS_BUCKET = "diagrams";
export const SIGNED_URL_TTL_SECONDS = 3600; // clients download PNGs immediately at sync

export const ASK_TIMEOUT_MS = 60_000;
export const ASK_MAX_PROMPT_CHARS = 4_000;

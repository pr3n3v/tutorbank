// /sync — full question bank JSON for the watch/phone offline cache (CLAUDE.md §2, §9 M2).
// GET, auth via X-App-Secret. Diagram PNGs come back as short-lived signed URLs;
// clients download them immediately during sync.

import { createClient } from "jsr:@supabase/supabase-js@2";
import { json, requireAppSecret } from "../_shared/auth.ts";
import { DIAGRAMS_BUCKET, SIGNED_URL_TTL_SECONDS } from "../_shared/config.ts";

Deno.serve(async (req) => {
  if (req.method !== "GET") return json({ error: "method not allowed" }, 405);
  const denied = await requireAppSecret(req);
  if (denied) return denied;

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  // format_profile is generation config — never shipped to clients.
  const { data: subjects, error } = await supabase
    .from("subjects")
    .select(`
      id, code, name,
      assignments ( id, title, number, source_file ),
      units (
        id, name, position,
        questions (
          id, text, qtype, variables, position, assignment_id,
          answers (
            id, variant, summary, answer, final_answer, followups,
            diagram_png_watch, diagram_png_phone, verified, confidence
          )
        )
      )
    `)
    .order("code")
    .order("position", { referencedTable: "units" });

  if (error) return json({ error: error.message }, 500);

  // One batch signed-URL call for every diagram path in the bank.
  const paths = new Set<string>();
  for (const s of subjects ?? []) {
    for (const u of s.units ?? []) {
      for (const q of u.questions ?? []) {
        for (const a of q.answers ?? []) {
          if (a.diagram_png_watch) paths.add(a.diagram_png_watch);
          if (a.diagram_png_phone) paths.add(a.diagram_png_phone);
        }
      }
    }
  }

  const urlFor = new Map<string, string>();
  if (paths.size > 0) {
    const { data: signed, error: signErr } = await supabase.storage
      .from(DIAGRAMS_BUCKET)
      .createSignedUrls([...paths], SIGNED_URL_TTL_SECONDS);
    if (signErr) return json({ error: signErr.message }, 500);
    for (const s of signed ?? []) {
      if (s.path && s.signedUrl) urlFor.set(s.path, s.signedUrl);
    }
  }

  for (const s of subjects ?? []) {
    for (const u of s.units ?? []) {
      u.questions?.sort((a, b) => a.position - b.position);
      for (const q of u.questions ?? []) {
        for (const a of q.answers ?? []) {
          a.diagram_watch_url = a.diagram_png_watch
            ? urlFor.get(a.diagram_png_watch) ?? null
            : null;
          a.diagram_phone_url = a.diagram_png_phone
            ? urlFor.get(a.diagram_png_phone) ?? null
            : null;
          delete a.diagram_png_watch;
          delete a.diagram_png_phone;
        }
      }
    }
  }

  return json({
    generated_at: new Date().toISOString(),
    signed_url_ttl_seconds: SIGNED_URL_TTL_SECONDS,
    subjects: subjects ?? [],
  });
});

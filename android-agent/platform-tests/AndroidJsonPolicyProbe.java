package com.formafx.storyfx.validation;

import com.formafx.storyfx.agent.publication.PublicationPolicy;
import org.json.JSONObject;

/** Pure synthetic policy regression executed on Android's own JSON implementation. */
public final class AndroidJsonPolicyProbe {
    public static void main(String[] args) throws Exception {
        JSONObject payload = new JSONObject()
            .put("device", "Validation technique").put("execution_origin", "web_android_agent")
            .put("web_triggered", true).put("platform", "WhatsApp").put("engine", "multi")
            .put("count", 3).put("due_at", "2020-01-01T00:00:00Z")
            .put("album", "Validation technique").put("album2", JSONObject.NULL)
            .put("page", JSONObject.NULL).put("page_name", JSONObject.NULL).put("system", JSONObject.NULL);
        JSONObject job = new JSONObject().put("id", "00000000-0000-0000-0000-000000000001")
            .put("occurrence_id", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
            .put("payload", payload);
        boolean androidNullCoercion = "null".equals(payload.optString("page_name"));
        if (!androidNullCoercion) throw new AssertionError("ANDROID_JSON_RUNTIME_REQUIRED");
        PublicationPolicy.INSTANCE.validate(job, "Validation technique");
        if (!"Validation technique".equals(PublicationPolicy.INSTANCE.album(payload)))
            throw new AssertionError("NULL_ALBUM_FALLBACK_FAILED");
        int rejected = 0;
        for (Object value : new Object[] {"Validation technique autre", "null", 42, true}) {
            payload.put("page_name", value);
            try { PublicationPolicy.INSTANCE.validate(job, "Validation technique"); }
            catch (IllegalArgumentException expected) { rejected++; }
        }
        if (rejected != 4) throw new AssertionError("DESTINATION_GUARD_FAILED");
        System.out.println("{\"android_json_null_coercion_verified\":true,\"nullable_policy_passed\":true,"
            + "\"album_fallback_passed\":true,\"unapproved_destinations_rejected\":4,\"phone_actions\":false}");
    }
}

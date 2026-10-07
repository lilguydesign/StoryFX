package com.formafx.storyfx.validation;

import com.formafx.storyfx.agent.publication.PublicationPolicy;
import com.formafx.storyfx.agent.publication.MediaPlan;
import com.formafx.storyfx.agent.publication.MediaShare;
import android.content.Intent;
import android.net.Uri;
import java.util.ArrayList;
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
        payload.put("page_name", JSONObject.NULL).put("album2", "Validation technique lot").put("count", 11);
        for (String mode : new String[] {"intro", "multi", "intro+multi"}) {
            payload.put("engine", mode);
            PublicationPolicy.INSTANCE.validate(job, "Validation technique");
            int expected = mode.equals("intro") ? 1 : mode.equals("multi") ? 11 : 12;
            if (MediaPlan.INSTANCE.total(payload) != expected) throw new AssertionError("MEDIA_MODE_COUNT_FAILED");
        }
        ArrayList<Uri> media = new ArrayList<>();
        ArrayList<String> types = new ArrayList<>();
        media.add(Uri.parse("content://validation/video/1")); types.add("video/mp4");
        for (int index = 1; index <= 11; index++) {
            media.add(Uri.parse("content://validation/image/" + index)); types.add("image/jpeg");
        }
        Intent share = MediaShare.INSTANCE.intent(media, types);
        ArrayList<Uri> streams = share.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
        if (!"*/*".equals(share.getType()) || !media.equals(streams) || share.getClipData().getItemCount() != 12 ||
            !"com.whatsapp.w4b".equals(share.getPackage()) ||
            (share.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION) == 0)
            throw new AssertionError("MIXED_SHARE_ORDER_OR_GRANT_FAILED");
        System.out.println("{\"android_json_null_coercion_verified\":true,\"nullable_policy_passed\":true,"
            + "\"album_fallback_passed\":true,\"unapproved_destinations_rejected\":4,\"media_modes_passed\":3,"
            + "\"mixed_share_order_verified\":true,\"phone_actions\":false}");
    }
}

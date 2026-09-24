import { defineConfig } from "@neon/config/v1";

// Declares the Neon services this backend uses. Apply with `neon deploy`,
// which also pulls DATABASE_URL and the AWS_* storage variables into .env.
export default defineConfig({
  buckets: {
    // Course videos, cover images and avatars. Private: videos are served
    // through short-lived presigned URLs after an access check.
    "intered-hub-uploads": { access: "private" },
  },
});

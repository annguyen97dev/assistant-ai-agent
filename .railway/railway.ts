import { defineRailway, preserve, project, service } from "railway/iac";

export default defineRailway(() => {
  const dailySync = service("daily-sync", {
    deploy: {
      startCommand: "python main.py",
      cronSchedule: "0 19 * * *",
      restartPolicyType: "NEVER",
    },
    env: {
      FILE_SEARCH_STORE_NAME: "fileSearchStores/optibot-help-center-3aahsbbl6zbm",
      GEMINI_API_KEY: preserve(),
    },
  });

  return project("violet-queue-07", {
    resources: [dailySync],
  });
});

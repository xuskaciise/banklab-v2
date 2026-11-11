import { redirect } from "next/navigation";

/** Moved to the Admin section. */
export default function PlatformRedirect() {
  redirect("/admin/platform");
}
